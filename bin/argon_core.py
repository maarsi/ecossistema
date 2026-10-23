#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""argon_core.py - nucleo de acesso ao Argon (Gemini) como AUDITOR do ecossistema.

Fonte UNICA das tres funcoes de auditoria. E importado em dois lugares:
  - na Ubuntu, por bin/llm.py, nos papeis 'auditor-argon' e 'doc-longo-argon';
  - no Windows, por mcp/windows/argon_mcp.py, que localiza este arquivo pela variavel de
    ambiente ARGON_CORE (caminho completo do arquivo). Sem ela as ferramentas do
    servidor MCP RECUSAM, uma por uma, em vez de cair numa copia divergente (o servidor sobe
    para que o proprio diagnostico possa informar o problema). Prompt de auditoria duplicado em duas
    maquinas e prompt que vira dois criterios diferentes sem ninguem perceber.

REGRAS QUE ESTE ARQUIVO IMPLEMENTA, nao apenas documenta:

1. FRONTEIRA DE DADOS. O Argon e modelo de NUVEM: o conteudo sai da workstation. Toda
   funcao publica exige nao_sigiloso=True explicito e recusa sem ele. Em bin/llm.py essa
   autorizacao vem da flag --nuvem, que ja existia para os papeis de NVIDIA.

2. RECUSA EM VEZ DE TRUNCAR. O orcamento de contexto e conferido ANTES da chamada, com
   contagem real via models.count_tokens e recuo para a estimativa pessimista de
   bin/llm.py. Excedido, recusa e diz de quanto foi o excesso. Corte silencioso devolve
   resposta plausivel e incompleta, que e o pior defeito possivel num auditor.

3. CREDENCIAL NAO APARECE EM SAIDA. Toda mensagem de erro passa por censurar() antes de
   sair, inclusive por substituicao do literal da chave carregada. A API do Gemini aceita
   a chave em query string (?key=) e a excecao da biblioteca carrega a URL: sem censura,
   um simples erro de rede vaza a credencial. Foi exatamente assim que a chave do TomTom
   vazou em 21/10/2026.

4. ANTIANCORAGEM. auditar_metodologia() pede que a conclusao do autor seja omitida, e
   prova_independente() NAO manda o numero do solicitante para o Argon: ele calcula as
   cegas e a comparacao acontece depois, aqui. Auditor que le a resposta do auditado
   tende a concordar com ela, e a auditoria passa a medir cortesia.

5. 'SEM RESSALVA' E RESPOSTA VALIDA. Os tres prompts dizem isso ao Argon e pedem a
   justificativa da aprovacao. Sem essa valvula o modelo sempre acha um problema, e
   auditor que nunca aprova nada nao informa nada: a taxa de falso positivo e metade da
   medicao do papel.

6. PROVA REAL E CODIGO EXECUTADO, NAO PARECER. prova_independente() exige do Argon uma
   rotina autocontida, executa essa rotina em ambiente isolado e o veredito e a
   comparacao dos dois numeros. Opiniao de outro modelo sobre um calculo e segunda
   opiniao; verificacao independente e recalcular por outro caminho.

Uso em linha de comando (diagnostico):
    argon_core.py --listar-modelos
    argon_core.py --diagnostico
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VARIAVEL_CHAVE = "GEMINI_API_KEY"
VARIAVEL_MODELO = "ARGON_MODELO"
CHARS_POR_TOKEN = 2.5            # mesma estimativa pessimista de bin/llm.py
TOLERANCIA_RELATIVA = 1e-3       # 0,1%: veredito CONFERE da prova real
LIMITE_SEGUNDOS_PROVA = 60
CTX_PADRAO = 131072              # orcamento conservador quando o papel nao declara ctx_max

_CACHE_ENV: dict[str, str] = {}


# --------------------------------------------------------------------- credencial e censura

