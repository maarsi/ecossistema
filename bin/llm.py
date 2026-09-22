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
CHARS_POR_TOKEN = 4.0  # estimativa central; a decisao final usa a contagem real devolvida pelo Ollama
FOLGA_ESTIMATIVA = 1.6  # insumo estimado ate 1,6x o ctx_max ainda e tentado (a estimativa pode exagerar)
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
    """Tenta no contexto estimado; se o Ollama sinalizar truncamento, sobe de degrau ate ctx_max.
    Retorna (None, estimativa) quando o insumo real nao cabe no ctx_max do papel."""
    prompt = f"{instrucao}\n\n=== CONTEUDO ===\n{conteudo}" if conteudo else instrucao
    est = estimar_tokens(prompt)
    if est > FOLGA_ESTIMATIVA * cfg["ctx_max"]:
        return None, est
    ctx = escolher_ctx(est, max_tokens, cfg["ctx_max"]) or cfg["ctx_max"]
    t = time.time()
    while True:
        resp, tin, tout = chamar_local(cfg["modelo"], prompt, ctx, max_tokens, temperatura)
        truncou = tin >= 0.95 * ctx
        if not truncou:
            return {"texto": resp, "tin": tin, "tout": tout, "ctx": ctx, "seg": time.time() - t}, est
        if ctx >= cfg["ctx_max"]:
            print(f"[llm] insumo real excede ctx_max {cfg['ctx_max']} (Ollama leu {tin} tokens e truncou)", file=sys.stderr)
            return None, max(est, tin)
        prox = escolher_ctx(int(tin * 1.3), max_tokens, cfg["ctx_max"]) or cfg["ctx_max"]
        print(f"[llm] truncamento detectado em num_ctx {ctx}; nova tentativa com {prox}", file=sys.stderr)
        ctx = max(prox, ctx * 2) if prox <= ctx else prox
        ctx = min(ctx, cfg["ctx_max"])


def main():
    ap = argparse.ArgumentParser(description="Gateway de modelos do ecossistema")
    ap.add_argument("--papel"); ap.add_argument("--listar", action="store_true")
    ap.add_argument("--instrucao", default=""); ap.add_argument("--texto"); ap.add_argument("--arquivo")
    ap.add_argument("--saida"); ap.add_argument("--partes", action="store_true")
    ap.add_argument("--nuvem", action="store_true"); ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--temperatura", type=float, default=0.2)
    ap.add_argument("--manter-raciocinio", action="store_true")
    a = ap.parse_args()

    if a.listar or not a.papel:
        print(f"{'PAPEL':22} {'ONDE':6} {'MODELO':46} {'CTX':>7}  USO")
        for n, c in PAPEIS.items():
            print(f"{n:22} {c['onde']:6} {c['modelo']:46} {str(c.get('ctx_max', '-')):>7}  {c['uso']}")
        return
    if a.papel not in PAPEIS:
        sys.exit(f"ERRO: papel '{a.papel}' inexistente. Use --listar.")
    cfg = PAPEIS[a.papel]
    max_tokens = a.max_tokens or cfg.get("max_tokens", 2048)

    conteudo = ""
    if a.arquivo:
        p = Path(a.arquivo)
        if p.suffix.lower() not in FORMATOS_TEXTO:
            sys.exit(f"ERRO: formato {p.suffix} nao suportado direto. Converter antes para .md (PDF/DOCX via Docling).")
        conteudo = p.read_text(encoding="utf-8", errors="replace")
    elif a.texto == "-":
        conteudo = sys.stdin.read()
    elif a.texto:
        conteudo = a.texto
    instrucao = a.instrucao or ("" if conteudo else sys.exit("ERRO: informar --instrucao e/ou conteudo."))

    t0 = time.time()
    if cfg["onde"] == "nuvem":
        if not a.nuvem:
            sys.exit("ERRO: papel de NUVEM exige --nuvem explicito. O conteudo sai da workstation: "
                     "nao usar com dado de cliente, pesquisa bruta ou material sob NDA.")
        prompt = f"{instrucao}\n\n=== CONTEUDO ===\n{conteudo}" if conteudo else instrucao
        texto, tin, tout = chamar_nuvem(cfg["modelo"], prompt, max_tokens, a.temperatura)
        modo = "nuvem"
    else:
        res, est = executar_local(cfg, instrucao, conteudo, max_tokens, a.temperatura)
        modo = "local"
        if res is None:
            if not a.partes:
                sys.exit(f"ERRO: insumo de ~{est} tokens excede ctx_max {cfg['ctx_max']} do papel '{a.papel}'. "
                         f"Usar --partes (divide e consolida) ou papel de nuvem se o material nao for sigiloso.")
            orc = cfg["ctx_max"] - max_tokens - estimar_tokens(instrucao) - 768
            blocos = dividir(conteudo, orc)
            print(f"[llm] modo partes: {len(blocos)} blocos de ate ~{orc} tokens", file=sys.stderr)
            parciais, tin, tout = [], 0, 0
            for i, b in enumerate(blocos, 1):
                r, _ = executar_local(cfg, f"{instrucao}\n(Parte {i} de {len(blocos)} do documento. "
                                           f"Responder apenas com base nesta parte.)", b, max_tokens, a.temperatura)
                parciais.append(f"--- PARTE {i} ---\n{limpar_raciocinio(r['texto'])}")
                tin += r["tin"]; tout += r["tout"]
            final, _ = executar_local(cfg, "Consolidar as respostas parciais abaixo em resposta unica, sem repeticao, "
                                           f"preservando todos os itens. Instrucao original: {instrucao}",
                                      "\n\n".join(parciais), max_tokens, a.temperatura)
            if final is None:
                texto = "[consolidacao excedeu o contexto; seguem as respostas parciais]\n\n" + "\n\n".join(parciais)
            else:
                texto = final["texto"]; tin += final["tin"]; tout += final["tout"]
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
