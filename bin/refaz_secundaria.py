#!/home/mateus/env_transporte/bin/python
"""Refaz a 3a passada (secundaria) do catalogo v2 com o esquema MOTIVO PRIMEIRO, por decisao da
regra declarada em bench/mede_ordem_secundaria.py (22/11/2026: preenchimento 45/60 contra 32/60,
concordancia 28/46). Acrescenta linha nova por documento ao catalogo_v2.jsonl (a ultima vence) com
protocolo registrado. Retomavel: pula o que ja tem o protocolo."""
import json, os, sys, time
from pathlib import Path
os.environ.setdefault("TAXONOMIA_ACERVO", "subareas_transportes_v2.json")
sys.path.insert(0, str(Path(__file__).resolve().parent)); import catalogar_acervo as ca
assert list(ca.ESQUEMA_SECUNDARIA["properties"])[0] == "motivo"
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS"); F = Path("/home/mateus/base_conhecimento/catalogo_v2.jsonl")
PROT = "3a_passada_refeita_20261122_motivo_primeiro"
ult = {}
for l in open(F, encoding="utf-8"):
    d = json.loads(l); ult[d["arquivo"]] = d
alvo = [d for d in ult.values() if d.get("status") == "ok" and d.get("subarea_principal") not in (None, "fora_de_escopo")
        and d.get("protocolo_secundaria") != PROT]
print(f"{len(alvo)} documentos a refazer", flush=True); t0 = time.time()
with open(F, "a", encoding="utf-8") as f:
    for i, d in enumerate(alvo, 1):
        try:
            txt, _ = ca.primeiras_paginas(R/d["arquivo"])
            sec, mot = ca.detectar_secundaria(txt, Path(d["arquivo"]).name, d.get("titulo"), d["subarea_principal"], "qwen3:14b")
        except Exception as e:
            print(f"{i} ERRO {type(e).__name__} {d['arquivo'][-50:]}", flush=True); continue
        novo = {**d, "subarea_secundaria_antes": d.get("subarea_secundaria"), "subarea_secundaria": ";".join(sec) or None,
                "motivo_secundaria": mot, "protocolo_secundaria": PROT}
        f.write(json.dumps(novo, ensure_ascii=False) + "\n"); f.flush()
        if i % 50 == 0:
            r = (time.time() - t0) / i; print(f"{i}/{len(alvo)} {r:.1f} s/doc, resta ~{(len(alvo)-i)*r/60:.0f} min", flush=True)
print("FIM")
