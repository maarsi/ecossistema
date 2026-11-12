#!/bin/bash
set -u
P="$HOME/ecossistema/bench/derpr/prevoo"
L="$P/prevoo2.log"; : > "$L"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

log "===== CORRECAO 1: hatchling e o pacote do ocr-v2 ====="
"$HOME/env_nemotron_ocr/bin/pip" install -q hatchling >>"$L" 2>&1
if (cd "$HOME/ecossistema/bench/derpr/fonte_ocr/nemotron-ocr" && \
    "$HOME/env_nemotron_ocr/bin/pip" install -q --no-build-isolation . >>"$L" 2>&1); then
  log "  pacote instalado"
  "$HOME/env_nemotron_ocr/bin/pip" freeze > "$HOME/ecossistema/bench/derpr/ambientes/nemotron_ocr.txt"
else log "  FALHOU de novo:"; tail -12 "$L" | sed 's/^/      /'; fi

log "===== CORRECAO 2: Docling pagina a pagina, para a comparacao ser justa ====="
"$HOME/env_transporte/bin/python" - <<'PY' 2>&1 | grep -viE "RapidOCR|provider_config|onnxruntime|it/s\]$|Loading weights" | tee -a "$HOME/ecossistema/bench/derpr/prevoo/prevoo2.log"
import pymupdf, pathlib
from docling.document_converter import DocumentConverter
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
d = pymupdf.open(str(pathlib.Path.home()/"ecossistema/bench/dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf"))
conv = DocumentConverter()
for pg in (10, 21, 13):
    uma = pymupdf.open(); uma.insert_pdf(d, from_page=pg-1, to_page=pg-1)
    f = P/f"p{pg:02d}.pdf"; uma.save(str(f))
    try:
        t = conv.convert(str(f)).document.export_to_markdown()
    except Exception as e:
        t = ""; print(f"  docling pagina {pg} FALHOU: {type(e).__name__}")
    (P/f"saidas/docling_p{pg:02d}.txt").write_text(t)
    print(f"  docling pagina {pg}: {len(t)} caracteres")
PY

log "===== PASSO 5 REFEITO: nemotron-ocr-v2 ====="
"$HOME/env_nemotron_ocr/bin/python" - <<'PY' 2>&1 | grep -viE "warning|hf_token|it/s\]$" | tail -12 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/prevoo2.log"
import pathlib, time
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
try:
    from nemotron_ocr.inference.pipeline_v2 import NemotronOCRV2
except Exception as e:
    print(f"  pacote nao importa: {type(e).__name__}: {e}"); raise SystemExit
for lang, rot in (("en","ingles"), ("multi","multilingue")):
    try:
        ocr = NemotronOCRV2(lang=lang)
        for pg in (10, 21, 13):
            t0=time.time(); pr = ocr(str(P/f"paginas/pagina_{pg:02d}.png"))
            txt = " ".join(x["text"] for x in pr)
            (P/f"saidas/ocr_{lang}_p{pg:02d}.txt").write_text(txt)
            print(f"  ocr {rot} p{pg}: {len(txt)} caracteres, {len(pr)} blocos, {time.time()-t0:.0f}s")
    except Exception as e:
        print(f"  ocr {rot} FALHOU: {type(e).__name__}: {str(e)[:200]}")
PY

log "===== MEDICAO CORRIGIDA: pagina 10, todos contra a mesma referencia ====="
"$HOME/env_transporte/bin/python" - <<'PY' 2>&1 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/prevoo2.log"
import json, pathlib, unicodedata
from collections import Counter
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
ref = json.loads((P/"camada_texto.json").read_text())["10"]
ac = lambda t: [c for c in t if unicodedata.combining(unicodedata.normalize("NFD",c)[-1]) or c in "cCçÇ" and c in "çÇ"]
A = ac(ref); cA = Counter(A)
print(f"  referencia: {len(A)} acentuados  {dict(cA.most_common(6))}\n")
print(f"  {'ferramenta':<24}{'acentuados':>11}{'taxa':>7}   acertou por tipo")
print("  "+"-"*72)
for nome, arq in [("Docling (incumbente)","docling_p10.txt"),("Nemotron-3.5-Parse","parse_p10.txt"),
                  ("ocr-v2 ingles","ocr_en_p10.txt"),("ocr-v2 multilingue","ocr_multi_p10.txt")]:
    f = P/"saidas"/arq
    if not f.exists(): print(f"  {nome:<24}{'nao gerou':>11}"); continue
    B = ac(f.read_text()); cB = Counter(B)
    taxa = 100*len(B)/len(A) if A else 0
    # por tipo: quanto de cada acento sobreviveu, limitado a 100% por tipo
    sobrev = sum(min(cB[k], v) for k,v in cA.items())
    print(f"  {nome:<24}{len(B):>11}{taxa:>6.0f}%   {100*sobrev/len(A):.0f}% dos tipos preservados")
PY
log "===== FIM ====="
