#!/bin/bash
set -u
B="$HOME/ecossistema/bench"; D="$B/derpr"
L="$D/resultados/bateria.log"; : > "$L"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
marco(){ echo "" | tee -a "$L"; log "===== $* ====="; }

marco "FASE 0: integridade e renderizacao"
for par in "suites/recuperacao_anuario_derpr.json:dde54454c84ddd7eadeb5b98d42657be4c901b67b6138d9b5419478adfe6c9e7" \
           "dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf:c19be5398997a7ae18117ac9cdd48ee866757a293652e5f4b26f7e689368649c"; do
  f="${par%%:*}"; e="${par##*:}"
  a=$(sha256sum "$B/$f" | cut -d' ' -f1)
  [ "$a" = "$e" ] && log "  confere: $f" || { log "  DIVERGE: $f -- PARANDO"; exit 1; }
done
"$HOME/env_transporte/bin/python" "$D/bat_render.py" 2>&1 | tee -a "$L"

for p in 1 2 3; do
  marco "PASSADA $p de 3"
  log "  bracos A e B: Docling sem e com OCR"
  "$HOME/env_transporte/bin/python" "$D/bat_texto_docling.py" $p 2>&1 | grep -viE "RapidOCR|provider_config|it/s\]|Loading weights" | tee -a "$L"
  log "  braco G: Nemotron-3.5-Parse"
  "$HOME/env_nemotron_parse/bin/python" "$D/bat_texto_parse.py" $p 2>&1 | grep -viE "warning|hf_token|it/s\]" | tail -3 | tee -a "$L"
  log "  bracos A, B e G: indexacao e consulta com o MESMO embedder"
  "$HOME/env_transporte/bin/python" "$D/bat_rank_texto.py" $p 2>&1 | tee -a "$L"
  log "  braco C: ColQwen2.5"
  "$HOME/env_colpali/bin/python" "$D/bat_rank_colqwen.py" $p 2>&1 | grep -viE "warning|hf_token|it/s\]" | tail -4 | tee -a "$L"
  log "  bracos D e E: nemotron embed-vl e reordenador"
  "$HOME/env_nemotron_vl/bin/python" "$D/bat_rank_nemotron.py" $p 2>&1 | grep -viE "warning|hf_token|it/s\]" | tail -4 | tee -a "$L"
  nvidia-smi --query-gpu=memory.used --format=csv,noheader | sed 's/^/  VRAM em uso: /' | tee -a "$L"
done

marco "FASE 6: pontuacao"
"$HOME/env_transporte/bin/python" "$D/bat_pontuar.py" 2>&1 | tee -a "$L"
marco "FIM DA BATERIA"
