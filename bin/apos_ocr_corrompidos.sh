#!/bin/bash
# Encadeado em 22/11/2026 23h: correcao dos 61 documentos com camada de texto corrompida.
# Espera o OCR forcado nos notebooks (PID 870315) E o fim da indexacao + bateria VRPTW (PID 612414), para nao
# disputar GPU com a bateria. Depois: reclassifica pelo texto do OCR, regenera a taxonomia, reindexa so os
# afetados (colecoes antigas e novas, com --refazer-lista) e grava o antes/depois das classes.
set -u
BC=/home/mateus/base_conhecimento; PY=/home/mateus/env_transporte/bin/python; BIN=/home/mateus/ecossistema/bin
for P in 870315 612414; do while kill -0 $P 2>/dev/null; do sleep 60; done; done
echo "[$(date +%F' '%H:%M)] OCR e bateria terminados"
grep -q "^FIM" /home/mateus/.claude_jobs/ocr_corrompidos.log || { echo "OCR NAO TERMINOU BEM; paro aqui"; exit 1; }
cp $BC/revisao_taxonomia_v2.csv $BC/revisao_taxonomia_v2_antes_corrompidos.csv
$PY $BIN/classificar_corrompidos.py 2>&1 | tail -3
cd $BC && $PY $BIN/taxonomia_v2_final.py 2>&1 | tail -4
$PY - <<'EOF'
import csv, json
BC="/home/mateus/base_conhecimento"
L=[r["arquivo"] for r in json.load(open(f"{BC}/ocr_corrompidos_20261122.json")) if (r.get("legibilidade_depois") or 0)>=0.5]
A={r["arquivo"]:r for r in csv.DictReader(open(f"{BC}/revisao_taxonomia_v2_antes_corrompidos.csv",encoding="utf-8-sig"))}
D={r["arquivo"]:r for r in csv.DictReader(open(f"{BC}/revisao_taxonomia_v2.csv",encoding="utf-8-sig"))}
mud=[dict(arquivo=a,antes=A[a]["subarea_principal"],depois=D[a]["subarea_principal"],origem=D[a]["origem_classificacao"]) for a in L]
json.dump(mud,open(f"{BC}/corrompidos_antes_depois.json","w"),ensure_ascii=False,indent=1)
open(f"{BC}/corrompidos_refazer.txt","w").write("\n".join(L)+"\n")
sub=sorted({m["antes"] for m in mud}|{m["depois"] for m in mud})
open(f"{BC}/corrompidos_subareas.txt","w").write("\n".join(sub)+"\n")
print(len(L),"legiveis;",sum(m["antes"]!=m["depois"] for m in mud),"mudaram de classe; colecoes afetadas:",len(sub))
EOF
ACERVO="/mnt/nvme_lexar/acervo/40 - REFERENCIAS"
for s in $(cat $BC/corrompidos_subareas.txt); do
  echo "=== [$(date +%H:%M)] reindexa $s"
  $PY $BIN/indice.py indexar "$ACERVO" --nome ref40_$s --catalogo $BC/catalogo_indice_v2.jsonl --subarea $s --pular-duplicatas --refazer-lista $BC/corrompidos_refazer.txt 2>&1 | grep --line-buffered -E "^filtro|^INDICE|ERRO|Traceback"
done
echo "[$(date +%F' '%H:%M)] FIM_CORROMPIDOS"
