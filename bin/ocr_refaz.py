#!/home/mateus/env_transporte/bin/python
"""Refaz, distribuido, os documentos que o lote de 21/11 nao conseguiu: recusa por PDF marcado
(Tagged PDF, codigo 15) e erro de renderizacao. Flags do converter.py MAIS --force-ocr e
--continue-on-soft-render-error. Fila remota propria (~/lote/ocr3). Ao fim, confere os 141."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import converter as cv, ocr_lote as ol, pymupdf
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); J = Path("/home/mateus/.claude_jobs")
E = json.loads((J/"ocr_estado.json").read_text()); cp = json.loads((J/"chave_paginas.json").read_text())
EXTRA = ["--force-ocr", "--continue-on-soft-render-error"]
pend = [c for c, rel in E["rel_de"].items() if cp.get(c, 0) > 0
        and not ((cv.CACHE/f"{c}_ocr.pdf").exists() and cv._ocr_valido(R/rel, cv.CACHE/f"{c}_ocr.pdf"))]
taxa = {"local": 0.45, "geneve": 0.54, "fedora": 0.89}; fim = {m: 0.0 for m in taxa}; parte = {m: [] for m in taxa}
for c in sorted(pend, key=lambda c: -cp[c]):
    m = min(fim, key=lambda m: fim[m] + cp[c] / taxa[m]); parte[m].append(c); fim[m] += cp[c] / taxa[m]
print({m: (len(v), sum(cp[c] for c in v), f"~{fim[m]/60:.0f} min") for m, v in parte.items()}, flush=True)
for h in ("geneve", "fedora"):
    if not parte[h]: continue
    st = Path(f"/tmp/ocr_envio/{h}3"); shutil.rmtree(st, ignore_errors=True); st.mkdir(parents=True)
    for c in parte[h]: os.symlink(R/E["rel_de"][c], st/f"{c}.pdf")
    tar = subprocess.run(["tar", "-chf", "-", "-C", str(st), "."], capture_output=True).stdout
    r = ol.ssh(h, "rm -rf ~/lote/ocr3 && mkdir -p ~/lote/ocr3/in && tar -xf - -C ~/lote/ocr3/in && ls ~/lote/ocr3/in | wc -l", tar, 600)
    rot = ol.roteiro(ol.MAQ[h]["jobs"]).replace("~/lote/ocr;", "~/lote/ocr3;").replace("--output-type pdf", "--output-type pdf " + " ".join(EXTRA))
    ol.ssh(h, "cat > ~/lote/ocr3/roda.sh", rot.encode())
    ok = ol.ssh(h, "bash -n ~/lote/ocr3/roda.sh && grep -c continue-on-soft ~/lote/ocr3/roda.sh").stdout.decode().strip()
    ol.ssh(h, "cd ~/lote/ocr3 && nohup setsid bash roda.sh > /dev/null 2>&1 < /dev/null &")
    print(f"{h}: recebeu {r.stdout.decode().strip()} de {len(parte[h])}, roteiro ok={ok}, lancado", flush=True)
for c in parte["local"]:
    src, dst = R/E["rel_de"][c], cv.CACHE/f"{c}_ocr.pdf"; t = time.time()
    r = subprocess.run(cv.OCR_CMD + EXTRA + [str(src), str(dst)], capture_output=True, text=True)
    print(f"local {c} {cp[c]}p rc={r.returncode} {time.time()-t:.0f}s {r.stderr.strip()[-120:] if r.returncode else ''}", flush=True)
for h in ("geneve", "fedora"):
    if not parte[h]: continue
    while "FIM" not in (log := ol.ssh(h, "cat ~/lote/ocr3/lote.log 2>/dev/null").stdout.decode()): time.sleep(90)
    tar = ol.ssh(h, "tar -cf - -C ~/lote/ocr3/out .", t=900).stdout
    subprocess.run(["tar", "-xf", "-", "-C", str(cv.CACHE)], input=tar)
    print(f"{h}: coletado, falhas {[l for l in log.splitlines() if l and l != 'FIM' and l.split()[1] != '0']}", flush=True)
docs = []
for rel in [l.strip() for l in open("/home/mateus/base_conhecimento/sem_texto_lista.txt") if l.strip()]:
    p = R/rel; q = cv.CACHE/f"{cv.chave_cache(p, ocr=True)}_ocr.pdf"; ok = q.exists() and cv._ocr_valido(p, q); cpp = None
    if ok:
        with pymupdf.open(q) as x: cpp = round(sum(len(pg.get_text()) for pg in x) / max(1, x.page_count))
    docs.append({"arquivo": rel, "valido": ok, "chars_por_pagina": cpp})
json.dump(docs, open("/home/mateus/base_conhecimento/ocr_lote_20261121.json", "w"), ensure_ascii=False, indent=1)
ok = [d for d in docs if d["valido"]]
print(f"RESULTADO FINAL: {len(ok)} de {len(docs)} validos; pouco texto: {sum(1 for d in ok if d['chars_por_pagina'] < 200)}; invalidos: {[d['arquivo'][-45:] for d in docs if not d['valido']]}")
print("FIM")
