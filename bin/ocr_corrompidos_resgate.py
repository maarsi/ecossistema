#!/home/mateus/env_transporte/bin/python
"""RESGATE 23/11/2026 00h25: o geneve saiu da rede no meio do OCR dos 61 corrompidos (Tailscale 'offline, last
seen 1h', ping sem resposta; provavel suspensao ou travamento, nao investigado). Este script: coleta o que o
Zurich (fedora) ja fez em ~/lote/ocr4, manda a parte do geneve (mesma particao determinista do ocr_corrompidos.py)
para o Zurich em ~/lote/ocr5, coleta e faz a conferencia final de legibilidade. Mesma saida do original."""
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
while "FIM" not in (log := ol.ssh("fedora", "cat ~/lote/ocr4/lote.log 2>/dev/null").stdout.decode()): time.sleep(60)
tar = ol.ssh("fedora", "tar -cf - -C ~/lote/ocr4/out .", t=1800).stdout
subprocess.run(["tar", "-xf", "-", "-C", str(cv.CACHE)], input=tar)
print(f"fedora parte 1: coletado, falhas {[l for l in log.splitlines() if l and l != 'FIM' and l.split()[1] != '0']}", flush=True)
g = parte["geneve"]
st_ = Path("/tmp/ocr_envio/fedora5"); shutil.rmtree(st_, ignore_errors=True); st_.mkdir(parents=True)
for d in g: os.symlink(R/d["arquivo"], st_/f"{d['chave']}.pdf")
tar = subprocess.run(["tar", "-chf", "-", "-C", str(st_), "."], capture_output=True).stdout
r = ol.ssh("fedora", "rm -rf ~/lote/ocr5 && mkdir -p ~/lote/ocr5/in && tar -xf - -C ~/lote/ocr5/in && ls ~/lote/ocr5/in | wc -l", tar, 900)
rot = ol.roteiro(ol.MAQ["fedora"]["jobs"]).replace("~/lote/ocr;", "~/lote/ocr5;").replace("--output-type pdf", "--output-type pdf " + " ".join(EXTRA))
ol.ssh("fedora", "cat > ~/lote/ocr5/roda.sh", rot.encode())
ok = ol.ssh("fedora", "bash -n ~/lote/ocr5/roda.sh && grep -c force-ocr ~/lote/ocr5/roda.sh").stdout.decode().strip()
ol.ssh("fedora", "cd ~/lote/ocr5 && nohup setsid bash roda.sh > /dev/null 2>&1 < /dev/null &")
print(f"fedora parte 2 (a do geneve): recebeu {r.stdout.decode().strip()} de {len(g)}, {sum(d['paginas'] for d in g)} paginas, force-ocr={ok}, lancado", flush=True)
while "FIM" not in (log := ol.ssh("fedora", "cat ~/lote/ocr5/lote.log 2>/dev/null").stdout.decode()): time.sleep(90)
tar = ol.ssh("fedora", "tar -cf - -C ~/lote/ocr5/out .", t=1800).stdout
subprocess.run(["tar", "-xf", "-", "-C", str(cv.CACHE)], input=tar)
print(f"fedora parte 2: coletado, falhas {[l for l in log.splitlines() if l and l != 'FIM' and l.split()[1] != '0']}", flush=True)
res = []
for d in L:
    q = cv.CACHE/f"{d['chave']}_ocr.pdf"
    ok = q.exists() and cv._ocr_valido(R/d["arquivo"], q)
    res.append({**d, "ocr_valido": ok, "legibilidade_antes": round(d["mediana"], 2), "legibilidade_depois": legivel(q) if ok else None})
json.dump(res, open(BC/"ocr_corrompidos_20261122.json", "w"), ensure_ascii=False, indent=1)
bons = [r for r in res if r["legibilidade_depois"] is not None and r["legibilidade_depois"] >= 0.5]
print(f"RESULTADO: {sum(r['ocr_valido'] for r in res)} de {len(res)} com OCR valido; {len(bons)} legiveis (>= 0,5) depois do OCR")
print("FIM")
