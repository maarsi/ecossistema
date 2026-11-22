#!/home/mateus/env_transporte/bin/python
"""Coletor: espera FIM nas tres filas remotas, traz os resultados para o cache, confere os 141."""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import converter as cv, ocr_lote as ol, pymupdf
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); J = Path("/home/mateus/.claude_jobs")
filas = [("geneve", "~/lote/ocr"), ("fedora", "~/lote/ocr"), ("fedora", "~/lote/ocr2")]
pend = list(filas)
while pend:
    for h, d in list(pend):
        log = ol.ssh(h, f"cat {d}/lote.log 2>/dev/null").stdout.decode()
        if "FIM" in log:
            tar = ol.ssh(h, f"tar -cf - -C {d}/out .", t=900).stdout
            subprocess.run(["tar", "-xf", "-", "-C", str(cv.CACHE)], input=tar)
            falhas = [l for l in log.splitlines() if l and l != "FIM" and l.split()[1] != "0"]
            print(f"{time.strftime('%H:%M')} coletado {h}:{d} {len(tar)/2**20:.0f} MB, {log.count(chr(10))-1} docs, falhas {falhas}", flush=True)
            pend.remove((h, d))
    if pend: time.sleep(120)
while subprocess.run(["pgrep", "-f", "[o]cr_trabalhador.py"]).returncode == 0: time.sleep(60)
docs = []
for rel in [l.strip() for l in open("/home/mateus/base_conhecimento/sem_texto_lista.txt") if l.strip()]:
    p = R/rel; q = cv.CACHE/f"{cv.chave_cache(p, ocr=True)}_ocr.pdf"; ok = q.exists() and cv._ocr_valido(p, q)
    cpp = None
    if ok:
        with pymupdf.open(q) as x: cpp = round(sum(len(pg.get_text()) for pg in x) / max(1, x.page_count))
    docs.append({"arquivo": rel, "valido": ok, "chars_por_pagina": cpp, "pdf_ocr": str(q) if ok else None})
json.dump(docs, open("/home/mateus/base_conhecimento/ocr_lote_20261121.json", "w"), ensure_ascii=False, indent=1)
ok = [d for d in docs if d["valido"]]
print(f"RESULTADO: {len(ok)} de {len(docs)} validos; pouco texto (<200 car./pag.): {sum(1 for d in ok if d['chars_por_pagina'] < 200)}; "
      f"invalidos: {[d['arquivo'][-50:] for d in docs if not d['valido']]}")
print("FIM")
