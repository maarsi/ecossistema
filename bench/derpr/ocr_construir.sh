#!/bin/bash
set -u
E="$HOME/env_nemotron_ocr"
S="$HOME/ecossistema/bench/derpr/fonte_ocr/nemotron-ocr"
P="$HOME/ecossistema/bench/derpr/prevoo"
L="$P/ocr_construcao.log"; : > "$L"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

log "esperando terminar qualquer construcao anterior"
i=0; while pgrep -f "build-extension" >/dev/null 2>&1 && [ $i -lt 300 ]; do sleep 5; i=$((i+5)); done
log "  esperei ${i}s"

log "construindo a extensao com gcc-13 (o CUDA 12.4 nao aceita o gcc 15)"
cd "$S" || exit 1
if CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 MAX_JOBS=8 "$E/bin/python" scripts/build-extension.py >>"$L" 2>&1; then
  log "  extensao construida"
else
  log "  FALHOU. Ultimas linhas:"; tail -15 "$L" | sed 's/^/      /'
fi
find "$S" -name "*nemotron_ocr_cpp*.so" 2>/dev/null | head -2 | sed 's/^/  gerado: /' | tee -a "$L"

log "instalando o pacote"
if CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 "$E/bin/pip" install -q --no-build-isolation . >>"$L" 2>&1; then
  log "  instalado"; "$E/bin/pip" freeze > "$HOME/ecossistema/bench/derpr/ambientes/nemotron_ocr.txt"
else log "  instalacao falhou"; tail -8 "$L" | sed 's/^/      /'; fi

log "testando: importa e roda?"
"$E/bin/python" - <<'PY' >>"$L" 2>&1
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
tail -10 "$L" | grep -E "ocr |modulo|NAO IMPORTA" | tee -a "$L"

log "medindo acento, agora com as quatro ferramentas"
"$HOME/env_transporte/bin/python" - <<'PY' >>"$L" 2>&1
import json, pathlib, unicodedata
from collections import Counter
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
ref = json.loads((P/"camada_texto.json").read_text())["10"]
def ac(t): return [c for c in t if unicodedata.combining(unicodedata.normalize("NFD",c)[-1]) or c in "çÇ"]
A = ac(ref); cA = Counter(A)
print(f"\n  referencia: {len(A)} acentuados")
print(f"  {'ferramenta':<24}{'acentuados':>11}{'taxa':>7}{'tipos preservados':>20}")
for nome, arq in [("Docling (incumbente)","docling_p10.txt"),("Nemotron-3.5-Parse","parse_p10.txt"),
                  ("ocr-v2 ingles","ocr_en_p10.txt"),("ocr-v2 multilingue","ocr_multi_p10.txt")]:
    f = P/"saidas"/arq
    if not f.exists(): print(f"  {nome:<24}{'nao gerou':>11}"); continue
    cB = Counter(ac(f.read_text())); n=sum(cB.values())
    sob = sum(min(cB[k],v) for k,v in cA.items())
    print(f"  {nome:<24}{n:>11}{100*n/len(A):>6.0f}%{100*sob/len(A):>19.0f}%")
PY
tail -8 "$L"
log "FIM"
