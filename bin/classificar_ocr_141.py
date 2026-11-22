#!/home/mateus/env_transporte/bin/python
"""Classifica PELO TEXTO os documentos que so ganharam texto com o OCR de 21/11/2026, usando o
PDF processado do cache. Motivo: classificar so pelo nome concordou com o texto em 40% (medido).
Grava catalogo_ocr_v2.jsonl no mesmo formato do catalogo v2, com hash e bytes do ORIGINAL."""
import json, os, sys, time
from pathlib import Path
os.environ.setdefault("TAXONOMIA_ACERVO", "subareas_transportes_v2.json")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogar_acervo as ca, converter as cv
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); S = Path("/home/mateus/base_conhecimento/catalogo_ocr_v2.jsonl")
feitos = {json.loads(l)["arquivo"] for l in open(S)} if S.exists() else set()
lista = [l.strip() for l in open("/home/mateus/base_conhecimento/sem_texto_lista.txt") if l.strip()]
t0 = time.time()
with open(S, "a", encoding="utf-8") as f:
    for i, rel in enumerate(lista, 1):
        if rel in feitos: continue
        p = R/rel; q = cv.CACHE/f"{cv.chave_cache(p, ocr=True)}_ocr.pdf"
        if not (q.exists() and cv._ocr_valido(p, q)):
            print(f"{i} sem OCR valido: {rel[-60:]}", flush=True); continue
        d = ca.catalogar_um(q, rel, "qwen3:14b", 8192)
        d.update({"hash": ca.hash24(p), "bytes": p.stat().st_size, "fonte_texto": "ocr_por+eng_20261121",
                  "protocolo": "taxonomia corrigida 21/11 + secundaria com motivo primeiro"})
        f.write(json.dumps(d, ensure_ascii=False) + "\n"); f.flush()
        print(f"{i}/{len(lista)} {time.time()-t0:.0f}s {d.get('status')} {d.get('subarea_principal')} | {rel[-55:]}", flush=True)
print("FIM")
