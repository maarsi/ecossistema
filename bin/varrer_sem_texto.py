#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Lista os PDFs do acervo que nao tem camada de texto e portanto precisam de OCR.
SO LE o acervo. Criterio: media de caracteres por pagina amostrada abaixo do limiar,
o mesmo criterio do indice.py, para os dois concordarem sobre o que e 'sem texto'."""
import json, os, sys
import pymupdf

RAIZ = sys.argv[1] if len(sys.argv) > 1 else "/media/mateus/DADOS_01/40 - REFERENCIAS"
SAIDA = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2
                           else "~/base_conhecimento/precisa_ocr.json")
LIMIAR = 100          # caracteres por pagina; igual ao do indice.py
AMOSTRA = 5           # paginas espalhadas pelo documento

pdfs = []
for cur, d, fs in os.walk(RAIZ):
    for f in fs:
        if f.lower().endswith(".pdf"):
            pdfs.append(os.path.join(cur, f))
pdfs.sort()
print("PDFs: %d" % len(pdfs), flush=True)

precisa, ok, erro = [], 0, []
for i, p in enumerate(pdfs, 1):
    rel = os.path.relpath(p, RAIZ)
    try:
        with pymupdf.open(p) as doc:
            n = doc.page_count
            idx = sorted(set(int(j * (n - 1) / (AMOSTRA - 1)) for j in range(AMOSTRA))) if n > 1 else [0]
            chars = sum(len(doc.load_page(j).get_text("text").strip()) for j in idx)
            dens = chars / len(idx)
        if dens < LIMIAR:
            precisa.append({"arquivo": rel, "paginas": n, "dens": round(dens, 1),
                            "bytes": os.path.getsize(p)})
        else:
            ok += 1
    except Exception as e:
        erro.append({"arquivo": rel, "erro": "%s: %s" % (type(e).__name__, str(e)[:70])})
    if i % 400 == 0:
        print("  %d/%d" % (i, len(pdfs)), flush=True)

precisa.sort(key=lambda r: -r["paginas"])
json.dump({"raiz": RAIZ, "limiar": LIMIAR, "com_texto": ok,
           "precisa_ocr": precisa, "erro": erro},
          open(SAIDA, "w"), ensure_ascii=False, indent=1)
tot_pag = sum(r["paginas"] for r in precisa)
tot_mb = sum(r["bytes"] for r in precisa) / 1048576
print()
print("com camada de texto .... %d" % ok)
print("PRECISAM DE OCR ........ %d  (%d paginas, %.0f MB)" % (len(precisa), tot_pag, tot_mb))
print("erro ao abrir .......... %d" % len(erro))
for r in precisa[:8]:
    print("   %4d pag  dens %5.1f  %s" % (r["paginas"], r["dens"], r["arquivo"][:66]))
print("lista em %s" % SAIDA)
