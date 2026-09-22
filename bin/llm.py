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
DEGRAUS_CTX = [4096, 8192, 16384, 32768, 65536, 131072]
# Estimativa PESSIMISTA de tokens (limite superior plausivel para portugues com numeros e acentos).
# Motivo: quando o prompt excede num_ctx, o Ollama descarta ~metade do contexto e guarda o FINAL,
# e o prompt_eval_count devolvido nao permite detectar isso de forma confiavel. Logo, prevenir.
CHARS_POR_TOKEN = 2.5
FORMATOS_TEXTO = {".txt", ".md", ".csv", ".json", ".tsv", ".xml", ".html"}


def estimar_tokens(txt):
    return int(len(txt) / CHARS_POR_TOKEN) + 1


def chave_nvidia():
    if os.environ.get("NVIDIA_API_KEY"):
        return os.environ["NVIDIA_API_KEY"]
    for p in [RAIZ / ".env", Path.home() / "TransportMCP" / ".env"]:
        if p.exists():
            for l in p.read_text(encoding="utf-8").splitlines():
                if l.startswith("NVIDIA_API_KEY="):
                    return l.split("=", 1)[1].strip().strip('"')
    sys.exit("ERRO: NVIDIA_API_KEY nao encontrada (ambiente, ~/ecossistema/.env ou ~/TransportMCP/.env).")


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


def chamar_local(modelo, prompt, ctx, max_tokens, temperatura):
    r = requests.post(f"{OLLAMA}/api/generate", timeout=1800, json={
        "model": modelo, "prompt": prompt, "stream": False, "keep_alive": "30m",
        "options": {"num_ctx": ctx, "num_predict": max_tokens, "temperature": temperatura}})
    r.raise_for_status()
    d = r.json()
    return d.get("response", ""), d.get("prompt_eval_count", 0), d.get("eval_count", 0)


def chamar_nuvem(modelo, prompt, max_tokens, temperatura):
    r = requests.post(NVIDIA, timeout=300, headers={"Authorization": f"Bearer {chave_nvidia()}"},
                      json={"model": modelo, "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens, "temperature": temperatura})
    if r.status_code != 200:
        sys.exit(f"ERRO nuvem HTTP {r.status_code} em {modelo}. Tentar outro papel de nuvem.")
    d = r.json()
    u = d.get("usage", {})
    return d["choices"][0]["message"].get("content") or "", u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


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
    ap.add_argument("--ctx", type=int, default=16384, help="num_ctx fixo para --modelo")
    ap.add_argument("--consolidar", choices=["concatenar", "llm"], default="concatenar",
                    help="modo partes: concatenar (extracao, deterministico) ou llm (sintese/resumo)")
    ap.add_argument("--manter-raciocinio", action="store_true")
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
    max_tokens = a.max_tokens or cfg.get("max_tokens", 2048)

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
        sys.exit("ERRO: informar --instrucao e/ou conteudo.")

    t0 = time.time()
    if cfg["onde"] == "nuvem":
        if not a.nuvem:
            sys.exit("ERRO: papel de NUVEM exige --nuvem explicito. O conteudo sai da workstation: "
                     "nao usar com dado de cliente, pesquisa bruta ou material sob NDA.")
        prompt = montar_prompt(instrucao, conteudo)
        texto, tin, tout = chamar_nuvem(cfg["modelo"], prompt, max_tokens, a.temperatura)
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
