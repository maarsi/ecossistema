#!/bin/bash
# Encadeado em 22/11/2026: espera a indexacao (por PID, nunca por pgrep do proprio nome), reindexa a colecao
# economia_avaliacao_regulacao (13 docs reclassificados depois de ela ter sido indexada) e roda a bateria VRPTW
# com a GPU livre, conforme bench/vrptw/PRE_REGISTRO.md.
set -u
PID=580662
while kill -0 $PID 2>/dev/null; do sleep 60; done
echo "[$(date +%F' '%H:%M)] indexacao terminou"
PY=/home/mateus/env_transporte/bin/python; IX=/home/mateus/ecossistema/bin/indice.py
ACERVO="/mnt/nvme_lexar/acervo/40 - REFERENCIAS"; CAT=/home/mateus/base_conhecimento/catalogo_indice_v2.jsonl
$PY $IX indexar "$ACERVO" --nome ref40_economia_avaliacao_regulacao --catalogo $CAT --subarea economia_avaliacao_regulacao --pular-duplicatas --sem-docling 2>&1 | grep --line-buffered -E "^filtro|^INDICE|ERRO|Traceback"
$PY $IX indexar "$ACERVO" --nome ref40_economia_avaliacao_regulacao --catalogo $CAT --subarea economia_avaliacao_regulacao --pular-duplicatas --refazer-docling 2>&1 | grep --line-buffered -E "^filtro|^INDICE|ERRO|Traceback"
for i in $(seq 1 60); do u=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1); [ "$u" -lt 10 ] && break; sleep 60; done
echo "[$(date +%F' '%H:%M)] GPU em ${u}% ; VRPTW"
cd /home/mateus/ecossistema/bench/vrptw
/mnt/nvme_lexar/envs/cuopt/bin/python vrptw_cuopt_ortools.py --orcamento 30 --rep-cuopt 3 --primeira PARALLEL_CHEAPEST_INSERTION 2>&1 | grep --line-buffered -v Warning
echo "[$(date +%F' '%H:%M)] FIM_ENCADEADO"
