#!/home/mateus/env_transporte/bin/python
"""Rebalanceamento do OCR distribuido de 21/11/2026 sem retrabalho. Le o estado salvo
(o que cada notebook recebeu), divide o que falta da parte local entre a workstation e uma
SEGUNDA fila no notebook mais rapido, que comeca sozinha quando a primeira termina."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import converter as cv, ocr_lote as ol
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); J = Path("/home/mateus/.claude_jobs")
E = json.loads((J/"ocr_estado.json").read_text()); cp = json.loads((J/"chave_paginas.json").read_text())
falta = sorted(E["falta_local"], key=lambda c: -cp[c])
# [premissa] taxas medidas nesta noite: workstation ~0,5 pag/s (dividindo CPU), fedora 0,97 pag/s
# a partir de ~100 min daqui, quando a primeira fila dele acaba
fim = {"local": 0.0, "fedora": 100 * 60.0}; taxa = {"local": 0.5, "fedora": 0.97}; parte = {"local": [], "fedora": []}
for c in falta:
    m = min(fim, key=lambda m: fim[m] + cp[c] / taxa[m]); parte[m].append(c); fim[m] += cp[c] / taxa[m]
print({m: (len(v), sum(cp[c] for c in v), f"termina em ~{fim[m]/60:.0f} min") for m, v in parte.items()}, flush=True)
(J/"ocr_parte_local.json").write_text(json.dumps(parte["local"]))
st = Path("/tmp/ocr_envio/fedora2"); shutil.rmtree(st, ignore_errors=True); st.mkdir(parents=True)
for c in parte["fedora"]: os.symlink(R/E["rel_de"][c], st/f"{c}.pdf")
tar = subprocess.run(["tar", "-chf", "-", "-C", str(st), "."], capture_output=True).stdout
r = ol.ssh("fedora", "rm -rf ~/lote/ocr2 && mkdir -p ~/lote/ocr2/in && tar -xf - -C ~/lote/ocr2/in && ls ~/lote/ocr2/in | wc -l", tar, 600)
print("fedora2 recebeu", r.stdout.decode().strip(), "de", len(parte["fedora"]), flush=True)
rot = ol.roteiro(ol.MAQ["fedora"]["jobs"]).replace("~/lote/ocr;", "~/lote/ocr2;")
rot = "until grep -q '^FIM' ~/lote/ocr/lote.log 2>/dev/null; do sleep 30; done\n" + rot
ol.ssh("fedora", "cat > ~/lote/ocr2/roda.sh", rot.encode())
ok = ol.ssh("fedora", "bash -n ~/lote/ocr2/roda.sh && grep -c 'lote/ocr2' ~/lote/ocr2/roda.sh").stdout.decode().strip()
print("roteiro fedora2 sintaxe + destino:", ok, flush=True)
ol.ssh("fedora", "cd ~/lote/ocr2 && nohup setsid bash roda.sh > /dev/null 2>&1 < /dev/null &"); print("fedora2 armado (espera a fila 1 terminar)")
