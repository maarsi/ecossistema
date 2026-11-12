#!/bin/bash
# Instalacao dos ambientes e modelos da bateria do anuario DER-PR.
# NAO usa "set -e" de proposito: se um ambiente falhar, os outros continuam,
# para que todos os problemas aparecam numa rodada so.
set -u

BASE="$HOME/ecossistema/bench"
TRAB="$BASE/derpr"
LOG="$TRAB/instalacao.log"
EST="$TRAB/estado.txt"
PY312="$HOME/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12"

mkdir -p "$TRAB"/{ambientes,vetores,prevoo,manifestos,indices,resultados,licencas}

log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
marco(){ echo "" | tee -a "$LOG"; log "===== $* ====="; }
estado(){ echo "$(date +%H:%M:%S) | $*" >> "$EST"; }

echo "===== INICIO $(date +'%d/%m %H:%M:%S') =====" >> "$LOG"
: > "$EST"

# ---------------------------------------------------------------- FASE 0
marco "FASE 0: conferindo que nada foi alterado"
declare -A ESPERADO=(
 ["suites/recuperacao_anuario_derpr.json"]="dde54454c84ddd7eadeb5b98d42657be4c901b67b6138d9b5419478adfe6c9e7"
 ["dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf"]="c19be5398997a7ae18117ac9cdd48ee866757a293652e5f4b26f7e689368649c"
 ["suites/recuperacao_anuario_derpr_ADENDO_04.json"]="f0c4a8703428c405b002aa4433821e6cd2aaddd2a9c8400e3d0066b9992dc7bc"
)
FALHA_HASH=0
for f in "${!ESPERADO[@]}"; do
  a=$(sha256sum "$BASE/$f" 2>/dev/null | cut -d' ' -f1)
  if [ "$a" = "${ESPERADO[$f]}" ]; then log "  confere: $f"
  else log "  DIVERGE: $f"; log "    esperado ${ESPERADO[$f]}"; log "    obtido   ${a:-arquivo ausente}"; FALHA_HASH=1; fi
done
if [ "$FALHA_HASH" = "1" ]; then
  log "PARANDO: um arquivo do pre-registro mudou. Nao vou corrigir arquivo nenhum."
  estado "PARADO na fase 0: hash divergente"
  exit 1
fi
estado "fase 0 OK: pre-registro e corpus intactos"

# ---------------------------------------------------------------- FASE 1
marco "FASE 1: lendo a licenca de cada modelo na fonte"
MODELOS=(
 "nvidia/llama-nemotron-embed-vl-1b-v2"
 "nvidia/llama-nemotron-rerank-vl-1b-v2"
 "nvidia/nemotron-colembed-vl-4b-v2"
 "nvidia/Nemotron-3.5-Parse"
 "nvidia/nemotron-ocr-v2"
 "vidore/colqwen2.5-v0.2"
)
: > "$TRAB/licencas/licencas.txt"
for m in "${MODELOS[@]}"; do
  j=$(curl -sS --max-time 45 "https://huggingface.co/api/models/$m" 2>/dev/null)
  lic=$(echo "$j" | grep -oE '"license"[^,]*' | head -1 | cut -d'"' -f4)
  gated=$(echo "$j" | grep -oE '"gated":[^,}]*' | head -1 | cut -d: -f2 | tr -d ' "')
  [ -z "$lic" ] && lic="(nao declarada na API)"
  [ -z "$gated" ] && gated="?"
  log "  $m"
  log "      licenca: $lic   acesso restrito: $gated"
  echo "$m | $lic | gated=$gated" >> "$TRAB/licencas/licencas.txt"
done
estado "fase 1 OK: licencas lidas em licencas/licencas.txt"

# ---------------------------------------------------------------- FASE 2
marco "FASE 2: criando os ambientes isolados"
if [ ! -x "$PY312" ]; then
  log "PARANDO: nao achei o Python 3.12 em $PY312"
  estado "PARADO na fase 2: Python 3.12 ausente"; exit 1
fi
log "  Python 3.12: $($PY312 --version)"
log "  PROIBIDO tocar em ~/TransportMCP/.venv e em ~/env_transporte"