def _ler_env_arquivo(nome: str) -> str:
    """Le NOME=valor dos .env conhecidos. Nunca levanta: usado dentro de censurar()."""
    if nome in _CACHE_ENV:
        return _CACHE_ENV[nome]
    valor = ""
    for p in (RAIZ / ".env", Path.home() / "TransportMCP" / ".env"):
        try:
            if p.exists():
                for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    if linha.startswith(nome + "="):
                        valor = linha.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
        if valor:
            break
    _CACHE_ENV[nome] = valor
    return valor


_SUBSTITUICOES = (
    (re.compile(r"(?i)(\bkey=)[^&\s'\"]+"), r"\1<chave_censurada>"),
    (re.compile(r"(?i)(x-goog-api-key\W{0,4})[A-Za-z0-9_\-]{8,}"), r"\1<chave_censurada>"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{10,}"), "<chave_censurada>"),
)


def censurar(texto) -> str:
    """Remove credencial de qualquer texto que va para a saida. Ultima linha de defesa:
    substituicao do literal da chave carregada, que cobre formato de chave desconhecido."""
    s = "" if texto is None else str(texto)
    for padrao, troca in _SUBSTITUICOES:
        s = padrao.sub(troca, s)
    atual = os.environ.get(VARIAVEL_CHAVE, "").strip() or _ler_env_arquivo(VARIAVEL_CHAVE)
    if atual and len(atual) >= 8:
        s = s.replace(atual, "<chave_censurada>")
    return s


class ArgonErro(RuntimeError):
    """Erro desta camada. A mensagem JA sai censurada."""

    def __init__(self, msg):
        super().__init__(censurar(msg))


def chave(obrigatoria: bool = True) -> str:
    v = os.environ.get(VARIAVEL_CHAVE, "").strip() or _ler_env_arquivo(VARIAVEL_CHAVE)
    if not v and obrigatoria:
        raise ArgonErro(
            f"{VARIAVEL_CHAVE} nao encontrada. Procurei no ambiente, em {RAIZ / '.env'} e em "
            f"{Path.home() / 'TransportMCP' / '.env'}. No Windows a chave vem do bloco 'env' do "
            "claude_desktop_config.json, nao do codigo.")
    return v


def impressao_digital_chave() -> str:
    """Primeiros 12 hex do sha256 da chave. Serve para conferir as duas pontas SEM
    exibir a credencial."""
    import hashlib
    v = chave(obrigatoria=False)
    return hashlib.sha256(v.encode()).hexdigest()[:12] if v else "(sem chave)"


def modelo(explicito: str = "") -> str:
    m = (explicito or os.environ.get(VARIAVEL_MODELO, "").strip()
         or _ler_env_arquivo(VARIAVEL_MODELO))
    if not m:
        raise ArgonErro(
            "identificador do modelo do Argon nao definido. Nao existe padrao chumbado neste "
            "arquivo de proposito: os nomes de modelo do Gemini giram e um palpite viraria 404 "
            f"silencioso semanas depois. Definir {VARIAVEL_MODELO} no ambiente ou no .env, ou "
            "passar mod= explicito. Para ver o que a chave alcanca: argon_core.py --listar-modelos")
    return m


# ------------------------------------------------------------------------------- transporte

_CLIENTE = None
_CLIENTE_CHAVE = ""


def _cliente():
    """Cliente UNICO por processo, memorizado de proposito.

    NAO voltar a criar um Client por chamada. No google-genai 2.32.0 o transporte HTTP e
    compartilhado entre instancias: quando uma instancia de Client e coletada pelo interpretador,
    ela fecha esse transporte, e a chamada seguinte morre com 'Cannot send a request, as the
    client has been closed' ANTES de sair da maquina. Foi o que derrubou a primeira rodada da
    bateria de auditoria em 22/10/2026: contar_tokens() abria um cliente, o cliente era coletado,
    e generate_content() falhava em seguida. Os tres modelos tiraram 0/8 e o unico sinal de que
    nao era qualidade do modelo foi a latencia: 0,0 s de tempo medio."""
    global _CLIENTE, _CLIENTE_CHAVE
    k = chave()
    if _CLIENTE is not None and _CLIENTE_CHAVE == k:
        return _CLIENTE
    try:
        from google import genai
    except ImportError as e:
        raise ArgonErro(
            f"pacote google-genai ausente no interpretador {sys.executable}: {e}. "
            "Instalar com: python -m pip install google-genai")
    try:
        _CLIENTE = genai.Client(api_key=k)
    except Exception as e:
        raise ArgonErro(f"falha ao abrir o cliente: {type(e).__name__}: {e}")
    _CLIENTE_CHAVE = k
    return _CLIENTE


def listar_modelos() -> list[dict]:
    """Modelos que ESTA chave alcanca, com os limites de contexto declarados pela API.
    E daqui que sai o identificador gravado em config/papeis.json, com a data."""
    c = _cliente()
    saida = []
    try:
        for m in c.models.list():
            acoes = list(getattr(m, "supported_actions", None) or [])
            if acoes and "generateContent" not in acoes:
                continue
            saida.append({
                "nome": (getattr(m, "name", "") or "").replace("models/", ""),
                "rotulo": getattr(m, "display_name", "") or "",
                "ctx_entrada": getattr(m, "input_token_limit", None),
                "ctx_saida": getattr(m, "output_token_limit", None),
            })
    except Exception as e:
        raise ArgonErro(f"falha ao listar modelos: {type(e).__name__}: {e}")
    return saida


def contar_tokens(texto: str, mod: str = "") -> tuple[int, str]:
    """Contagem REAL pela API; recuo para a estimativa pessimista de bin/llm.py.
    Devolve (tokens, origem) com origem em {'api', 'estimado'}."""
    try:
        r = _cliente().models.count_tokens(model=modelo(mod), contents=texto)
        n = getattr(r, "total_tokens", None)
        if isinstance(n, int) and n > 0:
            return n, "api"
    except Exception:
        pass
    return int(len(texto) / CHARS_POR_TOKEN) + 1, "estimado"


def _texto_da_resposta(r) -> str:
    try:
        t = getattr(r, "text", None)
        if t:
            return t
    except Exception:
        pass
    partes = []
    for c in (getattr(r, "candidates", None) or []):
        cont = getattr(c, "content", None)
        for p in (getattr(cont, "parts", None) or []):
            if getattr(p, "text", None):
                partes.append(p.text)
    return "\n".join(partes)


def _motivo_vazio(r) -> str:
    """Diagnostico do vazio. Caso mais comum e mais confundido: modelo de raciocinio que gasta
    TODO o orcamento de saida pensando e nao sobra token para o texto. Isso aparece como
    finish_reason=MAX_TOKENS com texto vazio, e nao e falha do modelo nem da chave: e max_tokens
    curto demais. Em 22/10/2026 isso fez o gemini-3.5-flash parecer quebrado numa sondagem feita
    com max_tokens=24."""
    motivos = []
    fb = getattr(r, "prompt_feedback", None)
    if getattr(fb, "block_reason", None):
        motivos.append(f"prompt bloqueado: {fb.block_reason}")
    razoes = [str(getattr(c, "finish_reason", "")) for c in (getattr(r, "candidates", None) or [])]
    if any("MAX_TOKENS" in x for x in razoes):
        u = getattr(r, "usage_metadata", None)
        pensados = getattr(u, "thoughts_token_count", None)
        motivos.append("finish_reason=MAX_TOKENS com texto vazio: o orcamento de saida acabou "
                       "antes de sair texto"
                       + (f" ({pensados} tokens foram gastos raciocinando)" if pensados else "")
                       + ". AUMENTAR max_tokens; nao e falha do modelo nem da chave")
    else:
        motivos += [f"finish_reason={x}" for x in razoes if x]
    return "; ".join(motivos) or "sem motivo declarado pela API"


def _exigir_autorizacao(nao_sigiloso) -> None:
    if nao_sigiloso is not True:
        raise ArgonErro(
            "o Argon e modelo de NUVEM: o conteudo sai da workstation. Exige nao_sigiloso=True "
            "explicito. Nao usar com dado de cliente, pesquisa bruta ou material sob NDA. Para "
            "auditar METODO sobre material sigiloso, substituir o dado por sintetico ou agregado "
            "e enviar so a formulacao e a rotina.")


SISTEMA = (
    "Voce e o Argon, auditor metodologico de uma consultoria de Engenharia de Transportes. "
    "Escreva em portugues do Brasil e NAO use travessao (em dash): no lugar dele, virgula, ponto "
    "e virgula, dois-pontos ou parenteses. Seja direto e tecnico; o interlocutor e engenheiro "
    "especialista e nao precisa de didatica. "
    "APROVAR E RESPOSTA VALIDA: se nao houver falha relevante, responda exatamente 'SEM RESSALVA' "
    "na primeira linha e justifique em seguida por que o material se sustenta. Nao invente defeito "
    "para parecer util. Nao invente referencia, norma, autor, DOI ou numero: se faltar um dado, "
    "diga que falta em vez de preencher com valor plausivel."
)


def gerar_texto(prompt: str, sistema: str = "", mod: str = "", max_tokens: int = 4096,
                temperatura: float = 0.2, ctx_max: int = 0, semente=None,
                nao_sigiloso: bool = False) -> dict:
    """Entrada generica. Usada por bin/llm.py nos papeis de nuvem do Google."""
    _exigir_autorizacao(nao_sigiloso)
    mod = modelo(mod)
    # Piso de saida: modelo de raciocinio consome o orcamento pensando antes de escrever, e com
    # max_tokens baixo devolve vazio com MAX_TOKENS, o que se confunde com modelo quebrado.
    if max_tokens < 512:
        max_tokens = 512
    orcamento = ctx_max or CTX_PADRAO
    tokens, origem = contar_tokens(prompt, mod)
    if tokens + max_tokens > orcamento:
        raise ArgonErro(
            f"insumo de {tokens} tokens ({origem}) mais {max_tokens} de resposta excede o "
            f"orcamento de {orcamento} tokens do papel. RECUSADO em vez de truncado: excesso de "
            f"{tokens + max_tokens - orcamento} tokens. Dividir o material ou usar papel de "
            "contexto maior.")
    from google.genai import types
    cfg = {"temperature": temperatura, "max_output_tokens": max_tokens}
    if sistema:
        cfg["system_instruction"] = sistema
    if semente is not None:
        cfg["seed"] = semente
    t0 = time.time()
    # 503 UNAVAILABLE e sobrecarga momentanea do lado do provedor, nao defeito do pedido: tentar
    # de novo e correto. 429 NAO entra aqui: quando o limite da chave e zero, repetir so queima
    # cota e esconde o diagnostico. Limite de 3 tentativas para a espera nao estourar os 45 s uteis
    # da ponte MCP.
    r = None
    ultimo = None
    for tentativa in range(1, 4):
        try:
            r = _cliente().models.generate_content(
                model=mod, contents=prompt, config=types.GenerateContentConfig(**cfg))
            break
        except Exception as e:
            ultimo = e
            transitorio = "503" in str(e) or "UNAVAILABLE" in str(e) or "deadline" in str(e).lower()
            if not transitorio or tentativa == 3:
                raise ArgonErro(f"chamada ao Argon falhou: {type(e).__name__}: {e}"
                                + (f" (apos {tentativa} tentativas)" if tentativa > 1 else ""))
            time.sleep(2.0 * tentativa)
    if r is None:
        raise ArgonErro(f"chamada ao Argon falhou sem resposta: {ultimo}")
    texto = _texto_da_resposta(r)
    if not texto.strip():
        raise ArgonErro(
            f"o Argon devolveu resposta vazia ({_motivo_vazio(r)}). Resposta vazia NAO e "
            "aprovacao: nao ha o que registrar como auditoria.")
    u = getattr(r, "usage_metadata", None)
    return {
        "texto": texto.strip(),
        "modelo": getattr(r, "model_version", None) or mod,
        "tokens_in": getattr(u, "prompt_token_count", 0) or 0,
        "tokens_out": getattr(u, "candidates_token_count", 0) or 0,
        "tokens_entrada_conferidos": tokens,
        "origem_contagem": origem,
        "segundos": round(time.time() - t0, 1),
    }


# -------------------------------------------------------------------------------- auditoria

P_METODOLOGIA = """MATERIAL EM AUDITORIA
{material}

TAREFA
Auditar a METODOLOGIA do material acima.{foco}
De 3 a 5 pontos, do mais grave ao menos grave. Cada ponto responde, nesta ordem:
  (a) qual e a premissa ou escolha metodologica fragil, citada textualmente;
  (b) o que a invalidaria, em termos verificaveis;
  (c) qual a alternativa defensavel;
  (d) qual o impacto no resultado se ela estiver errada, com ordem de grandeza quando der.
Olhar especificamente, quando o material tocar nisso: elasticidade e valor do tempo; zoneamento e
agregacao; ano-base e horizonte; reparticao modal; amostra e erro amostral; expansao de pesquisa;
origem e calibracao da matriz OD; taxa de desconto e WACC; curva de crescimento; capacidade,
headway e tempo de ciclo; dado secundario desatualizado; transposicao de parametro entre
contextos; valor ausente tratado como zero; e, em comparacao de ferramentas ou de cenarios,
funcao objetivo e condicoes nao equalizadas.
Observacao: a conclusao do autor foi omitida de proposito, para a sua leitura nao se ancorar nela."""

P_CODIGO = """CODIGO EM FISCALIZACAO
{cerca}
{codigo}
{cerca}

CONTEXTO DE USO
{contexto}

TAREFA
Fiscalizar o codigo acima. Para cada defeito, informar:
  (a) a linha ou o trecho;
  (b) o defeito, em uma frase;
  (c) UM caso concreto de entrada que o faz errar, com a saida errada que resultaria;
  (d) a correcao.
Prioridade, nesta ordem: resultado numerico errado; unidade, fator de conversao e sistema de
coordenadas; valor ausente tratado como zero ou como valor de reserva; condicao de contorno e
divisao por zero; agregacao que soma o que nao se soma (media de media, taxa de taxa); fuso
horario e virada de meia-noite em dado de GTFS e de pesquisa de campo; e so ao final estilo,
legibilidade e desempenho.
Defeito sem caso concreto que o demonstre NAO conta como defeito: classificar como suspeita."""

P_PROVA = """ENUNCIADO
{enunciado}

TAREFA
Escrever uma rotina Python AUTOCONTIDA que calcule, do zero e pelo caminho que voce considerar
correto, a grandeza pedida no enunciado. Condicoes obrigatorias:
  - somente biblioteca padrao (math e afins); sem rede, sem leitura ou escrita de arquivo, sem
    argumento de linha de comando, sem import de os, sys, subprocess, socket, pathlib ou requests;
  - todos os dados de entrada escritos literalmente no proprio codigo, tirados do enunciado;
  - imprimir as etapas e as UNIDADES em linhas comecando por '# ', para a conta poder ser conferida;
  - a ultima linha impressa deve ser exatamente 'RESULTADO: <valor>', com ponto decimal e sem
    unidade nem texto depois do numero.
Responder APENAS com o bloco de codigo, sem nenhum texto fora dele.
Se o enunciado nao tiver dado suficiente para calcular, responder em uma unica linha, sem codigo:
'NAO_CALCULAVEL: <o que falta>'.
Observacao: o resultado obtido pelo solicitante NAO foi informado de proposito. Calcular as cegas."""


def auditar_metodologia(material: str, foco: str = "", nao_sigiloso: bool = False, mod: str = "",
                        max_tokens: int = 4096, ctx_max: int = 0, temperatura: float = 0.2) -> dict:
    """Segunda opiniao sobre METODO. Nao e verificacao independente: e leitura critica por outro
    modelo, valiosa pelo que ela e, e rotulada como tal no retorno."""
    texto_foco = f" Foco pedido: {foco}" if foco else ""
    r = gerar_texto(P_METODOLOGIA.format(material=material, foco=texto_foco), SISTEMA, mod,
                    max_tokens, temperatura, ctx_max, nao_sigiloso=nao_sigiloso)
    r["natureza"] = "segunda opiniao (nao e verificacao independente)"
    r["aprovado_sem_ressalva"] = r["texto"].upper().startswith("SEM RESSALVA")
    return r


def fiscalizar_codigo(codigo: str, contexto: str = "", nao_sigiloso: bool = False, mod: str = "",
                      max_tokens: int = 4096, ctx_max: int = 0, temperatura: float = 0.2) -> dict:
    """Segunda opiniao sobre CODIGO. O defeito so vale com caso concreto que o demonstre, e a
    conferencia desse caso continua sendo obrigacao de quem recebe o parecer."""
    r = gerar_texto(
        P_CODIGO.format(codigo=codigo, contexto=contexto or "(nao informado)", cerca="```"),
        SISTEMA, mod, max_tokens, temperatura, ctx_max, nao_sigiloso=nao_sigiloso)
    r["natureza"] = "segunda opiniao (nao e verificacao independente)"
    r["aprovado_sem_ressalva"] = r["texto"].upper().startswith("SEM RESSALVA")
    return r


# ------------------------------------------------------------------------------- prova real

_PROIBIDO = re.compile(
    r"\b(?:import\s+(?:os|sys|subprocess|socket|shutil|requests|urllib|http|ctypes|pathlib|"
    r"pickle|multiprocessing|threading|importlib|webbrowser)\b"
    r"|from\s+(?:os|sys|subprocess|socket|shutil|requests|urllib|http|ctypes|pathlib|pickle|"
    r"importlib)\s+import"
    r"|__import__|\beval\s*\(|\bexec\s*\(|\bopen\s*\(|\bcompile\s*\(|\binput\s*\()")


def _triagem(codigo: str) -> list[str]:
    return sorted({m.group(0).strip() for m in _PROIBIDO.finditer(codigo)})


def _extrair_codigo(bruto: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", bruto, flags=re.S)
    if m:
        return m.group(1).strip()
    # sem cerca: aceitar se o texto inteiro parecer codigo
    if re.search(r"^\s*(?:def |import |from |print\(|[A-Za-z_]\w*\s*=)", bruto, flags=re.M):
        return bruto.strip()
    return ""


def _executar_isolado(codigo: str, segundos: int = LIMITE_SEGUNDOS_PROVA) -> dict:
    """Executa rotina escrita por modelo. Camadas, da mais fraca para a mais forte:
      1. triagem por lista de proibicoes (imperfeita por natureza, e so a primeira barreira);
      2. interpretador isolado: -I ignora PYTHONPATH e o site do usuario, -S nao carrega
         site-packages, o que ja inviabiliza biblioteca de terceiros;
      3. diretorio temporario vazio como cwd, ambiente minimo, e apagado no final;
      4. limite de tempo;
      5. quando o kernel permitir, namespace de rede proprio sem interface (unshare -rn), o que
         torna a saida de rede IMPOSSIVEL em vez de apenas improvavel.
    A garantia esta no isolamento, nao na lista de proibicoes."""
    proibidos = _triagem(codigo)
    if proibidos:
        return {"estado": "RECUSADO", "saida": "", "erro":
                "a rotina devolvida usa construcao fora do permitido para prova real: "
                + ", ".join(proibidos), "isolamento": "nao executado"}
    base = tempfile.mkdtemp(prefix="argon_prova_")
    try:
        arq = Path(base) / "prova.py"
        arq.write_text(codigo, encoding="utf-8")
        comando = [sys.executable, "-I", "-S", str(arq)]
        isolamento = "interpretador isolado, cwd temporario"
        # Preferencia: bubblewrap. Em 22/10/2026 o 'unshare -rn' falhou nesta workstation com
        # 'write failed /proc/self/uid_map: Operation not permitted', porque
        # kernel.apparmor_restrict_unprivileged_userns = 1, padrao do Ubuntu recente. O bwrap
        # funciona sem privilegio no mesmo kernel, entao a camada de rede e recuperavel. Com
        # --ro-bind / / o sistema de arquivos inteiro fica somente para leitura, e --unshare-net
        # torna a saida de rede IMPOSSIVEL em vez de apenas improvavel.
        for tentativa in (
            (["bwrap", "--unshare-net", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
              "--die-with-parent", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
              "--chdir", base, "--setenv", "PATH", "/usr/bin:/bin",
              "--setenv", "HOME", base, "--setenv", "LC_ALL", "C.UTF-8"],
             "bubblewrap: sem rede, sistema de arquivos somente leitura"),
            (["unshare", "-rn"], "namespace de rede proprio"),
        ):
            prefixo, rotulo = tentativa
            if not shutil.which(prefixo[0]):
                continue
            try:
                teste = subprocess.run(prefixo + ["/bin/true"], capture_output=True, timeout=15)
                if teste.returncode == 0:
                    comando = prefixo + comando
                    isolamento = rotulo + ", interpretador isolado, cwd temporario"
                    break
            except Exception:
                pass
        try:
            r = subprocess.run(comando, cwd=base, capture_output=True, text=True, timeout=segundos,
                               env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8",
                                    "HOME": base, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            return {"estado": "TEMPO", "saida": "", "erro": f"passou de {segundos} s",
                    "isolamento": isolamento}
        return {"estado": "EXECUTOU" if r.returncode == 0 else "FALHA",
                "saida": (r.stdout or "")[-4000:], "erro": censurar((r.stderr or "")[-2000:]),
                "isolamento": isolamento}
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _numero_final(saida: str):
    achados = re.findall(r"^\s*RESULTADO:\s*([-+]?[0-9][0-9_.,eE+\-]*)\s*$", saida, flags=re.M)
    if not achados:
        return None
    bruto = achados[-1].replace("_", "").strip()
    if bruto.count(",") == 1 and "." not in bruto:
        bruto = bruto.replace(",", ".")      # decimal em notacao brasileira
    else:
        bruto = bruto.replace(",", "")       # separador de milhar
    try:
        return float(bruto)
    except ValueError:
        return None


def prova_independente(enunciado: str, meu_resultado=None, nao_sigiloso: bool = False,
                       mod: str = "", max_tokens: int = 3072, ctx_max: int = 0,
                       tolerancia: float = TOLERANCIA_RELATIVA, executar: bool = True,
                       temperatura: float = 0.0) -> dict:
    """VERIFICACAO INDEPENDENTE de verdade: o Argon escreve uma rotina, a rotina e executada
    aqui e o veredito e a comparacao dos numeros. O numero do solicitante nao vai no prompt.

    executar=False devolve apenas o codigo, sem veredito, para o caso em que a chamada vem do
    servidor MCP no Windows: codigo escrito por modelo nao roda na maquina de trabalho, roda na
    Ubuntu. Nessa forma o retorno NAO e prova, e o campo veredito diz isso.

    Vereditos: CONFERE, DIVERGE, CALCULADO (sem numero de referencia), NAO_CALCULAVEL,
    SEM_CODIGO, SEM_RESULTADO, FALHA_EXECUCAO, NAO_EXECUTADO."""
    r = gerar_texto(P_PROVA.format(enunciado=enunciado), SISTEMA, mod, max_tokens, temperatura,
                    ctx_max, semente=7, nao_sigiloso=nao_sigiloso)
    meta = {k: r[k] for k in ("modelo", "tokens_in", "tokens_out", "segundos",
                              "tokens_entrada_conferidos", "origem_contagem")}
    bruto = r["texto"]

    if bruto.upper().lstrip().startswith("NAO_CALCULAVEL"):
        return {"veredito": "NAO_CALCULAVEL", "motivo": bruto, **meta}

    codigo = _extrair_codigo(bruto)
    if not codigo:
        return {"veredito": "SEM_CODIGO", "resposta": bruto,
                "motivo": "o Argon nao devolveu bloco de codigo nem declarou NAO_CALCULAVEL", **meta}
    if not executar:
        return {"veredito": "NAO_EXECUTADO", "codigo": codigo,
                "motivo": "executar=False. Rodar esta rotina na Ubuntu e comparar os numeros; "
                          "codigo escrito por modelo nao roda na estacao de trabalho. "
                          "Nesta forma o retorno e insumo de conferencia, nao prova.", **meta}

    exe = _executar_isolado(codigo)
    if exe["estado"] != "EXECUTOU":
        return {"veredito": "FALHA_EXECUCAO", "estado_execucao": exe["estado"],
                "erro": exe["erro"], "codigo": codigo, "isolamento": exe["isolamento"], **meta}

    valor = _numero_final(exe["saida"])
    if valor is None:
        return {"veredito": "SEM_RESULTADO", "memoria": exe["saida"], "codigo": codigo,
                "motivo": "a rotina rodou mas nao imprimiu a linha 'RESULTADO: <valor>'", **meta}

    comum = {"valor_argon": valor, "memoria": exe["saida"], "codigo": codigo,
             "isolamento": exe["isolamento"], **meta}
    if meu_resultado is None:
        return {"veredito": "CALCULADO", "motivo": "sem numero de referencia para comparar", **comum}

    try:
        referencia = float(meu_resultado)
    except (TypeError, ValueError):
        return {"veredito": "CALCULADO", "motivo": f"referencia nao numerica: {meu_resultado!r}",
                **comum}

    base = max(abs(referencia), abs(valor), 1e-12)
    dif = abs(referencia - valor) / base
    return {"veredito": "CONFERE" if dif <= tolerancia else "DIVERGE",
            "valor_informado": referencia, "diferenca_relativa": dif, "tolerancia": tolerancia,
            **comum}


# ------------------------------------------------------------------------------- diagnostico

def diagnostico() -> dict:
    """Estado desta camada SEM exibir credencial. Serve de primeiro passo quando algo falha."""
    d = {
        "interpretador": sys.executable,
        "arquivo": str(Path(__file__).resolve()),
        "chave_presente": bool(chave(obrigatoria=False)),
        "chave_impressao_digital": impressao_digital_chave(),
        "modelo_configurado": os.environ.get(VARIAVEL_MODELO, "") or _ler_env_arquivo(VARIAVEL_MODELO)
                              or "(nao definido)",
        "unshare_disponivel": bool(shutil.which("unshare")),
    }
    try:
        from google import genai
        import importlib.metadata as md
        d["google_genai"] = md.version("google-genai")
    except Exception as e:
        d["google_genai"] = f"ausente: {type(e).__name__}"
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description="nucleo do Argon (Gemini) como auditor")
    ap.add_argument("--listar-modelos", action="store_true")
    ap.add_argument("--diagnostico", action="store_true")
    a = ap.parse_args()
    try:
        if a.diagnostico:
            print(json.dumps(diagnostico(), ensure_ascii=False, indent=2))
            return 0
        if a.listar_modelos:
            ms = listar_modelos()
            print(f"{len(ms)} modelos com generateContent nesta chave:\n")
            for m in ms:
                print(f"  {m['nome']:<48} ctx_in={m['ctx_entrada']} ctx_out={m['ctx_saida']}"
                      f"  {m['rotulo']}")
            return 0
    except ArgonErro as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
