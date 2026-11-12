#!/bin/bash
set -u
E="$HOME/env_nemotron_ocr"
S="$HOME/ecossistema/bench/derpr/fonte_ocr/nemotron-ocr"
P="$HOME/ecossistema/bench/derpr/prevoo"
CU="$HOME/env_cuopt/lib/python3.14/site-packages/nvidia/cu13"
L="$P/ocr_final.log"; : > "$L"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

log "TENTATIVA FINAL. Historico das falhas, para quem ler depois:"
log "  1a: gcc 15 do sistema recusado pelo CUDA 12.4 (exige < 14)"
log "  2a: nvcc 12.4 nao conhece compute_120 (Blackwell). Pacote pip de nvcc so traz ptxas."
log "  3a: nvcc 13.4 resolveu o CUDA, mas o torch 2.14 traz cabecalhos C++20 e o pacote"
log "      compila com -std=c++17. Erro em operator!= e at::symint."
log "  AGORA: torch 2.9.1+cu130. Mantem o CUDA 13 (Blackwell) e volta a geracao C++17"
log "      que o pacote espera. Se falhar, o braco H e reportado como NAO EXECUTADO."

log "PASSO 1: torch 2.9.1 com CUDA 13"
if "$E/bin/pip" install -q torch==2.9.1+cu130 torchvision --index-url https://download.pytorch.org/whl/cu130 >>"$L" 2>&1; then
  log "  torch: $("$E/bin/python" -c 'import torch;print(torch.__version__)' 2>/dev/null)"
  log "  arquiteturas: $("$E/bin/python" -c 'import torch;print(torch.cuda.get_arch_list())' 2>/dev/null)"
else log "  FALHOU ao instalar o torch"; exit 1; fi

log "PASSO 2: compilando"
cd "$S" || exit 1; rm -rf build
if CUDA_HOME="$CU" PATH="$CU/bin:$PATH" CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 \
   TORCH_CUDA_ARCH_LIST="12.0" MAX_JOBS=8 \
   "$E/bin/python" scripts/build-extension.py >>"$L" 2>&1; then
  log "  extensao CONSTRUIDA"
else
  log "  FALHOU. Erro relevante:"
  grep -iE "nvcc fatal|error:|RuntimeError" "$L" | tail -4 | sed 's/^/     /'
fi
find "$S" -name "*nemotron_ocr_cpp*.so" 2>/dev/null | head -1 | sed 's/^/  gerado: /' | tee -a "$L"

log "PASSO 3: instalando"
CUDA_HOME="$CU" PATH="$CU/bin:$PATH" CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 \
  "$E/bin/pip" install -q --no-build-isolation . >>"$L" 2>&1 \
  && { log "  instalado"; "$E/bin/pip" freeze > "$HOME/ecossistema/bench/derpr/ambientes/nemotron_ocr.txt"; } \
  || log "  instalacao falhou"

log "PASSO 4: roda?"
"$E/bin/python" - <<'PY' 2>&1 | grep -viE "warning|hf_token|it/s\]" | tee -a "$HOME/ecossistema/bench/derpr/prevoo/ocr_final.log"
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

log "PASSO 5: taxa de acento, quadro final do pre-voo"
"$HOME/env_transporte/bin/python" - <<'PY' 2>&1 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/ocr_final.log"
import json, pathlib, unicodedata
from collections import Counter
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
ref = json.loads((P/"camada_texto.json").read_text())["10"]
def ac(t): return [c for c in t if unicodedata.combining(unicodedata.normalize("NFD",c)[-1]) or c in "çÇ"]
A = ac(ref); cA = Counter(A)
print(f"\n  referencia da pagina 10: {len(A)} caracteres acentuados")
print(f"  {'ferramenta':<24}{'acentuados':>11}{'taxa':>7}{'tipos':>8}  veredito")
print("  "+"-"*66)
for nome, arq in [("Docling (incumbente)","docling_p10.txt"),("Nemotron-3.5-Parse","parse_p10.txt"),
                  ("ocr-v2 ingles","ocr_en_p10.txt"),("ocr-v2 multilingue","ocr_multi_p10.txt")]:
    f = P/"saidas"/arq
    if not f.exists(): print(f"  {nome:<24}{'nao gerou':>11}{'':>7}{'':>8}  NAO EXECUTADO"); continue
    cB = Counter(ac(f.read_text())); n=sum(cB.values())
    sob = 100*sum(min(cB[k],v) for k,v in cA.items())/len(A)
    v = "APROVADO" if sob>=95 else ("COM RESSALVA" if sob>=80 else "REPROVADO")
    print(f"  {nome:<24}{n:>11}{100*n/len(A):>6.0f}%{sob:>7.0f}%  {v}")
PY
log "FIM"
