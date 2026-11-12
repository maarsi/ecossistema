#!/bin/bash
set -u
TRAB="$HOME/ecossistema/bench/derpr"
P="$TRAB/prevoo"
LOG="$P/prevoo.log"
PDF="$HOME/ecossistema/bench/dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf"
CACHE="$HOME/.cache/huggingface/hub"
mkdir -p "$P"/{paginas,saidas}
: > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
marco(){ echo "" | tee -a "$LOG"; log "===== $* ====="; }

marco "PASSO 1: instalando o pacote do nemotron-ocr-v2"
REPO=$(find "$CACHE/models--nvidia--nemotron-ocr-v2/snapshots" -maxdepth 1 -type d | tail -1)
if [ ! -f "$HOME/env_nemotron_ocr/.pacote_pronto" ]; then
  rm -rf "$TRAB/fonte_ocr"; mkdir -p "$TRAB/fonte_ocr"
  cp -rL "$REPO/nemotron-ocr" "$TRAB/fonte_ocr/" 2>/dev/null
  if (cd "$TRAB/fonte_ocr/nemotron-ocr" && "$HOME/env_nemotron_ocr/bin/pip" install -q --no-build-isolation . >>"$LOG" 2>&1); then
    touch "$HOME/env_nemotron_ocr/.pacote_pronto"; log "  pacote instalado"
  else log "  FALHOU ao instalar o pacote. Ultimas linhas:"; tail -15 "$LOG" | sed 's/^/      /'; fi
else log "  ja estava instalado"; fi

marco "PASSO 2: renderizando as 3 paginas"
"$HOME/env_transporte/bin/python" - <<PY 2>&1 | tee -a "$LOG"
import pymupdf, json, pathlib
d = pymupdf.open("$PDF")
ref = {}
for pg in (10, 21, 13):
    p = d[pg-1]
    p.get_pixmap(dpi=200).save("$P/paginas/pagina_%02d.png" % pg)
    ref[pg] = p.get_text()
    print(f"  pagina {pg}: imagem gravada, camada de texto com {len(ref[pg].strip())} caracteres")
pathlib.Path("$P/camada_texto.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1))
PY

marco "PASSO 3: Docling com OCR, a referencia conhecida (braco B)"
"$HOME/env_transporte/bin/python" - <<PY 2>&1 | tail -6 | tee -a "$LOG"
import pymupdf, json, pathlib
from docling.document_converter import DocumentConverter
d = pymupdf.open("$PDF"); novo = pymupdf.open()
for pg in (10, 21, 13): novo.insert_pdf(d, from_page=pg-1, to_page=pg-1)
novo.save("$P/tres_paginas.pdf")
try:
    r = DocumentConverter().convert("$P/tres_paginas.pdf")
    t = r.document.export_to_markdown()
    pathlib.Path("$P/saidas/docling.txt").write_text(t)
    print(f"  Docling: {len(t)} caracteres")
except Exception as e:
    print(f"  Docling FALHOU: {type(e).__name__}: {e}")
PY

marco "PASSO 4: Nemotron-3.5-Parse (braco G)"
"$HOME/env_nemotron_parse/bin/python" - <<'PY' 2>&1 | grep -viE "warning|hf_token|it/s\]$" | tail -12 | tee -a "$LOG"
import torch, pathlib, time
from PIL import Image
from transformers import AutoModel, AutoProcessor, GenerationConfig
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
M = "nvidia/Nemotron-3.5-Parse"
TASK = "</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>"
try:
    mod = AutoModel.from_pretrained(M, trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval()
    proc = AutoProcessor.from_pretrained(M, trust_remote_code=True)
    gen = GenerationConfig.from_pretrained(M); gen.max_new_tokens = 8744
    for pg in (10, 21, 13):
        t0 = time.time()
        img = Image.open(P/f"paginas/pagina_{pg:02d}.png").convert("RGB")
        inp = proc(images=[img], text=TASK, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            out = mod.generate(**inp, generation_config=gen)
        txt = proc.batch_decode(out, skip_special_tokens=False)[0]
        (P/f"saidas/parse_p{pg:02d}.txt").write_text(txt)
        print(f"  parse pagina {pg}: {len(txt)} caracteres em {time.time()-t0:.0f}s")
except Exception as e:
    print(f"  Nemotron-3.5-Parse FALHOU: {type(e).__name__}: {str(e)[:250]}")
PY

marco "PASSO 5: nemotron-ocr-v2, as duas variantes (braco H)"
"$HOME/env_nemotron_ocr/bin/python" - <<'PY' 2>&1 | grep -viE "warning|hf_token" | tail -14 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/prevoo.log"
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
            t0 = time.time()
            pr = ocr(str(P/f"paginas/pagina_{pg:02d}.png"))
            txt = " ".join(x["text"] for x in pr)
            (P/f"saidas/ocr_{lang}_p{pg:02d}.txt").write_text(txt)
            print(f"  ocr {rot} pagina {pg}: {len(txt)} caracteres, {len(pr)} blocos, {time.time()-t0:.0f}s")
    except Exception as e:
        print(f"  ocr {rot} FALHOU: {type(e).__name__}: {str(e)[:200]}")
PY

marco "PASSO 6: medindo a taxa de acento na pagina 10"
"$HOME/env_transporte/bin/python" - <<'PY' 2>&1 | tee -a "$HOME/ecossistema/bench/derpr/prevoo/prevoo.log"
import json, pathlib, unicodedata
P = pathlib.Path.home()/"ecossistema/bench/derpr/prevoo"
ref = json.loads((P/"camada_texto.json").read_text())["10"]
def acentos(t):
    return [c for c in t if unicodedata.combining(unicodedata.normalize("NFD", c)[-1]) or c in "çÇ"]
A = acentos(ref)
from collections import Counter
print(f"  referencia (camada de texto do PDF): {len(A)} caracteres acentuados")
print(f"    mais comuns: {dict(Counter(A).most_common(6))}")
print()
print(f"  {'ferramenta':<22}{'acentuados':>12}{'taxa':>9}")
print("  " + "-"*44)
for nome, arq in [("Docling (referencia)","docling.txt"),("Nemotron-3.5-Parse","parse_p10.txt"),
                  ("ocr-v2 ingles","ocr_en_p10.txt"),("ocr-v2 multilingue","ocr_multi_p10.txt")]:
    f = P/"saidas"/arq
    if not f.exists(): print(f"  {nome:<22}{'nao gerou':>12}"); continue
    B = acentos(f.read_text())
    taxa = 100*len(B)/len(A) if A else 0
    print(f"  {nome:<22}{len(B):>12}{taxa:>8.0f}%")
print()
print("  ATENCAO: esta taxa compara QUANTIDADE de acentos, nao se estao nas palavras certas.")
print("  Ela detecta quem perde acento, nao quem troca. A conferencia do Mateus decide.")
PY

marco "FIM DO PRE-VOO"
log "saidas em: $P/saidas/"
ls -la "$P/saidas/" 2>/dev/null | tail -n +2 | awk '{printf "  %8s  %s\n", $5, $9}' | tee -a "$LOG"
