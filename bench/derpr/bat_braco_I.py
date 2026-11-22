"""Braco I (ADENDO_11): a cadeia de producao do indice para PDF digitalizado.
OCRmyPDF com as flags do converter.py -> PyMuPDF por pagina -> qwen3-embedding:4b."""
import json, pathlib, sys, time, requests, numpy as np, pymupdf
sys.path.insert(0, str(pathlib.Path.home()/"ecossistema/bin")); import converter as cv
B = pathlib.Path.home()/"ecossistema/bench"
PDF = B/"dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf"
OCRP = B/"derpr/_braco_I_ocr.pdf"
if not OCRP.exists():
    t0 = time.time(); cv._ocr(PDF, OCRP); print(f"OCRmyPDF: {time.time()-t0:.0f}s, comando {' '.join(cv.OCR_CMD)}", flush=True)
with pymupdf.open(OCRP) as d: out = {str(i+1): d[i].get_text() for i in range(d.page_count)}
assert len(out) == 58, len(out)
perg = {p["id"]: p["texto"] for p in json.loads((B/"suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}
def emb(textos, lote=8):
    v = []
    for k in range(0, len(textos), lote):
        r = requests.post("http://localhost:11434/api/embed", json={"model": "qwen3-embedding:4b",
             "input": [t[:8000] if t.strip() else " " for t in textos[k:k+lote]]}, timeout=600)
        r.raise_for_status(); v.extend(r.json()["embeddings"])
    a = np.array(v, dtype=np.float32); return a/(np.linalg.norm(a, axis=1, keepdims=True)+1e-9)
for passada in (1, 2, 3):
    (B/f"derpr/textos/I_p{passada}.json").write_text(json.dumps(out, ensure_ascii=False))
    Q = emb([perg[k] for k in sorted(perg)]); Pv = emb([out[str(i)] for i in range(1, 59)]); S = Q @ Pv.T
    rank = {q: (np.argsort(-S[i])+1).tolist() for i, q in enumerate(sorted(perg))}
    (B/f"derpr/rank/I_p{passada}.json").write_text(json.dumps({"braco": "I", "passada": passada, "rank": rank,
        "bytes_indice": int(Pv.nbytes), "dim": int(Pv.shape[1]), "vetores_por_pagina": 1}))
    print(f"I passada {passada}: ok, {sum(1 for t in out.values() if len(t.strip())<20)} paginas quase vazias", flush=True)
print("FIM")
