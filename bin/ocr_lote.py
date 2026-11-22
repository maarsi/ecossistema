#!/home/mateus/env_transporte/bin/python
"""OCR em lote distribuido entre a workstation e os notebooks de lote (geneve, fedora/Zurich).
Grava cada resultado no cache do converter.py com a MESMA chave, de modo que a conversao
posterior (converter.py --ocr, indice.py) reaproveita em vez de refazer.
Fronteira de dados: so para acervo de REFERENCIA (publicado). Nunca dado de cliente.
Uso: ocr_lote.py --lista arquivos.txt --raiz <acervo> --manifesto saida.json"""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import converter as cv, pymupdf
U = "mateusaraujoesilva"
# peso pela capacidade MEDIDA em 13/11 (todos os nucleos, 60 s): ws 88.233, geneve 56.753,
# zurich 50.077 blocos/s. A workstation leva peso menor que a medida porque divide CPU com o
# catalogo em curso. [premissa] de divisao, nao medicao de OCR.
MAQ = {"local": {"peso": 0.40, "jobs": 6}, "geneve": {"peso": 0.32, "jobs": 6}, "fedora": {"peso": 0.28, "jobs": 10}}
FLAGS = [a for a in cv.OCR_CMD[1:] if a not in ("--jobs", "6")]      # sem --jobs: cada maquina usa o seu

def ssh(host, cmd, entrada=None, t=120):
    return subprocess.run(["timeout", str(t), "tailscale", "ssh", "--", f"{U}@{host}", cmd],
                          input=entrada, capture_output=True, timeout=t + 10)

