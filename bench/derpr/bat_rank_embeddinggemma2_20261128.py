#!/home/mateus/env_nemotron_vl/bin/python
# -*- coding: utf-8 -*-
"""Braco L da suite de recuperacao do Anuario DER-PR: o MESMO texto do braco vencedor (B, Docling
com OCR) indexado e consultado por OUTRO embedder, o google/embeddinggemma-2.

Desenho copiado de bat_rank_texto.py item por item, de proposito: mesmo arquivo de texto
(derpr/textos/B_p{1,2,3}.json, inalterado desde 12/11), mesmo chunking (uma pagina por vetor, 58
paginas), mesmas 30 perguntas da suite, mesmo corte de 8000 caracteres por pagina, mesma
normalizacao L2 e mesmo produto interno. A UNICA variavel e o embedder.

Por que fora do Ollama: a tag `embeddinggemma-2` declara `requires: 0.40.4` no registro oficial e
o Ollama instalado e o 0.34.0, que a especificacao desta tarefa proibe atualizar. Os pesos vem do
repositorio do fabricante (google/embeddinggemma-2, apache-2.0, nao restrito) e rodam no
sentence-transformers 6.3.0 que JA existe em ~/env_nemotron_vl. Nada e instalado nesse ambiente.

O embeddinggemma-2 e um modelo com PREFIXO DE TAREFA: consulta e documento recebem instrucoes
diferentes, pelos prompts declarados no proprio cartao. Usar o mesmo prefixo nos dois lados seria
medir o modelo errado de proposito; os prompts usados ficam gravados no arquivo de saida.

Dois pares de prompt sao medidos, os DOIS declarados no ADENDO 01 ao pre-registro ANTES de rodar,
para que a escolha nao seja feita depois de ver o numero:
  braco L (principal)     query / document            -> "task: search result | query: " e
                                                          "title: none | text: "
  braco N (exploratorio)  QuestionAnswering / Document -> "task: question answering | query: " e
                                                          "title: none | text: "

Grava derpr/rank/<braco>_p<passada>.json, no mesmo formato que o pontuador ja le.
Uso: bat_rank_embeddinggemma2_20261128.py <passada> [braco]   (braco L, padrao, ou N)
"""
import json
import os
import pathlib
import sys
import time

os.environ.setdefault("HF_HOME", "/mnt/nvme_lexar/hf_cache_20261128")

import numpy as np                                  # noqa: E402
import torch                                        # noqa: E402
from sentence_transformers import SentenceTransformer   # noqa: E402

B = pathlib.Path.home() / "ecossistema/bench"
MOD = "google/embeddinggemma-2"
REVISAO = "f9972ac22e696a105c482202646979e33e4b5a1e"   # commit fixo: peso identificado
passada = sys.argv[1]
BRACO = sys.argv[2] if len(sys.argv) > 2 else "L"
PROMPTS = {"L": ("query", "document"), "N": ("QuestionAnswering", "Document")}
if BRACO not in PROMPTS:
    sys.exit(f"braco desconhecido: {BRACO} (so L ou N, declarados no ADENDO 01)")
P_CONSULTA, P_DOC = PROMPTS[BRACO]

perg = {p["id"]: p["texto"] for p in json.loads(
    (B / "suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}

alvo = B / f"derpr/rank/{BRACO}_p{passada}.json"
if alvo.exists():
    print(f"  braco {BRACO} passada {passada}: ja existe, nao sobrescrevo")
    sys.exit()

t0 = time.time()
m = SentenceTransformer(MOD, revision=REVISAO, device="cuda")
carga_modelo = time.time() - t0
print(f"  modelo carregado em {carga_modelo:.1f}s | dim {m.get_sentence_embedding_dimension()} | "
      f"prompts do cartao: {sorted(m.prompts) if getattr(m, 'prompts', None) else 'nenhum'}",
      flush=True)


def norm(a):
    a = np.asarray(a, dtype=np.float32)
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)


t0 = time.time()
Q = norm(m.encode([perg[k] for k in sorted(perg)], prompt_name=P_CONSULTA,
                  batch_size=8, show_progress_bar=False))
seg_consulta = time.time() - t0

f = B / f"derpr/textos/{'B'}_p{passada}.json"
txt = json.loads(f.read_text())
paginas = [txt.get(str(i), "") for i in range(1, 59)]
paginas = [t[:8000] if t.strip() else " " for t in paginas]

t1 = time.time()
Pv = norm(m.encode(paginas, prompt_name=P_DOC, batch_size=4, show_progress_bar=False))
seg_indexacao = time.time() - t1

S = Q @ Pv.T                                        # 30 x 58
rank = {qid: (np.argsort(-S[i]) + 1).tolist() for i, qid in enumerate(sorted(perg))}
alvo.write_text(json.dumps(
    {"braco": BRACO, "passada": int(passada), "rank": rank,
     "embedder": MOD, "revisao": REVISAO, "runtime": "sentence-transformers (fora do Ollama)",
     "texto_de_origem": f"derpr/textos/B_p{passada}.json (Docling com OCR, braco B do ADENDO_07)",
     "prompt_nome_consulta": P_CONSULTA, "prompt_nome_documento": P_DOC,
     "prompt_consulta": (m.prompts or {}).get(P_CONSULTA),
     "prompt_documento": (m.prompts or {}).get(P_DOC),
     "bytes_indice": int(Pv.nbytes), "dim": int(Pv.shape[1]), "vetores_por_pagina": 1,
     "seg_carga_modelo": round(carga_modelo, 2),
     "seg_consulta": round(seg_consulta, 2), "seg_indexacao": round(seg_indexacao, 2),
     "vram_pico_torch_MB": round(torch.cuda.max_memory_allocated() / 2**20)},
    ensure_ascii=False))
print(f"  braco {BRACO} passada {passada}: indice {Pv.nbytes / 1024:.0f} KB, dim {Pv.shape[1]}, "
      f"indexacao {seg_indexacao:.1f}s, consulta {seg_consulta:.1f}s, "
      f"pico torch {torch.cuda.max_memory_allocated() / 2**20:.0f} MB", flush=True)
