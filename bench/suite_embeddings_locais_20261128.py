#!/home/mateus/env_nemotron_vl/bin/python
# -*- coding: utf-8 -*-
"""Suite `embeddings` do bench.py (12 trechos, 10 consultas) no braco B da rodada local de
28/11/2026: google/embeddinggemma-2 contra qwen3-embedding:4b.

Roda no ambiente ~/env_nemotron_vl porque e o unico com transformers 5.22.2 e
sentence-transformers 6.3.0, que conhecem a arquitetura EmbeddingGemma2Model. O ambiente e USADO,
nao alterado: nada e instalado nele. Os TRECHOS, as CONSULTAS e o alvo de cada consulta vem
IMPORTADOS de bench.py, nao copiados.

Por que nao `bench.py --suite embeddings`: a suite_embeddings do bench.py consulta
`POST /api/embed` do Ollama, e o Ollama 0.34.0 nao roda o embeddinggemma-2 (requires 0.40.4 no
registro oficial). O caminho do titular continua sendo exatamente o do bench.py.

Grava bench/resultados/20261128_locais_B_suite_embeddings.jsonl, uma linha por consulta e passada.
Uso: suite_embeddings_locais_20261128.py [--passadas 3]
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", "/mnt/nvme_lexar/hf_cache_20261128")

import requests                                      # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "bin"))
sys.path.insert(0, str(RAIZ / "bench"))
import llm      # noqa: E402
import bench    # noqa: E402

SAIDA = RAIZ / "bench" / "resultados" / "20261128_locais_B_suite_embeddings.jsonl"
HF = "google/embeddinggemma-2"
REVISAO = "f9972ac22e696a105c482202646979e33e4b5a1e"
OLLAMA_EMB = "qwen3-embedding:4b"
_cache_hf = {}


def cos(a, b):
    return (sum(x * y for x, y in zip(a, b))
            / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))))


def emb_ollama(textos, **_):
    """Identico ao caminho da suite_embeddings do bench.py: sem prefixo de tarefa, que e como o
    titular roda na producao."""
    r = requests.post(f"{llm.OLLAMA}/api/embed",
                      json={"model": OLLAMA_EMB, "input": textos, "keep_alive": "30m"},
                      timeout=300).json()
    if r.get("error"):
        raise RuntimeError(r["error"][:160])
    return r["embeddings"]


def emb_hf(textos, prompt_name=None):
    if "m" not in _cache_hf:
        import torch
        from sentence_transformers import SentenceTransformer
        _cache_hf["m"] = SentenceTransformer(HF, revision=REVISAO, device="cuda")
        _cache_hf["torch"] = torch
    return _cache_hf["m"].encode(textos, prompt_name=prompt_name,
                                 show_progress_bar=False).tolist()


# Dois bracos do embeddinggemma-2, os MESMOS pares de prefixo declarados no ADENDO 01 ao
# pre-registro, antes de medir. O titular nao leva prefixo, porque sem prefixo e como ele roda.
BRACOS = [
    ("qwen3-embedding:4b", emb_ollama, None, None, "Ollama (sem prefixo de tarefa)"),
    ("embeddinggemma-2 (query/document)", emb_hf, "query", "document",
     "sentence-transformers, pesos do fabricante"),
    ("embeddinggemma-2 (QuestionAnswering/Document)", emb_hf, "QuestionAnswering", "Document",
     "sentence-transformers, pesos do fabricante"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passadas", type=int, default=3)
    a = ap.parse_args()
    for nome, f, p_q, p_d, runtime in BRACOS:
        for passada in range(1, a.passadas + 1):
            t0 = time.time()
            try:
                E = f(bench.TRECHOS, prompt_name=p_d)
                Q = f([q for q, _ in bench.CONSULTAS], prompt_name=p_q)
            except Exception as e:
                print(f"  {nome:<48} p{passada} ERRO {type(e).__name__}: {e}", flush=True)
                continue
            seg = time.time() - t0
            linhas = []
            for (q, alvo), vq in zip(bench.CONSULTAS, Q):
                ordem = sorted(range(len(E)), key=lambda i: -cos(vq, E[i]))
                linhas.append({"braco": "B", "suite": "embeddings_bench", "passada": passada,
                               "modelo": nome, "runtime": runtime,
                               "prompt_consulta": p_q, "prompt_documento": p_d,
                               "tarefa": f"q{alvo:02d}", "ok": ordem[0] == alvo,
                               "posicao_do_trecho_certo": ordem.index(alvo) + 1,
                               "dim": len(vq),
                               "seg_total_da_passada": round(seg, 2)})
            with SAIDA.open("a", encoding="utf-8") as fh:
                for x in linhas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")
            print(f"  {nome:<48} p{passada} {sum(x['ok'] for x in linhas)}/{len(linhas)}  "
                  f"dim {len(Q[0])}  {seg:.1f}s  posicoes="
                  f"{[x['posicao_do_trecho_certo'] for x in linhas]}", flush=True)
    print(f"\ngravado em {SAIDA}", flush=True)


if __name__ == "__main__":
    main()
