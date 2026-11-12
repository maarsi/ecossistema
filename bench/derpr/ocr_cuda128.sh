#!/bin/bash
set -u
E="$HOME/env_nemotron_ocr"
S="$HOME/ecossistema/bench/derpr/fonte_ocr/nemotron-ocr"
P="$HOME/ecossistema/bench/derpr/prevoo"
SHIM="$HOME/ecossistema/bench/derpr/cuda128"
L="$P/ocr_cuda128.log"; : > "$L"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

log "PASSO 1: nvcc 12.8 por pip, dentro do ambiente isolado"
"$E/bin/pip" install -q "nvidia-cuda-nvcc-cu12==12.8.93" "nvidia-cuda-cccl-cu12" >>"$L" 2>&1 \
  && log "  instalado" || { log "  FALHOU"; tail -6 "$L" | sed 's/^/     /'; }

log "PASSO 2: montando um CUDA_HOME proprio, sem mexer no do sistema"
NV="$E/lib/python3.12/site-packages/nvidia"
rm -rf "$SHIM"; mkdir -p "$SHIM"/{bin,include,lib64}
for d in cuda_nvcc cuda_runtime cuda_cccl cuda_nvrtc cublas; do
  [ -d "$NV/$d/bin" ]     && cp -rsn "$NV/$d/bin/."     "$SHIM/bin/"     2>/dev/null
  [ -d "$NV/$d/include" ] && cp -rsn "$NV/$d/include/." "$SHIM/include/" 2>/dev/null
  [ -d "$NV/$d/lib" ]     && cp -rsn "$NV/$d/lib/."     "$SHIM/lib64/"   2>/dev/null
done
[ -d "$NV/cuda_nvcc/nvvm" ] && ln -sfn "$NV/cuda_nvcc/nvvm" "$SHIM/nvvm"
if [ -x "$SHIM/bin/nvcc" ]; then
  log "  nvcc do shim: $("$SHIM/bin/nvcc" --version 2>/dev/null | grep release | sed 's/.*release //')"
else
  log "  nvcc do shim AUSENTE; abortando"; exit 1
fi

log "PASSO 3: recompilando a extensao"
cd "$S" || exit 1
rm -rf build
if CUDA_HOME="$SHIM" PATH="$SHIM/bin:$PATH" CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 \
   TORCH_CUDA_ARCH_LIST="12.0" MAX_JOBS=8 \
   "$E/bin/python" scripts/build-extension.py >>"$L" 2>&1; then
  log "  extensao CONSTRUIDA"
else
  log "  FALHOU. Erro relevante:"
  grep -iE "nvcc fatal|error:|Error [0-9]" "$L" | tail -5 | sed 's/^/     /' | tee -a "$L"
fi
find "$S" -name "*nemotron_ocr_cpp*.so" 2>/dev/null | head -2 | sed 's/^/  gerado: /' | tee -a "$L"

log "PASSO 4: instalando"
CUDA_HOME="$SHIM" PATH="$SHIM/bin:$PATH" CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 \
  "$E/bin/pip" install -q --no-build-isolation . >>"$L" 2>&1 \
  && { log "  instalado"; "$E/bin/pip" freeze > "$HOME/ecossistema/bench/derpr/ambientes/nemotron_ocr.txt"; } \
  || log "  instalacao falhou"

log "PASSO 5: importa e roda?"
"$E/bin/python" - <<'PY' 2>&1 | grep -viE "warning|hf_token|it/s\]" | tee -a "$HOME/ecossistema/bench/derpr/prevoo/ocr_cuda128.log"
import pathlib, time
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
try:
    from nemotron_ocr.inference.pipeline_v2 import NemotronOCRV2
    print("  modulo importa OK")
except Exception as e:
    print(f"  NAO IMPORTA: {type(e).__name__}: {str(e)[:200]}"); raise SystemExit
for lang, rot in (("en","ingles"), ("multi","multilingue")):
    try:
        ocr = NemotronOCRV2(lang=lang)
        for pg in (10,21,13):
            t0=time.time(); pr = ocr(str(P/f"paginas/pagina_{pg:02d}.png"))
            txt = " ".join(x["text"] for x in pr)
            (P/f"saidas/ocr_{lang}_p{pg:02d}.txt").write_text(txt)
            print(f"  ocr {rot} p{pg}: {len(txt)} caracteres, {len(pr)} blocos, {time.time()-t0:.0f}s")
    except Exception as e:
        print(f"  ocr {rot} FALHOU: {type(e).__name__}: {str(e)[:200]}")
PY

log "PASSO 6: taxa de acento das quatro ferramentas"
"$HOME/env_transporte/bin/python" - <<'PY' 2>&1 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/ocr_cuda128.log"
import json, pathlib, unicodedata
from collections import Counter
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
ref = json.loads((P/"camada_texto.json").read_text())["10"]
def ac(t): return [c for c in t if unicodedata.combining(unicodedata.normalize("NFD",c)[-1]) or c in "çÇ"]
A = ac(ref); cA = Counter(A)
print(f"  referencia da pagina 10: {len(A)} caracteres acentuados")
print(f"  {'ferramenta':<24}{'acentuados':>11}{'taxa':>7}{'tipos preservados':>20}")
print("  "+"-"*62)
for nome, arq in [("Docling (incumbente)","docling_p10.txt"),("Nemotron-3.5-Parse","parse_p10.txt"),
                  ("ocr-v2 ingles","ocr_en_p10.txt"),("ocr-v2 multilingue","ocr_multi_p10.txt")]:
    f = P/"saidas"/arq
    if not f.exists(): print(f"  {nome:<24}{'nao gerou':>11}"); continue
    cB = Counter(ac(f.read_text())); n=sum(cB.values())
    sob = sum(min(cB[k],v) for k,v in cA.items())
    print(f"  {nome:<24}{n:>11}{100*n/len(A):>6.0f}%{100*sob/len(A):>19.0f}%")
PY
log "FIM"