def roteiro(jobs):
    f = " ".join(FLAGS)
    # TESSDATA_PREFIX: os notebooks nao tem osd.traineddata no sistema, e --rotate-pages exige.
    # Medido em 21/11/2026: sem ele, codigo 7 em 4 de 4. Instalado em ~/tessdata sem sudo.
    return f"""set -u; export TESSDATA_PREFIX=$HOME/tessdata; cd ~/lote/ocr; mkdir -p out; : > lote.log
for p in in/*.pdf; do n=$(basename "$p" .pdf); t0=$(date +%s)
  ~/venv_lote/bin/ocrmypdf {f} --jobs {jobs} "$p" "out/${{n}}_ocr.pdf" >> erros.log 2>&1; rc=$?
  if [ $rc -eq 6 ]; then ~/venv_lote/bin/ocrmypdf {f} --jobs {jobs} --force-ocr "$p" "out/${{n}}_ocr.pdf" >> erros.log 2>&1; rc=$?; fi
  echo "$n $rc $(( $(date +%s) - t0 ))" >> lote.log
done; echo FIM >> lote.log
"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lista"); ap.add_argument("--raiz"); ap.add_argument("--manifesto")
    a = ap.parse_args(); R = Path(a.raiz)
    docs = []
    for rel in [l.strip() for l in open(a.lista) if l.strip()]:
        p = R / rel; ch = cv.chave_cache(p, ocr=True); dest = cv.CACHE / f"{ch}_ocr.pdf"
        try:
            with pymupdf.open(p) as d: n = d.page_count
        except Exception: n = 0
        docs.append({"arquivo": rel, "chave": ch, "paginas": n, "destino": str(dest),
                     "ja_feito": dest.exists() and cv._ocr_valido(p, dest)})
    pend = [d for d in docs if not d["ja_feito"] and d["paginas"] > 0]
    ileg = [d for d in docs if d["paginas"] == 0]
    carga = {m: 0 for m in MAQ}
    for d in sorted(pend, key=lambda d: -d["paginas"]):                 # guloso pela capacidade
        m = min(MAQ, key=lambda m: (carga[m] + d["paginas"]) / MAQ[m]["peso"])
        d["maquina"] = m; carga[m] += d["paginas"]
    print(f"{len(docs)} docs | ja no cache {sum(d['ja_feito'] for d in docs)} | ilegiveis {len(ileg)} | paginas por maquina {carga}", flush=True)
    cv.CACHE.mkdir(parents=True, exist_ok=True); t0 = time.time()
    for host in ("geneve", "fedora"):                                    # envio
        meus = [d for d in pend if d["maquina"] == host]
        if not meus: continue
        st = Path(f"/tmp/ocr_envio/{host}"); shutil.rmtree(st, ignore_errors=True); st.mkdir(parents=True)
        for d in meus: os.symlink(R / d["arquivo"], st / f"{d['chave']}.pdf")
        tar = subprocess.run(["tar", "-chf", "-", "-C", str(st), "."], capture_output=True).stdout
        r = ssh(host, "rm -rf ~/lote/ocr && mkdir -p ~/lote/ocr/in && tar -xf - -C ~/lote/ocr/in && ls ~/lote/ocr/in | wc -l", tar, 600)
        print(f"  {host}: enviados {r.stdout.decode().strip()} de {len(meus)} ({len(tar)/2**20:.0f} MB) em {time.time()-t0:.0f}s", flush=True)
        ssh(host, "cat > ~/lote/ocr/roda.sh", roteiro(MAQ[host]["jobs"]).encode())
        chk = ssh(host, "bash -n ~/lote/ocr/roda.sh && echo SINTAXE_OK")
        if b"SINTAXE_OK" not in chk.stdout: print(f"  {host}: roteiro com erro de sintaxe, NAO lancado"); continue
        ssh(host, "cd ~/lote/ocr && nohup setsid bash roda.sh > /dev/null 2>&1 < /dev/null &")
        print(f"  {host}: lancado", flush=True)
    for d in [d for d in pend if d["maquina"] == "local"]:              # parte local, sequencial
        t1 = time.time()
        try:
            cv._ocr(R / d["arquivo"], Path(d["destino"])); d["rc"] = 0
        except Exception as e:
            d["rc"] = 1; d["erro"] = str(e)[-200:]
        d["segundos"] = round(time.time() - t1); print(f"  local {d['paginas']}p {d['segundos']}s rc={d['rc']} {d['arquivo'][-60:]}", flush=True)
    for host in ("geneve", "fedora"):                                    # espera e coleta
        meus = [d for d in pend if d["maquina"] == host]
        if not meus: continue
        while True:
            log = ssh(host, "cat ~/lote/ocr/lote.log 2>/dev/null").stdout.decode()
            if "FIM" in log: break
            print(f"  {host}: {log.count(chr(10))} de {len(meus)} prontos, {time.time()-t0:.0f}s", flush=True); time.sleep(60)
        tar = ssh(host, "tar -cf - -C ~/lote/ocr/out .", t=900).stdout
        subprocess.run(["tar", "-xf", "-", "-C", str(cv.CACHE)], input=tar)
        info = {l.split()[0]: l.split()[1:] for l in log.splitlines() if l and l != "FIM"}
        for d in meus:
            rc, s = info.get(d["chave"], ["?", "?"]); d["rc"], d["segundos"] = rc, s
        print(f"  {host}: coletado {len(tar)/2**20:.0f} MB", flush=True)
    for d in docs:                                                       # conferencia
        p, q = R / d["arquivo"], Path(d["destino"])
        d["valido"] = q.exists() and cv._ocr_valido(p, q)
        if d["valido"]:
            with pymupdf.open(q) as x: d["chars_por_pagina"] = round(sum(len(pg.get_text()) for pg in x) / max(1, x.page_count))
    json.dump(docs, open(a.manifesto, "w"), ensure_ascii=False, indent=1)
    ok = [d for d in docs if d.get("valido")]
    print(f"\nRESULTADO: {len(ok)} de {len(docs)} validos em {time.time()-t0:.0f}s")
    print(f"  pouco texto (<200 car./pag.): {[d['arquivo'][-50:] for d in ok if d.get('chars_por_pagina', 0) < 200][:12]}")
    print(f"  falhas: {[(d['arquivo'][-50:], d.get('maquina'), d.get('rc')) for d in docs if not d.get('valido')]}")
    print("FIM")
if __name__ == "__main__":
    main()
