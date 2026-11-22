#!/home/mateus/env_transporte/bin/python
"""Refaz com --force-ocr os documentos que o OCRmyPDF recusou por serem Tagged PDF (codigo 15 no
lote de 21/11). O nome contem 'ocr_trabalhador' de proposito: o coletor espera esse padrao."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import converter as cv
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); E = json.loads(Path("/home/mateus/.claude_jobs/ocr_estado.json").read_text())
for c in sys.argv[1:]:
    rel = E["rel_de"][c + "_ocr"] if c + "_ocr" in E["rel_de"] else E["rel_de"][c]
    src, dst = R/rel, cv.CACHE/f"{c}_ocr_ocr.pdf" if not c.endswith("_ocr") else cv.CACHE/f"{c}_ocr.pdf"
    t = time.time(); r = subprocess.run(cv.OCR_CMD + ["--force-ocr", str(src), str(dst)], capture_output=True, text=True)
    print(f"{c} rc={r.returncode} {time.time()-t:.0f}s valido={dst.exists() and cv._ocr_valido(src, dst)} | {rel[-60:]} | {r.stderr.strip()[-150:] if r.returncode else ''}", flush=True)
print("FIM")
