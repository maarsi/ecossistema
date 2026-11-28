#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Suite `embeddings` do bench.py (12 trechos, 10 consultas) pela via OLLAMA 0.40.19.

Irma do suite_embeddings_locais_20261128.py, que mediu o embeddinggemma-2 por
`sentence-transformers` porque o Ollama 0.34.0 nao o rodava. Com o 0.40.19 os tres embedders rodam
no MESMO runtime, o que remove a desigualdade de condicao que o pre-registro teve de declarar:
aqui runtime, maquina, sessao, lote e quantizacao de servico sao os mesmos para candidato e
titular. Esta e a medicao principal; a outra fica como segundo caminho.

Tres bracos:
  embeddinggemma-2:740m  prefixos query/document do cartao
  embeddinggemma-2:270m  os mesmos prefixos
  qwen3-embedding:4b     sem prefixo, que e como o titular roda na producao do acervo

Os TRECHOS, as CONSULTAS e o alvo de cada consulta vem IMPORTADOS de bench.py, nao copiados.
Grava bench/resultados/20261128_locais_B_suite_embeddings_ollama.jsonl.
Uso: suite_embeddings_ollama_20261128.py [--passadas 3]
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "bin"))
sys.path.insert(0, str(RAIZ / "bench"))
import llm      # noqa: E402
import bench    # noqa: E402

SAIDA = RAIZ / "bench" / "resultados" / "20261128_locais_B_suite_embeddings_ollama.jsonl"
VERSAO = subprocess.run(["ollama", "--version"], capture_output=True,
                        text=True).stdout.strip().split()[-1]
PC = "task: search result | query: "      # cadeias do config_sentence_transformers.json dos pesos
PD = "title: none | text: "

BRACOS = [("embeddinggemma-2:740m", PC, PD), ("embeddinggemma-2:270m", PC, PD),
          ("qwen3-embedding:4b", "", "")]


def cos(a, b):
    return (sum(x * y for x, y in zip(a, b))
            / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))))


def emb(modelo, textos, prefixo):
    r = requests.post(f"{llm.OLLAMA}/api/embed",
                      json={"model": modelo, "input": [prefixo + t for t in textos],
                            "keep_alive": "30m"}, timeout=900).json()
    if r.get("error"):
        raise RuntimeError(str(r["error"])[:200])
    return r["embeddings"]


def digest(modelo):
    o = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
    return next((l.split()[1] for l in o.splitlines() if l.startswith(modelo + " ")), "?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passadas", type=int, default=3)
    a = ap.parse_args()
    for modelo, p_q, p_d in BRACOS:
        dg = digest(modelo)
        for passada in range(1, a.passadas + 1):
            t0 = time.time()
            try:
                E = emb(modelo, bench.TRECHOS, p_d)
                Q = emb(modelo, [q for q, _ in bench.CONSULTAS], p_q)
            except Exception as e:
                print(f"  {modelo:<26} p{passada} ERRO {type(e).__name__}: {e}", flush=True)
                continue
            seg = time.time() - t0
            linhas = []
            for (q, alvo), vq in zip(bench.CONSULTAS, Q):
                ordem = sorted(range(len(E)), key=lambda i: -cos(vq, E[i]))
                linhas.append({"braco": "B", "suite": "embeddings_bench", "passada": passada,
                               "modelo": modelo, "pesos": dg, "runtime": f"Ollama {VERSAO}",
                               "ollama": VERSAO, "prompt_consulta": p_q or None,
                               "prompt_documento": p_d or None,
                               "tarefa": f"q{alvo:02d}", "ok": ordem[0] == alvo,
                               "posicao_do_trecho_certo": ordem.index(alvo) + 1,
                               "dim": len(vq), "seg_total_da_passada": round(seg, 2)})
            with SAIDA.open("a", encoding="utf-8") as fh:
                for x in linhas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")
            print(f"  {modelo:<26} p{passada} {sum(x['ok'] for x in linhas)}/{len(linhas)}  "
                  f"dim {len(Q[0])}  {seg:.1f}s  ollama {VERSAO}  posicoes="
                  f"{[x['posicao_do_trecho_certo'] for x in linhas]}", flush=True)
        requests.post(f"{llm.OLLAMA}/api/embed",
                      json={"model": modelo, "input": ["x"], "keep_alive": 0}, timeout=300)
    print(f"\ngravado em {SAIDA}", flush=True)


if __name__ == "__main__":
    main()
