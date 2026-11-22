#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""llm.py - gateway unico do ecossistema para modelos locais (Ollama) e de nuvem (NVIDIA).

Exemplos:
  llm.py --listar
  llm.py --papel doc --arquivo edital.txt --instrucao "Liste prazos e multas" --saida prazos.md
  llm.py --papel doc --arquivo edital_longo.txt --instrucao "..." --partes
  llm.py --papel raciocinio-nuvem --nuvem --texto "Pergunta conceitual sem dado sigiloso"

Garantias:
  1. num_ctx dimensionado pelo tamanho do insumo; nunca trunca em silencio
     (aborta, divide com --partes, ou alerta se o Ollama indicar truncamento).
  2. Papel de nuvem exige a flag --nuvem: o conteudo sai da workstation.
  3. Com --saida, a resposta vai para arquivo e o terminal mostra so estatisticas.
"""
import argparse, json, os, re, sys, time
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parent.parent
PAPEIS = json.loads((RAIZ / "config" / "papeis.json").read_text(encoding="utf-8"))
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
NVIDIA = "https://integrate.api.nvidia.com/v1/chat/completions"
# Provedores de nuvem que falam o formato OpenAI de chat completions. Acrescentar um aqui e
# acrescentar uma linha, nao um caminho de codigo novo. O Google NAO entra nesta tabela: o SDK
# dele tem outra forma e vive em bin/argon_core.py.
PROVEDORES_OPENAI = {
    "nvidia": {"url": NVIDIA, "chave": "NVIDIA_API_KEY"},
    "deepseek": {"url": "https://api.deepseek.com/v1/chat/completions",
                 "chave": "DEEPSEEK_API_KEY"},
    # Moonshot (Kimi). Duas particularidades MEDIDAS em 23/10/2026, nao supostas:
    #  1. a familia k3 e de raciocinio puro e RECUSA temperatura diferente de 1, com HTTP 400
    #     "invalid temperature: only 1 is allowed for this model". Para esses modelos o campo e
    #     omitido e vale o padrao da API.
    #  2. reasoning_effort e HONRADO (low contra max, 4 repeticoes cada: 4,2 s e 112 caracteres
    #     de raciocinio contra 10,9 s e 1.748, intervalos sem sobreposicao), POREM a API NAO
    #     valida o valor: tanto um valor invalido quanto um nome de parametro inventado voltam
    #     200. Erro de digitacao nao da erro, so custa 2,6 vezes o tempo em silencio, por isso a
    #     validacao e feita AQUI.
    "moonshot": {"url": "https://api.moonshot.ai/v1/chat/completions",
                 "chave": "MOONSHOT_API_KEY",
                 "sem_temperatura": ("kimi-k3", "kimi-k3.1-pro", "kimi-k3.1-pro-highspeed"),
                 "esforcos": ("low", "high", "max")},
}
DEGRAUS_CTX = [4096, 8192, 16384, 32768, 65536, 131072]
# Estimativa PESSIMISTA de tokens (limite superior plausivel para portugues com numeros e acentos).
# Motivo: quando o prompt excede num_ctx, o Ollama descarta ~metade do contexto e guarda o FINAL,
# e o prompt_eval_count devolvido nao permite detectar isso de forma confiavel. Logo, prevenir.
CHARS_POR_TOKEN = 2.5
FORMATOS_TEXTO = {".txt", ".md", ".csv", ".json", ".tsv", ".xml", ".html"}


def estimar_tokens(txt):
    return int(len(txt) / CHARS_POR_TOKEN) + 1


def chave_env(nome):
    """Le a credencial do ambiente ou dos .env conhecidos. Nunca devolve string vazia: ou acha,
    ou encerra dizendo onde procurou."""
    if os.environ.get(nome):
        return os.environ[nome]
    # ORDEM DELIBERADA: ~/TransportMCP/.env PRIMEIRO. Ele nao e sincronizado.
    # ~/ecossistema/.env fica dentro da pasta que o Syncthing envia para quatro
    # dispositivos, entao credencial ali se replica em maquina que talvez nem precise
    # dela. Ate 24/10 a ordem era a inversa e o arquivo EXPOSTO era o que vencia.
    for p in [Path.home() / "TransportMCP" / ".env", RAIZ / ".env"]:
        if p.exists():
            for l in p.read_text(encoding="utf-8").splitlines():
                if l.startswith(nome + "="):
                    v = l.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    sys.exit(f"ERRO: {nome} nao encontrada (ambiente, ~/ecossistema/.env ou "
             f"~/TransportMCP/.env). Atencao: ~/ecossistema/.env e sincronizado pelo Syncthing "
             f"para quatro dispositivos; credencial que nao precisa estar neles vai em "
             f"~/TransportMCP/.env.")


def chave_nvidia():
    return chave_env("NVIDIA_API_KEY")


def _sem_credencial(texto):
    """Nenhum texto de erro de provedor sai sem passar por aqui. Estes provedores mandam a chave
    em cabecalho Authorization, nao em query string, mas um dia um deles pode mudar, e a hora de
    descobrir isso nao e lendo a chave na tela."""
    s = str(texto)
    s = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9_\-.]{8,}", r"\1<censurado>", s)
    s = re.sub(r"(?i)(\bkey=)[^&\s'\"]+", r"\1<censurado>", s)
    for nome in ("NVIDIA_API_KEY", "DEEPSEEK_API_KEY", "NGC_API_KEY", "GEMINI_API_KEY"):
        v = os.environ.get(nome, "")
        if v and len(v) >= 8:
            s = s.replace(v, "<censurado>")
    return s


def montar_prompt(instrucao, conteudo):
    """Conteudo primeiro, tarefa por ultimo: modelos pequenos perdem a instrucao depois de texto longo."""
    if not conteudo:
        return instrucao
    if not instrucao:
        return conteudo  # prompt bruto: o proprio conteudo ja traz a solicitacao
    citar = (" Ao usar uma informacao, indicar a pagina de origem: o texto de cada pagina N fica entre"
             " <!-- pagina N: inicio --> e <!-- pagina N: fim -->."
             if "<!-- pagina " in conteudo else "")
    return (f"=== CONTEUDO ===\n{conteudo}\n=== FIM DO CONTEUDO ===\n\n"
            f"TAREFA (responder apenas com base no conteudo acima): {instrucao}{citar}")


def limpar_raciocinio(txt):
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()


IMAGENS = []  # caminhos de imagem para papeis de visao (preenchido por --imagem)

# Tetos de imagem. [premissa] NAO conferidos na API de nenhum provedor: sao limites LOCAIS,
# escolhidos para recusar aqui, com mensagem que diz o que fazer, em vez de deixar o provedor
# recusar com HTTP 400 generico ou, pior, aceitar e reescalar em silencio. Uma pagina A4 de PDF
# rasterizada a 300 dpi em PNG fica tipicamente entre 1 e 4 MB, entao 8 MB acomoda a pagina densa
# e barra o despejo de uma foto de camera inteira.
TETO_IMAGEM_MB = 8          # por imagem, medida ANTES do base64
TETO_IMAGENS_TOTAL_MB = 20  # soma DEPOIS do base64, que e o que trafega
# [premissa] custo de uma imagem em tokens para os provedores de formato OpenAI. O valor real
# depende da resolucao e do ladrilhamento interno de cada modelo, e nenhum dos tres declara o
# numero numa rota consultavel. 4096 e teto alto de proposito: aqui o erro so pode ser para o
# lado de RECUSAR, porque truncar em silencio e o que esta verificacao existe para impedir.
# No Google NAO se usa esta constante: argon_core conta pela propria API, inclusive a imagem.
TOKENS_POR_IMAGEM = 4096

ASSINATURAS_IMAGEM = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
                      (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))


def _mime_da_imagem(dados, caminho):
    """Tipo decidido pelo CONTEUDO, nunca pela extensao. Arquivo renomeado seria aceito pelo nome
    e recusado la na frente, com erro que nao aponta para o nome."""
    for assinatura, mime in ASSINATURAS_IMAGEM:
        if dados.startswith(assinatura):
            return mime
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    sys.exit(f"ERRO: {caminho} nao e PNG, JPEG, GIF nem WEBP pelos bytes iniciais "
             f"({dados[:8]!r}). O tipo e decidido pelo conteudo e nao pela extensao.")


class Imagem(dict):
    """Dicionario com representacao CURTA. Motivo medido em 21/11/2026: a estrutura carrega os
    bytes do arquivo e o base64, entao um print, um repr em traceback ou um log de depuracao
    despejava centenas de milhares de caracteres (287 KB num teste de 9 casos). O conteudo
    continua acessivel por chave; so a representacao e que nao o despeja."""

    def __repr__(self):
        return (f"<Imagem {Path(self['caminho']).name} {self['mime']} {self['mb']} MB "
                f"base64 {len(self['b64'])} chars>")

    __str__ = __repr__


def preparar_imagens(caminhos=None):
    """Le cada imagem UMA vez e devolve o que os dois caminhos de nuvem precisam: 'bytes' e
    'mime' para o SDK do Google, 'b64' para o data URI do formato OpenAI. Recusa aqui, com
    mensagem acionavel, o que o provedor recusaria com HTTP 400 sem explicar."""
    import base64
    saida, soma_b64 = [], 0
    for c in (IMAGENS if caminhos is None else caminhos):
        p = Path(c)
        if not p.is_file():
            sys.exit(f"ERRO: imagem nao encontrada: {p}")
        dados = p.read_bytes()
        mb = len(dados) / 1048576
        if mb > TETO_IMAGEM_MB:
            sys.exit(f"ERRO: {p.name} tem {mb:.1f} MB, acima do teto local de {TETO_IMAGEM_MB} MB "
                     f"por imagem. Reduzir a resolucao (pagina de PDF a 150-200 dpi costuma "
                     f"bastar para leitura de tabela) ou recortar a regiao de interesse.")
        b64 = base64.b64encode(dados).decode()
        soma_b64 += len(b64)
        saida.append(Imagem(caminho=str(p), bytes=dados, b64=b64,
                            mime=_mime_da_imagem(dados, p), mb=round(mb, 2)))
    total = soma_b64 / 1048576
    if total > TETO_IMAGENS_TOTAL_MB:
        sys.exit(f"ERRO: as {len(saida)} imagens somam {total:.1f} MB ja em base64, acima do teto "
                 f"local de {TETO_IMAGENS_TOTAL_MB} MB. Enviar em chamadas separadas.")
    return saida


def chamar_local(modelo, prompt, ctx, max_tokens, temperatura,
                 esquema=None, pensar=None):
    """esquema: dicionario de JSON Schema. Quando dado, o Ollama DECODIFICA RESTRITO a ele e a
    saida e JSON valido por construcao, nao por obediencia ao prompt.
    pensar: False desliga o raciocinio de modelo que pensa (qwen3 e afins).

    MEDIDO em 17/11/2026, qwen3:14b, 6 documentos reais do acervo, prompt de ~6000 chars:
        sem esquema .... mediana 17,6 s, 0 de 6 com JSON valido, 6 de 6 VAZIOS
        com esquema .... mediana  3,0 s, 6 de 6 validos
    A resposta vinha vazia porque o modelo gastava os 700 tokens de num_predict pensando e o
    raciocinio era removido depois. Pedir JSON no prompt NAO resolve isso; restringir a
    decodificacao resolve. Ambos os argumentos sao opcionais e o padrao preserva o
    comportamento anterior, para nao mexer em quem ja chama esta funcao."""
    j = {
        "model": modelo, "prompt": prompt, "stream": False, "keep_alive": "30m",
        "options": {"num_ctx": ctx, "num_predict": max_tokens, "temperature": temperatura}}
    if esquema is not None:
        j["format"] = esquema
    if pensar is not None:
        j["think"] = bool(pensar)
    if IMAGENS:
        import base64
        j["images"] = [base64.b64encode(Path(i).read_bytes()).decode() for i in IMAGENS]
    r = requests.post(f"{OLLAMA}/api/generate", timeout=1800, json=j)
    r.raise_for_status()
    d = r.json()
    return d.get("response", ""), d.get("prompt_eval_count", 0), d.get("eval_count", 0)


def chamar_nuvem(modelo, prompt, max_tokens, temperatura, provedor="nvidia", esforco="",
                 imagens=None):
    """imagens: saida de preparar_imagens(). Sem imagem o corpo e identico ao anterior, com
    'content' em string: nao se muda a forma da chamada de quem nao pediu imagem."""
    if provedor not in PROVEDORES_OPENAI:
        sys.exit(f"ERRO: provedor '{provedor}' desconhecido. Conhecidos: "
                 f"{', '.join(sorted(PROVEDORES_OPENAI))}.")
    p = PROVEDORES_OPENAI[provedor]
    if imagens:
        # Formato OpenAI de mensagem multimodal: 'content' deixa de ser string e vira lista de
        # partes. A imagem vem ANTES do texto pelo mesmo motivo medido que poe a instrucao no fim
        # do prompt. Vai como data URI e nao como URL remota: a imagem esta em disco aqui, e uma
        # URL exigiria publica-la em algum lugar.
        conteudo = [{"type": "image_url",
                     "image_url": {"url": f"data:{i['mime']};base64,{i['b64']}"}} for i in imagens]
        conteudo.append({"type": "text", "text": prompt})
    else:
        conteudo = prompt
    corpo = {"model": modelo, "messages": [{"role": "user", "content": conteudo}],
             "max_tokens": max_tokens}
    if modelo not in p.get("sem_temperatura", ()):
        corpo["temperature"] = temperatura
    if esforco:
        validos = p.get("esforcos", ())
        if not validos:
            sys.exit(f"ERRO: o provedor '{provedor}' nao declara esforco de raciocinio.")
        if esforco not in validos:
            # Validado AQUI porque o provedor aceita valor invalido em silencio.
            sys.exit(f"ERRO: esforco '{esforco}' invalido para {provedor}. Validos: "
                     f"{', '.join(validos)}. A API aceitaria o valor errado sem reclamar e "
                     f"cobraria o esforco padrao, por isso a recusa e local.")
        corpo["reasoning_effort"] = esforco
    r = requests.post(p["url"], timeout=300,
                      headers={"Authorization": f"Bearer {chave_env(p['chave'])}"}, json=corpo)
    if r.status_code != 200:
        # O corpo entra na mensagem porque 'HTTP 400' sozinho nao diagnostica nada; passa pela
        # censura antes de sair.
        dica = ""
        if imagens and r.status_code in (400, 404, 415, 422):
            dica = (f"\nDICA: a chamada levava {len(imagens)} imagem(ns). Recusa nesta faixa de "
                    f"codigo costuma ser modelo que nao aceita entrada de imagem, e nao defeito "
                    f"do pedido. Conferir se '{modelo}' declara entrada multimodal antes de mexer "
                    f"no resto.")
        sys.exit(f"ERRO nuvem {provedor} HTTP {r.status_code} em {modelo}: "
                 f"{_sem_credencial(r.text)[:400]}{dica}")
    d = r.json()
    u = d.get("usage", {})
    msg = d["choices"][0]["message"]
    texto = msg.get("content") or ""
    if not texto.strip():
        # Modelo de raciocinio puro devolve o pensamento em reasoning_content e a resposta em
        # content. Conteudo vazio com raciocinio cheio significa orcamento de saida gasto
        # pensando, e NAO modelo quebrado: e max_tokens curto demais, ou esforco alto demais.
        racio = len(msg.get("reasoning_content") or "")
        if racio:
            sys.exit(f"ERRO nuvem {provedor}: resposta vazia com {racio} caracteres de "
                     f"raciocinio em {modelo}. O orcamento de saida acabou antes de sair texto: "
                     f"aumentar --max-tokens (agora {max_tokens}) ou baixar o esforco para 'low'.")
        sys.exit(f"ERRO nuvem {provedor}: resposta vazia em {modelo}, sem motivo declarado. "
                 "Resposta vazia nao e resposta.")
    return texto, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def chamar_google(modelo_, prompt, max_tokens, temperatura, ctx_max=0, persona="", imagens=None):
    """Papel de nuvem do Google (Argon/Gemini). Delega a bin/argon_core.py, que e a FONTE UNICA
    das regras de censura de credencial, de recusa em vez de truncar e de autorizacao de saida
    de dado. A autorizacao de saida aqui ja foi dada pela flag --nuvem, conferida em main().
    persona='auditor' aplica o prompt de sistema do auditor; vazio deixa o modelo generico."""
    sys.path.insert(0, str(RAIZ / "bin"))
    try:
        import argon_core
    except ImportError as e:
        sys.exit(f"ERRO: bin/argon_core.py nao importavel por {sys.executable}: {e}")
    try:
        r = argon_core.gerar_texto(
            prompt, sistema=(argon_core.SISTEMA if persona == "auditor" else ""),
            mod=modelo_, max_tokens=max_tokens, temperatura=temperatura,
            ctx_max=ctx_max, nao_sigiloso=True, imagens=imagens)
    except argon_core.ArgonErro as e:
        sys.exit(f"ERRO nuvem Google: {e}")
    return r["texto"], r["tokens_in"], r["tokens_out"]


def prova_real(cfg, enunciado, referencia, max_tokens):
    """VERIFICACAO INDEPENDENTE, nao segunda opiniao: o Argon escreve uma rotina autocontida, a
    rotina e executada AQUI, na Ubuntu, em ambiente isolado, e o veredito e a comparacao dos dois
    numeros. O numero de referencia nao vai no prompt: o calculo do Argon e feito as cegas.
    Esta funcao nao existe no servidor MCP do Windows de proposito: codigo escrito por modelo nao
    roda na estacao de trabalho."""
    sys.path.insert(0, str(RAIZ / "bin"))
    try:
        import argon_core
    except ImportError as e:
        sys.exit(f"ERRO: bin/argon_core.py nao importavel por {sys.executable}: {e}")
    try:
        return argon_core.prova_independente(
            enunciado, meu_resultado=referencia, nao_sigiloso=True, mod=cfg["modelo"],
            max_tokens=max_tokens, ctx_max=cfg.get("ctx_max", 0), executar=True)
    except argon_core.ArgonErro as e:
        return {"veredito": "ERRO", "motivo": str(e)}


def escolher_ctx(tokens_in, max_tokens, ctx_max):
    necessario = tokens_in + max_tokens + 256
    for c in DEGRAUS_CTX:
        if necessario <= c <= ctx_max:
            return c
    return None


def dividir(texto, orcamento):
    """Divide por linhas respeitando o orcamento de tokens; linha gigante e cortada por caracteres."""
    blocos, atual = [], ""
    limite_chars = int(orcamento * CHARS_POR_TOKEN)
    for linha in texto.split("\n"):
        while estimar_tokens(linha) > orcamento:
            if atual:
                blocos.append(atual); atual = ""
            blocos.append(linha[:limite_chars]); linha = linha[limite_chars:]
        if estimar_tokens(atual + linha) > orcamento and atual:
            blocos.append(atual); atual = ""
        atual += linha + "\n"
    if atual.strip():
        blocos.append(atual)
    return blocos


def executar_local(cfg, instrucao, conteudo, max_tokens, temperatura):
    """Contexto FIXO no ctx_max do papel (evita recarga do modelo a cada chamada).
    Recusa (None) se a estimativa pessimista nao couber: nunca envia prompt que possa ser truncado."""
    prompt = montar_prompt(instrucao, conteudo)
    est = estimar_tokens(prompt)
    ctx = cfg["ctx_max"]
    if est + max_tokens + 256 > ctx:
        return None, est
    t = time.time()
    resp, tin, tout = chamar_local(cfg["modelo"], prompt, ctx, max_tokens, temperatura)
    return {"texto": resp, "tin": tin, "tout": tout, "ctx": ctx, "seg": time.time() - t}, est


VAZIAS = ("nenhum", "nenhuma", "nao ha", "não há", "nao foram encontrad", "não foram encontrad", "sem ocorrencia")


def resposta_vazia(txt):
    t = txt.strip().lower()
    return (not t) or any(t.startswith(v) for v in VAZIAS)


def main():
    ap = argparse.ArgumentParser(description="Gateway de modelos do ecossistema")
    ap.add_argument("--papel"); ap.add_argument("--listar", action="store_true")
    ap.add_argument("--instrucao", default=""); ap.add_argument("--texto"); ap.add_argument("--arquivo")
    ap.add_argument("--saida"); ap.add_argument("--partes", action="store_true")
    ap.add_argument("--tam-parte", type=int, default=6000,
                    help="tokens estimados por parte no modo --partes (padrao 6000; extracao rende mais em partes curtas)")
    ap.add_argument("--nuvem", action="store_true"); ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--temperatura", type=float, default=0.2)
    ap.add_argument("--modelo", help="modelo Ollama avulso, sem papel (uso legado)")
    ap.add_argument("--ocr", action="store_true", help="PDF digitalizado: aplicar OCRmyPDF antes do Docling")
    ap.add_argument("--imagem", action="append", default=[], help="imagem (PNG, JPEG, GIF ou WEBP) para papel que declare visao, local ou de "
                         "nuvem; repetivel. O tipo e decidido pelos bytes, nao pela extensao")
    ap.add_argument("--ctx", type=int, default=16384, help="num_ctx fixo para --modelo")
    ap.add_argument("--consolidar", choices=["concatenar", "llm"], default="concatenar",
                    help="modo partes: concatenar (extracao, deterministico) ou llm (sintese/resumo)")
    ap.add_argument("--manter-raciocinio", action="store_true")
    ap.add_argument("--prova", action="store_true",
                    help="papel do Argon: verificacao independente. O modelo escreve a "
                         "rotina, a Ubuntu executa em ambiente isolado e compara os numeros")
    ap.add_argument("--referencia", type=float,
                    help="numero a conferir na --prova; sem ele o veredito e CALCULADO")
    a = ap.parse_args()

    if a.listar or not (a.papel or a.modelo):
        print(f"{'PAPEL':22} {'ONDE':6} {'MODELO':46} {'CTX':>7}  USO")
        for n, c in PAPEIS.items():
            print(f"{n:22} {c['onde']:6} {c['modelo']:46} {str(c.get('ctx_max', '-')):>7}  {c['uso']}")
        return
    if a.modelo:
        cfg = {"onde": "local", "modelo": a.modelo, "ctx_max": a.ctx, "max_tokens": 2048, "uso": "avulso"}
        a.papel = f"avulso:{a.modelo}"
    elif a.papel not in PAPEIS:
        sys.exit(f"ERRO: papel '{a.papel}' inexistente. Use --listar.")
    else:
        cfg = PAPEIS[a.papel]
    if cfg.get("embeddings"):
        sys.exit(f"ERRO: '{a.papel}' e papel de embeddings (vetores), nao gera texto.")
    max_tokens = a.max_tokens or cfg.get("max_tokens", 2048)
    if a.imagem:
        # A capacidade de ler imagem e declarada NO PAPEL, e papel so muda por medicao. Nao ha
        # tabela de modelos multimodais aqui de proposito: ela envelheceria em silencio, como ja
        # aconteceu com catalogo de modelo de nuvem duas vezes neste ecossistema.
        if not cfg.get("visao"):
            visuais = [n for n, c in PAPEIS.items() if c.get("visao")]
            sys.exit(f"ERRO: o papel '{a.papel}' nao declara leitura de imagem. Papeis que "
                     f"declaram: {', '.join(visuais) or 'nenhum'}.")
        IMAGENS.extend(a.imagem)

    conteudo = ""
    if a.arquivo:
        p = Path(a.arquivo)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import converter as conv
        if p.suffix.lower() in conv.FORMATOS:
            md, info = conv.converter(p, ocr=a.ocr)
            print(f"[llm] conversao: {info['paginas']} pag, {info['tabelas']} tabelas, {info['seg']} s"
                  f"{' (cache)' if info['cache'] else ''}", file=sys.stderr)
            if info.get("suspeita_digitalizado"):
                sys.exit(f"ERRO: {p.name} parece digitalizado (quase sem texto extraivel). Repetir com --ocr.")
            conteudo = md.read_text(encoding="utf-8")
        elif p.suffix.lower() in FORMATOS_TEXTO:
            conteudo = p.read_text(encoding="utf-8", errors="replace")
        else:
            sys.exit(f"ERRO: formato {p.suffix} nao suportado.")
    elif a.texto == "-":
        conteudo = sys.stdin.read()
    elif a.texto:
        conteudo = a.texto
    instrucao = a.instrucao
    if not instrucao and not conteudo:
        if a.imagem:
            sys.exit("ERRO: imagem sem --instrucao. A imagem e o material, nao a pergunta: dizer "
                     "o que extrair dela (ex.: --instrucao \"Transcreva a tabela em CSV\").")
        sys.exit("ERRO: informar --instrucao e/ou conteudo.")

    t0 = time.time()
    if cfg["onde"] == "nuvem":
        if not a.nuvem:
            sys.exit("ERRO: papel de NUVEM exige --nuvem explicito. O conteudo sai da workstation: "
                     "nao usar com dado de cliente, pesquisa bruta ou material sob NDA.")
        prompt = montar_prompt(instrucao, conteudo)
        imgs = preparar_imagens() if IMAGENS else None
        if imgs:
            print(f"[llm] {len(imgs)} imagem(ns): "
                  + ", ".join(f"{Path(i['caminho']).name} {i['mime'].split('/')[1]} {i['mb']} MB"
                              for i in imgs), file=sys.stderr)
        # RECUSA EM VEZ DE TRUNCAR, agora tambem na nuvem. Ate 23/10/2026 esta verificacao
        # existia apenas no ramo local, e papel de nuvem mandava o insumo inteiro e deixava o
        # provedor cortar em silencio. Papel sem ctx_max declarado nao e verificado, e isso esta
        # dito no campo uso: contexto que eu nao conferi na API nao entra como numero aqui.
        if cfg.get("ctx_max"):
            # A imagem NAO entra em estimar_tokens, que conta caracteres. Sem a parcela abaixo,
            # um prompt curto com varias imagens passaria na verificacao e seria o provedor a
            # cortar, que e exatamente o que esta verificacao existe para impedir. No provedor
            # google a conta de verdade e refeita por argon_core contra a API, com a imagem junto.
            est = estimar_tokens(prompt) + TOKENS_POR_IMAGEM * len(imgs or [])
            if est + max_tokens > cfg["ctx_max"]:
                sys.exit(f"ERRO: insumo de ~{est} tokens (estimativa pessimista de "
                         f"{CHARS_POR_TOKEN} caracteres por token) mais {max_tokens} de resposta "
                         f"excede o ctx_max {cfg['ctx_max']} do papel '{a.papel}'. RECUSADO em "
                         f"vez de truncado: excesso de ~{est + max_tokens - cfg['ctx_max']} "
                         f"tokens. Dividir o material com --partes ou usar papel de contexto "
                         f"maior.")
        if a.prova:
            if cfg.get("provedor") != "google":
                sys.exit("ERRO: --prova existe apenas nos papeis de provedor 'google' (Argon). "
                         "Nos demais papeis de nuvem nao ha execucao da rotina, logo nao ha prova.")
            print(json.dumps(prova_real(cfg, prompt, a.referencia, max_tokens),
                             ensure_ascii=False, indent=2))
            return
        if cfg.get("provedor") == "google":
            texto, tin, tout = chamar_google(cfg["modelo"], prompt, max_tokens,
                                             a.temperatura, cfg.get("ctx_max", 0),
                                             cfg.get("persona", ""), imgs)
        else:
            texto, tin, tout = chamar_nuvem(cfg["modelo"], prompt, max_tokens, a.temperatura,
                                            cfg.get("provedor", "nvidia"), cfg.get("esforco", ""),
                                            imgs)
        modo = "nuvem"
    else:
        res, est = (None, estimar_tokens(conteudo)) if a.partes else executar_local(cfg, instrucao, conteudo, max_tokens, a.temperatura)
        modo = "local"
        if res is None:
            if not a.partes:
                sys.exit(f"ERRO: insumo de ~{est} tokens excede ctx_max {cfg['ctx_max']} do papel '{a.papel}'. "
                         f"Usar --partes (divide e consolida) ou papel de nuvem se o material nao for sigiloso.")
            orc = min(a.tam_parte, cfg["ctx_max"] - max_tokens - estimar_tokens(instrucao) - 768)
            blocos = dividir(conteudo, orc)
            print(f"[llm] modo partes: {len(blocos)} blocos de ate ~{orc} tokens", file=sys.stderr)
            parciais, tin, tout = [], 0, 0
            for i, b in enumerate(blocos, 1):
                r, _ = executar_local(cfg, instrucao, b, max_tokens, a.temperatura)
                txt = limpar_raciocinio(r["texto"])
                tin += r["tin"]; tout += r["tout"]
                if not resposta_vazia(txt):
                    parciais.append(f"[parte {i}/{len(blocos)}] {txt}")
            if not parciais:
                texto = "NENHUM (nenhuma parte retornou ocorrencia)"
            elif a.consolidar == "concatenar" or len(parciais) == 1:
                texto = "\n".join(parciais)
            else:
                final, _ = executar_local(cfg, "Consolidar as respostas parciais acima em resposta unica, sem repeticao, "
                                               f"preservando TODOS os itens. Instrucao original: {instrucao}",
                                          "\n\n".join(parciais), max_tokens, a.temperatura)
                texto = final["texto"] if final else "\n".join(parciais)
                if final:
                    tin += final["tin"]; tout += final["tout"]
            modo = f"local/{len(blocos)} partes"
        else:
            texto, tin, tout = res["texto"], res["tin"], res["tout"]

    if not a.manter_raciocinio:
        texto = limpar_raciocinio(texto)
    stats = f"[llm] papel={a.papel} modelo={cfg['modelo']} modo={modo} tokens_in={tin} tokens_out={tout} t={time.time()-t0:.1f}s"
    if a.saida:
        Path(a.saida).write_text(texto, encoding="utf-8")
        print(f"{stats} -> {a.saida} ({len(texto)} caracteres)")
    else:
        print(texto)
        print(stats, file=sys.stderr)


if __name__ == "__main__":
    main()
