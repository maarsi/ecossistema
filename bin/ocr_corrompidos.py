#!/home/mateus/env_transporte/bin/python
"""OCR forcado dos 61 documentos com CAMADA DE TEXTO CORROMPIDA (achado de 22/11/2026: o PDF tem texto, mas a
codificacao das fontes esta quebrada, e o pipeline so fazia OCR no que NAO tinha texto). So nos notebooks, para nao
disputar a workstation com a indexacao e com a bateria VRPTW. Mesmo roteiro e mesma chave de cache do ocr_lote.py,
com --force-ocr (refaz o texto de toda pagina) e --continue-on-soft-render-error. Fila remota ~/lote/ocr4.
Ao fim confere, para cada documento, a fracao de palavras plausiveis ANTES e DEPOIS."""
import json, os, re, shutil, subprocess, statistics as st, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import converter as cv, ocr_lote as ol, pymupdf
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); BC = Path("/home/mateus/base_conhecimento")
L = json.load(open(BC/"texto_corrompido_20261122.json"))
EXTRA = ["--force-ocr", "--continue-on-soft-render-error"]
pal = re.compile(r"^[A-Za-zÀ-ÿ]{2,}$"); vog = re.compile(r"[aeiouáéíóúâêôãõàAEIOUÁÉÍÓÚÂÊÔÃÕ]")
def legivel(pdf):
    v = []
    with pymupdf.open(pdf) as d:
        for pg in d:
            tk = pg.get_text().split()
            if len(tk) >= 20: v.append(sum(1 for x in tk if pal.match(x.strip('.,;:()"\'')) and vog.search(x)) / len(tk))
    return round(st.median(v), 2) if v else None
taxa = {"geneve": 0.54, "fedora": 0.89}; fim = {m: 0.0 for m in taxa}; parte = {m: [] for m in taxa}
for d in sorted(L, key=lambda d: -d["paginas"]):
    m = min(fim, key=lambda m: fim[m] + d["paginas"] / taxa[m]); parte[m].append(d); fim[m] += d["paginas"] / taxa[m]
print({m: (len(v), sum(d["paginas"] for d in v), f"~{fim[m]/60:.0f} min") for m, v in parte.items()}, flush=True)
for h in taxa:
    st_ = Path(f"/tmp/ocr_envio/{h}4"); shutil.rmtree(st_, ignore_errors=True); st_.mkdir(parents=True)
    for d in parte[h]: os.symlink(R/d["arquivo"], st_/f"{d['chave']}.pdf")
    tar = subprocess.run(["tar", "-chf", "-", "-C", str(st_), "."], capture_output=True).stdout
    r = ol.ssh(h, "rm -rf ~/lote/ocr4 && mkdir -p ~/lote/ocr4/in && tar -xf - -C ~/lote/ocr4/in && ls ~/lote/ocr4/in | wc -l", tar, 900)
    rot = ol.roteiro(ol.MAQ[h]["jobs"]).replace("~/lote/ocr;", "~/lote/ocr4;").replace("--output-type pdf", "--output-type pdf " + " ".join(EXTRA))
    ol.ssh(h, "cat > ~/lote/ocr4/roda.sh", rot.encode())
    ok = ol.ssh(h, "bash -n ~/lote/ocr4/roda.sh && grep -c force-ocr ~/lote/ocr4/roda.sh").stdout.decode().strip()
    ol.ssh(h, "cd ~/lote/ocr4 && nohup setsid bash roda.sh > /dev/null 2>&1 < /dev/null &")
    print(f"{h}: recebeu {r.stdout.decode().strip()} de {len(parte[h])}, roteiro com force-ocr={ok}, lancado", flush=True)
for h in taxa:
    while "FIM" not in (log := ol.ssh(h, "cat ~/lote/ocr4/lote.log 2>/dev/null").stdout.decode()): time.sleep(120)
    tar = ol.ssh(h, "tar -cf - -C ~/lote/ocr4/out .", t=1800).stdout
    subprocess.run(["tar", "-xf", "-", "-C", str(cv.CACHE)], input=tar)
    print(f"{h}: coletado, falhas {[l for l in log.splitlines() if l and l != 'FIM' and l.split()[1] != '0']}", flush=True)
res = []
for d in L:
    q = cv.CACHE/f"{d['chave']}_ocr.pdf"
    ok = q.exists() and cv._ocr_valido(R/d["arquivo"], q)
    res.append({**d, "ocr_valido": ok, "legibilidade_antes": round(d["mediana"], 2), "legibilidade_depois": legivel(q) if ok else None})
json.dump(res, open(BC/"ocr_corrompidos_20261122.json", "w"), ensure_ascii=False, indent=1)
bons = [r for r in res if r["legibilidade_depois"] is not None and r["legibilidade_depois"] >= 0.5]
print(f"RESULTADO: {sum(r['ocr_valido'] for r in res)} de {len(res)} com OCR valido; {len(bons)} legiveis (>= 0,5) depois do OCR")
print("FIM")
