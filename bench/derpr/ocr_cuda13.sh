#!/bin/bash
set -u
E="$HOME/env_nemotron_ocr"
S="$HOME/ecossistema/bench/derpr/fonte_ocr/nemotron-ocr"
P="$HOME/ecossistema/bench/derpr/prevoo"
CU="$HOME/env_cuopt/lib/python3.14/site-packages/nvidia/cu13"
L="$P/ocr_cuda13.log"; : > "$L"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

log "CONTEXTO: o nvcc do sistema e 12.4 e nao conhece a arquitetura Blackwell (compute_120)"
log "da RTX 5060 Ti. O toolkit CUDA 13.4 que existe dentro do env_cuopt compila para"
log "sm_120, verificado por teste. Para o par ficar consistente, o torch deste ambiente"
log "passa de CUDA 12.8 para CUDA 13.0. Dependencia so de CONSTRUCAO: o .so gerado nao"
log "precisa do toolkit depois."

log "PASSO 1: trocando o torch para a serie CUDA 13"
if "$E/bin/pip" install -q torch==2.14.0+cu130 torchvision --index-url https://download.pytorch.org/whl/cu130 >>"$L" 2>&1; then
  log "  torch agora: $("$E/bin/python" -c 'import torch;print(torch.__version__)' 2>/dev/null)"
  log "  arquiteturas suportadas: $("$E/bin/python" -c 'import torch;print(torch.cuda.get_arch_list())' 2>/dev/null)"
else log "  FALHOU"; tail -8 "$L" | sed 's/^/     /'; exit 1; fi

log "PASSO 2: compilando a extensao com nvcc 13.4 e gcc-13"
cd "$S" || exit 1
rm -rf build
if CUDA_HOME="$CU" PATH="$CU/bin:$PATH" CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 \
   TORCH_CUDA_ARCH_LIST="12.0" MAX_JOBS=8 \
   "$E/bin/python" scripts/build-extension.py >>"$L" 2>&1; then
  log "  extensao CONSTRUIDA"
else
  log "  FALHOU. Erro relevante:"
  grep -iE "nvcc fatal|error:|Error [0-9]|RuntimeError" "$L" | tail -6 | sed 's/^/     /'
fi
find "$S" -name "*nemotron_ocr_cpp*.so" 2>/dev/null | head -2 | sed 's/^/  gerado: /' | tee -a "$L"

log "PASSO 3: instalando o pacote"
CUDA_HOME="$CU" PATH="$CU/bin:$PATH" CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 \
  "$E/bin/pip" install -q --no-build-isolation . >>"$L" 2>&1 \
  && { log "  instalado"; "$E/bin/pip" freeze > "$HOME/ecossistema/bench/derpr/ambientes/nemotron_ocr.txt"; } \
  || log "  instalacao falhou"

log "PASSO 4: importa e roda?"
"$E/bin/python" - <<'PY' 2>&1 | grep -viE "warning|hf_token|it/s\]" | tee -a "$HOME/ecossistema/bench/derpr/prevoo/ocr_cuda13.log"
import pathlib, time
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
try:
    from nemotron_ocr.inference.pipeline_v2 import NemotronOCRV2
    print("  modulo importa OK")
except Exception as e:
    print(f"  NAO IMPORTA: {type(e).__name__}: {str(e)[:220]}"); raise SystemExit
for lang, rot in (("en","ingles"), ("multi","multilingue")):
    try:
        ocr = NemotronOCRV2(lang=lang)
        for pg in (10,21,13):
            t0=time.time(); pr = ocr(str(P/f"paginas/pagina_{pg:02d}.png"))
            txt = " ".join(x["text"] for x in pr)
            (P/f"saidas/ocr_{lang}_p{pg:02d}.txt").write_text(txt)
            print(f"  ocr {rot} p{pg}: {len(txt)} caracteres, {len(pr)} blocos, {time.time()-t0:.0f}s")
    except Exception as e:
        print(f"  ocr {rot} FALHOU: {type(e).__name__}: {str(e)[:220]}")
PY

log "PASSO 5: taxa de acento"
"$HOME/env_transporte/bin/python" - <<'PY' 2>&1 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/ocr_cuda13.log"
import json, pathlib, unicodedata
from collections import Counter
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
ref = json.loads((P/"camada_texto.json").read_text())["10"]
def ac(t): return [c for c in t if unicodedata.combining(unicodedata.normalize("NFD",c)[-1]) or c in "çÇ"]
A = ac(ref); cA = Counter(A)
print(f"\n  referencia da pagina 10: {len(A)} caracteres acentuados")
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
