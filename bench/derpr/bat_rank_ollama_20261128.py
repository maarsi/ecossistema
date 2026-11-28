#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Braco B da rodada LOCAL de 28/11/2026, via OLLAMA 0.40.19.

Depois que o Mateus atualizou o Ollama de 0.34.0 para 0.40.19 (14h10 de 28/11), o
`embeddinggemma-2` passou a ser servido pelo proprio Ollama, que era o caminho pedido na
especificacao e que o portao de versao do registro barrava (`requires: 0.40.4`). A medicao por
`sentence-transformers`, ja feita as 13:49, continua valendo como SEGUNDO CAMINHO; esta aqui e a
principal.

Tres bracos novos, todos sobre o MESMO texto do braco vencedor (B do ADENDO_07, Docling com OCR,
`derpr/textos/B_p{1,2,3}.json`, inalterado desde 12/11), mesmo chunking (uma pagina por vetor, 58
paginas), mesmo corte de 8000 caracteres, mesma normalizacao L2, mesmo produto interno, mesmas 30
perguntas. SO MUDA O EMBEDDER:

  P  embeddinggemma-2:740m  pelo Ollama, prefixos query/document do cartao
  Q  embeddinggemma-2:270m  pelo Ollama, os mesmos prefixos
  R  qwen3-embedding:4b     pelo Ollama, SEM prefixo (titular, remedido em 0.40.19)

Por que o titular e remedido: a ATUALIZACAO DO AMBIENTE manda que toda medicao desta rodada,
inclusive a das referencias, saia em 0.40.19. O braco B publicado no ADENDO_07 foi medido em outra
versao e serve de historico, nao de lado da comparacao.

Por que o titular vai SEM prefixo: e como ele roda na producao do acervo (`bat_rank_texto.py`).
Acrescentar prefixo a ele mudaria o titular medido. A assimetria e de projeto dos dois modelos e
esta registrada no ADENDO 01 ao pre-registro.

Os prefixos sao aplicados AQUI, com as cadeias exatas do `config_sentence_transformers.json` dos
pesos do fabricante, porque o `/api/embed` do Ollama nao os aplica sozinho. Isso mantem a via
Ollama comparavel com a via sentence-transformers, onde o `prompt_name` fazia o mesmo.

Grava derpr/rank/<braco>_p<passada>.json, no formato que o pontuador ja le.
Uso: bat_rank_ollama_20261128.py <passada> <braco P|Q|R>
"""
import json
import pathlib
import subprocess
import sys
import time

import numpy as np
import requests

B = pathlib.Path.home() / "ecossistema/bench"
URL = "http://localhost:11434/api/embed"

# Cadeias lidas do cartao dos pesos do fabricante (snapshot f9972ac2), nao digitadas de memoria.
PREFIXO_CONSULTA = "task: search result | query: "
PREFIXO_DOCUMENTO = "title: none | text: "

BRACOS = {
    "P": ("embeddinggemma-2:740m", PREFIXO_CONSULTA, PREFIXO_DOCUMENTO, "query", "document"),
    "Q": ("embeddinggemma-2:270m", PREFIXO_CONSULTA, PREFIXO_DOCUMENTO, "query", "document"),
    "R": ("qwen3-embedding:4b", "", "", None, None),
}

passada = sys.argv[1]
braco = sys.argv[2]
if braco not in BRACOS:
    sys.exit(f"braco desconhecido: {braco} (so P, Q ou R)")
MOD, PC, PD, NC, ND = BRACOS[braco]

versao = subprocess.run(["ollama", "--version"], capture_output=True, text=True).stdout.strip().split()[-1]
digest = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
digest = next((l.split()[1] for l in digest.splitlines() if l.startswith(MOD + " ")), "?")

perg = {p["id"]: p["texto"] for p in json.loads(
    (B / "suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}

alvo = B / f"derpr/rank/{braco}_p{passada}.json"
if alvo.exists():
    sys.exit(f"  braco {braco} passada {passada}: ja existe, nao sobrescrevo")


def vram_mb():
    o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True).stdout.strip().splitlines()
    return int(o[0]) if o else 0


def emb(textos, prefixo, lote=8):
    """Mesmo lote, mesmo corte de 8000 caracteres e mesma troca de texto vazio por um espaco que
    bat_rank_texto.py usa, para que o unico efeito medido seja o do embedder."""
    v = []
    for i in range(0, len(textos), lote):
        pedaco = [prefixo + (t[:8000] if t.strip() else " ") for t in textos[i:i + lote]]
        r = requests.post(URL, json={"model": MOD, "input": pedaco, "keep_alive": "30m"},
                          timeout=900)
        r.raise_for_status()
        d = r.json()
        if d.get("error"):
            sys.exit(f"erro do Ollama em {MOD}: {d['error'][:300]}")
        v.extend(d["embeddings"])
    a = np.array(v, dtype=np.float32)
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)


base = vram_mb()
t0 = time.time()
Q = emb([perg[k] for k in sorted(perg)], PC)
seg_consulta = time.time() - t0

txt = json.loads((B / f"derpr/textos/B_p{passada}.json").read_text())
t1 = time.time()
Pv = emb([txt.get(str(i), "") for i in range(1, 59)], PD)
seg_indexacao = time.time() - t1
pico = vram_mb()

ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
proc = next((" ".join(l.split()[3:5]) for l in ps.splitlines() if l.startswith(MOD + " ")), None)

S = Q @ Pv.T                                        # 30 x 58
rank = {qid: (np.argsort(-S[i]) + 1).tolist() for i, qid in enumerate(sorted(perg))}
alvo.write_text(json.dumps(
    {"braco": braco, "passada": int(passada), "rank": rank,
     "embedder": MOD, "digest": digest, "runtime": f"Ollama {versao}", "ollama": versao,
     "texto_de_origem": f"derpr/textos/B_p{passada}.json (Docling com OCR, braco B do ADENDO_07)",
     "prompt_nome_consulta": NC, "prompt_nome_documento": ND,
     "prompt_consulta": PC or None, "prompt_documento": PD or None,
     "bytes_indice": int(Pv.nbytes), "dim": int(Pv.shape[1]), "vetores_por_pagina": 1,
     "seg_consulta": round(seg_consulta, 2), "seg_indexacao": round(seg_indexacao, 2),
     "vram_base_MB": base, "vram_pico_MB": pico, "processador_ollama_ps": proc},
    ensure_ascii=False))
print(f"  braco {braco} p{passada}: {MOD} ({digest}) dim {Pv.shape[1]}, "
      f"indexacao {seg_indexacao:.1f}s, consulta {seg_consulta:.1f}s, "
      f"VRAM {base}->{pico} MB, proc {proc}, ollama {versao}", flush=True)
