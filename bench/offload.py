#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""offload.py - mede o custo real de um modelo que nao cabe inteiro na VRAM.

  offload.py --modelos qwen2.5:14b,qwen3:30b-a3b --ctx 32768 [--tokens-doc 20000]

Para cada modelo: tokens/s de leitura do documento (prefill), tokens/s de geracao,
tempo total e a divisao GPU/CPU informada pelo Ollama. O prefill e o que domina
revisao de documento longo; a geracao domina resposta curta.
"""
import argparse, random, re, subprocess, time
import requests

OLLAMA = "http://localhost:11434"


def documento(tokens_alvo):
    random.seed(5)
    temas = ["frota", "tarifa", "demanda", "headway", "terminal", "garagem", "bilhetagem", "subsidio", "corredor"]
    linhas = []
    while len(" ".join(linhas)) < tokens_alvo * 3.6:
        i = len(linhas) + 1
        linhas.append(f"Item {i}: a {random.choice(temas)} do lote {random.randint(1, 9)} sera revista em "
                      f"{random.randint(2027, 2035)} conforme o anexo {random.choice('ABCDEFG')}.")
    return "\n".join(linhas)


def divisao_gpu(modelo):
    s = subprocess.run("ollama ps", shell=True, capture_output=True, text=True).stdout
    for l in s.splitlines():
        if l.startswith(modelo.split(":")[0]):
            m = re.search(r"(\d+%/?\d*%?\s*(?:CPU/GPU|GPU|CPU))", l)
            return m.group(1) if m else "?"
    return "nao carregado"


def medir(modelo, ctx, tokens_doc, saida=128):
    doc = documento(tokens_doc)
    prompt = f"=== CONTEUDO ===\n{doc}\n=== FIM DO CONTEUDO ===\n\nTAREFA: resuma em uma frase o tipo de documento acima."
    t0 = time.time()
    r = requests.post(f"{OLLAMA}/api/generate", timeout=3600, json={
        "model": modelo, "prompt": prompt, "stream": False, "keep_alive": "5m", "think": False,
        "options": {"num_ctx": ctx, "num_predict": saida, "temperature": 0}}).json()
    if r.get("error"):
        r2 = requests.post(f"{OLLAMA}/api/generate", timeout=3600, json={
            "model": modelo, "prompt": prompt, "stream": False, "keep_alive": "5m",
            "options": {"num_ctx": ctx, "num_predict": saida, "temperature": 0}}).json()
        if r2.get("error"):
            return {"modelo": modelo, "erro": str(r.get("error"))[:120]}
        r = r2
    ns = 1e9
    pe, pd = r.get("prompt_eval_count", 0), r.get("prompt_eval_duration", 1) / ns
    ev, ed = r.get("eval_count", 0), r.get("eval_duration", 1) / ns
    return {"modelo": modelo, "ctx": ctx, "tokens_lidos": pe, "prefill_tps": pe / pd if pd else 0,
            "tokens_gerados": ev, "geracao_tps": ev / ed if ed else 0,
            "carga_s": r.get("load_duration", 0) / ns, "total_s": time.time() - t0, "divisao": divisao_gpu(modelo)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", required=True); ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--tokens-doc", type=int, default=20000)
    a = ap.parse_args()
    print(f"{'MODELO':22} {'CTX':>6} {'LIDOS':>7} {'PREFILL':>10} {'GERACAO':>9} {'CARGA':>7} {'TOTAL':>7}  DIVISAO")
    for m in a.modelos.split(","):
        d = medir(m, a.ctx, a.tokens_doc)
        if d.get("erro"):
            print(f"{m:22} ERRO: {d['erro']}"); continue
        print(f"{d['modelo']:22} {d['ctx']:6} {d['tokens_lidos']:7} {d['prefill_tps']:8.1f}/s {d['geracao_tps']:7.1f}/s "
              f"{d['carga_s']:6.1f}s {d['total_s']:6.1f}s  {d['divisao']}", flush=True)
