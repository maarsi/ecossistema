"""Efeito da ORDEM das propriedades no esquema da 3a passada (secundaria). Mesmo prompt, mesma
taxonomia, mesmos 60 documentos; muda so a ordem: ANTIGA (subarea, confianca, motivo), usada no
catalogo v2 de 21/11, contra NOVA (motivo, subarea, confianca).
REGRA DE DECISAO, declarada antes de rodar: refazer a 3a passada nos 1.945 se |preenchimento
NOVA - ANTIGA| > 10 pontos OU concordancia entre as duas nas secundarias preenchidas < 70%."""
import copy, json, os, random, sys
from pathlib import Path
os.environ["TAXONOMIA_ACERVO"] = "subareas_transportes_v2.json"
sys.path.insert(0, "/home/mateus/ecossistema/bin"); import catalogar_acervo as ca
R = Path("/mnt/nvme_lexar/acervo/40 - REFERENCIAS")
NOVA = copy.deepcopy(ca.ESQUEMA_SECUNDARIA); assert list(NOVA["properties"])[0] == "motivo"
ANTIGA = {"type": "object", "properties": {"subarea": {"type": "string"},
          "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]}, "motivo": {"type": "string"}},
          "required": ["subarea", "confianca", "motivo"]}
cat = [json.loads(l) for l in open("/home/mateus/base_conhecimento/catalogo_v2.jsonl")]
ok = [d for d in cat if d.get("status") == "ok" and d.get("subarea_principal") not in (None, "fora_de_escopo")]
random.seed(2211); am = random.sample(ok, 60); res = []
for i, d in enumerate(am, 1):
    txt, _ = ca.primeiras_paginas(R/d["arquivo"]); lin = {"arquivo": d["arquivo"], "catalogo": d.get("subarea_secundaria")}
    for nome, esq in (("antiga", ANTIGA), ("nova", NOVA)):
        ca.ESQUEMA_SECUNDARIA = esq
        sec, mot = ca.detectar_secundaria(txt, Path(d["arquivo"]).name, d.get("titulo"), d["subarea_principal"], "qwen3:14b")
        lin[nome] = sec[0] if sec else None
    res.append(lin); print(f"{i}/60 cat={lin['catalogo']} antiga={lin['antiga']} nova={lin['nova']}", flush=True)
pa = sum(1 for r in res if r["antiga"]); pn = sum(1 for r in res if r["nova"]); pc = sum(1 for r in res if r["catalogo"])
amb = [r for r in res if r["antiga"] or r["nova"]]; conc = sum(1 for r in amb if r["antiga"] == r["nova"])
rep = sum(1 for r in res if r["antiga"] == (r["catalogo"].split(";")[0] if r["catalogo"] else None))
print(f"\npreenchimento: catalogo {pc}/60, antiga {pa}/60, nova {pn}/60")
print(f"concordancia antiga x nova onde alguma preencheu: {conc}/{len(amb)}")
print(f"reprodutibilidade antiga x catalogo (mesmo esquema, outra execucao): {rep}/60")
refazer = abs(pn - pa) / 60 > 0.10 or (amb and conc / len(amb) < 0.70)
print("DECISAO PELA REGRA DECLARADA:", "REFAZER a 3a passada" if refazer else "MANTER")
json.dump({"linhas": res, "refazer": refazer}, open("/home/mateus/ecossistema/bench/resultados/20261122_ordem_secundaria.json", "w"), ensure_ascii=False, indent=1)
print("FIM")
