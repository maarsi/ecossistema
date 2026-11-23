#!/home/mateus/env_transporte/bin/python
"""Classifica PELO TEXTO DO OCR os documentos cuja camada de texto original estava CORROMPIDA (achado de 22/11/2026),
usando o PDF do OCR forcado (bin/ocr_corrompidos.py). Adaptado de classificar_ocr_141.py. Antigo cabecalho: o
PDF processado do cache. Motivo: classificar so pelo nome concordou com o texto em 40% (medido).
Grava catalogo_ocr_v2.jsonl no mesmo formato do catalogo v2, com hash e bytes do ORIGINAL."""
import json, os, sys, time
from pathlib import Path
os.environ.setdefault("TAXONOMIA_ACERVO", "subareas_transportes_v2.json")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogar_acervo as ca, converter as cv
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); S = Path("/home/mateus/base_conhecimento/catalogo_ocr_corrompidos.jsonl")
feitos = {json.loads(l)["arquivo"] for l in open(S)} if S.exists() else set()
lista = [r["arquivo"] for r in json.load(open("/home/mateus/base_conhecimento/ocr_corrompidos_20261122.json"))
         if (r.get("legibilidade_depois") or 0) >= 0.5]
t0 = time.time()
with open(S, "a", encoding="utf-8") as f:
    for i, rel in enumerate(lista, 1):
        if rel in feitos: continue
        p = R/rel; q = cv.CACHE/f"{cv.chave_cache(p, ocr=True)}_ocr.pdf"
        if not (q.exists() and cv._ocr_valido(p, q)):
            print(f"{i} sem OCR valido: {rel[-60:]}", flush=True); continue
        d = ca.catalogar_um(q, rel, "qwen3:14b", 8192)
        d.update({"hash": ca.hash24(p), "bytes": p.stat().st_size, "fonte_texto": "ocr_forcado_por+eng_20261122",
                  "protocolo": "taxonomia corrigida 21/11 + secundaria com motivo primeiro"})
        f.write(json.dumps(d, ensure_ascii=False) + "\n"); f.flush()
        print(f"{i}/{len(lista)} {time.time()-t0:.0f}s {d.get('status')} {d.get('subarea_principal')} | {rel[-55:]}", flush=True)
print("FIM")
