#!/home/mateus/env_transporte/bin/python
"""Trabalhador local: processa a lista de chaves, PULANDO o que ja estiver valido no cache."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import converter as cv
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); J = Path("/home/mateus/.claude_jobs")
E = json.loads((J/"ocr_estado.json").read_text()); cp = json.loads((J/"chave_paginas.json").read_text())
for c in json.loads((J/"ocr_parte_local.json").read_text()):
    src, dst = R/E["rel_de"][c], cv.CACHE/f"{c}_ocr.pdf"
    if dst.exists() and cv._ocr_valido(src, dst): print("ja feito", c, flush=True); continue
    t = time.time()
    try: cv._ocr(src, dst); rc = 0
    except Exception as e: rc = str(e)[-120:]
    print(f"{c} {cp[c]}p {time.time()-t:.0f}s rc={rc}", flush=True)
print("FIM")