criar(){ # nome, pacotes...
  local nome="$1"; shift
  local dir="$HOME/env_$nome"
  if [ -f "$dir/.pronto" ]; then log "  $nome: ja estava pronto, pulando"; return 0; fi
  log "  $nome: criando ambiente"
  "$PY312" -m venv "$dir" >>"$LOG" 2>&1 || { log "  $nome: FALHOU ao criar o ambiente"; estado "fase 2: $nome FALHOU (venv)"; return 1; }
  "$dir/bin/pip" install -q --upgrade pip setuptools wheel >>"$LOG" 2>&1
  log "  $nome: instalando $*  (pode demorar varios minutos)"
  if "$dir/bin/pip" install -q "$@" >>"$LOG" 2>&1; then
    "$dir/bin/pip" freeze > "$TRAB/ambientes/$nome.txt"
    touch "$dir/.pronto"
    log "  $nome: PRONTO ($(wc -l < "$TRAB/ambientes/$nome.txt") pacotes)"
    estado "fase 2: $nome pronto"
  else
    log "  $nome: FALHOU na instalacao. Ultimas linhas do erro:"
    tail -12 "$LOG" | sed 's/^/        /'
    estado "fase 2: $nome FALHOU (pip)"
    return 1
  fi
}

criar nemotron_vl    torch torchvision transformers accelerate sentence-transformers pillow einops timm huggingface_hub
criar nemotron_parse torch torchvision transformers accelerate pillow einops timm huggingface_hub
criar colpali        colpali-engine torch torchvision pillow huggingface_hub

log "  nemotron_ocr: o cartao do modelo pede torch com CUDA 12.8; instalando do indice proprio"
if [ ! -f "$HOME/env_nemotron_ocr/.pronto" ]; then
  "$PY312" -m venv "$HOME/env_nemotron_ocr" >>"$LOG" 2>&1
  "$HOME/env_nemotron_ocr/bin/pip" install -q --upgrade pip setuptools wheel >>"$LOG" 2>&1
  if "$HOME/env_nemotron_ocr/bin/pip" install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128 >>"$LOG" 2>&1 \
  && "$HOME/env_nemotron_ocr/bin/pip" install -q huggingface_hub pillow numpy >>"$LOG" 2>&1; then
    "$HOME/env_nemotron_ocr/bin/pip" freeze > "$TRAB/ambientes/nemotron_ocr.txt"
    touch "$HOME/env_nemotron_ocr/.pronto"
    log "  nemotron_ocr: base PRONTA (o pacote do modelo vem na fase 3, do repositorio)"
    estado "fase 2: nemotron_ocr base pronta"
  else
    log "  nemotron_ocr: FALHOU"; tail -12 "$LOG" | sed 's/^/        /'
    estado "fase 2: nemotron_ocr FALHOU"
  fi
else log "  nemotron_ocr: ja estava pronto, pulando"; fi

# ---------------------------------------------------------------- FASE 3
marco "FASE 3: baixando os pesos dos modelos"
ANTES=$(du -sm "$HOME/.cache/huggingface" 2>/dev/null | cut -f1)
baixar(){ # ambiente, repo
  local amb="$1" repo="$2"
  local py="$HOME/env_$amb/bin/python"
  [ -x "$py" ] || { log "  pulando $repo: ambiente $amb nao existe"; return 1; }
  log "  baixando $repo  (varios GB, pode demorar)"
  if "$py" - <<PY >>"$LOG" 2>&1
from huggingface_hub import snapshot_download
snapshot_download("$repo", ignore_patterns=["*.onnx","*.msgpack","*.h5"])
PY
  then log "  $repo: OK"; estado "fase 3: $repo baixado"
  else log "  $repo: FALHOU"; tail -8 "$LOG" | sed 's/^/        /'; estado "fase 3: $repo FALHOU"; fi
}
baixar nemotron_vl    "nvidia/llama-nemotron-embed-vl-1b-v2"
baixar nemotron_vl    "nvidia/llama-nemotron-rerank-vl-1b-v2"
baixar nemotron_parse "nvidia/Nemotron-3.5-Parse"
baixar nemotron_ocr   "nvidia/nemotron-ocr-v2"
baixar colpali        "vidore/colqwen2.5-v0.2"
log "  o braco F (colembed-vl-4b) NAO foi baixado: depende da licenca lida na fase 1"
DEPOIS=$(du -sm "$HOME/.cache/huggingface" 2>/dev/null | cut -f1)
log "  disco usado pelos modelos nesta rodada: $(( ${DEPOIS:-0} - ${ANTES:-0} )) MB"
log "  espaco livre: $(df -h "$HOME" | tail -1 | awk '{print $4}')"

marco "FIM DA INSTALACAO"
log "Resumo do que aconteceu:"
cat "$EST" | sed 's/^/  /' | tee -a "$LOG"
estado "ROTEIRO TERMINADO"
