#!/home/mateus/env_transporte/bin/python
"""Monta revisao_taxonomia_v2.csv e .xlsx a partir da v1, do catalogo v2 e das passadas
auxiliares, segundo a especificacao de Mateus de 21/11/2026 (22 subareas).

Ordem das regras, cada uma registrada em origem_classificacao:
  1. modelo_texto_v2            classificacao do catalogo v2 pelo texto
  2. inferencia_caminho_titulo  sem texto (pendente_ocr, erro_leitura): caminho + nome
  3. correcao_dirigida          passadas medidas (ex.: ferrovia), de correcoes_v2.jsonl
  4. regra_pasta_especificacao  pastas que a especificacao atribui explicitamente
  5. revisao_manual             REVISAO_subarea preenchida por Mateus vence tudo
Uso: taxonomia_v2_final.py [--parcial]   (--parcial aceita catalogo v2 incompleto, para teste)
"""
import csv, json, sys
from collections import Counter
from pathlib import Path
BC = Path("/home/mateus/base_conhecimento"); ECO = Path("/home/mateus/ecossistema")
TAX = json.loads((ECO/"config/subareas_transportes_v2.json").read_text())
SUB = TAX["subareas"]; PARCIAL = "--parcial" in sys.argv

def jsonl(p):
    d = {}
    if p.exists():
        for l in open(p, encoding="utf-8"):
            if l.strip():
                x = json.loads(l); d[x["arquivo"]] = x       # a ultima linha vence
    return d

v1 = list(csv.DictReader(open(BC/"revisao_taxonomia_20261118.csv", encoding="utf-8-sig")))
v2 = jsonl(BC/"catalogo_v2.jsonl"); st = jsonl(BC/"sem_texto_v2.jsonl"); co = jsonl(BC/"correcoes_v2.jsonl")
oc = jsonl(BC/"catalogo_ocr_v2.jsonl")    # classificacao PELO TEXTO do OCR de 21/11 (os sem texto)
dup = {r["rel"]: r for r in json.loads((BC/"duplicatas_v2.json").read_text())["registros"]}
assert len(v1) == 1945, len(v1)
faltam = [r["arquivo"] for r in v1 if r["arquivo"] not in v2]
if faltam and not PARCIAL:
    sys.exit(f"ERRO: {len(faltam)} arquivos da v1 sem linha no catalogo v2. Usar --parcial so para teste.")

def secs(*listas, excluir=None):
    vistos, out = {excluir}, []
    for l in listas:
        for s in (l or "").split(";"):
            s = s.strip()
            if s and s in SUB and s not in vistos:
                vistos.add(s); out.append(s)
    return ";".join(out[:2]) or ""

def regra_pasta(arq):
    """So as pastas que a ESPECIFICACAO atribui explicitamente. Mapa de referencia vai para
    metodos_quantitativos_sig, que a especificacao tambem lista: [premissa] a regra mais
    especifica (mapa) vence a mais geral (pasta)."""
    a = arq.replace("\\", "/")
    if a.startswith(("3 - Ferrovias/", "4 - Rodovias/")) and "/Mapas" in a:
        return "metodos_quantitativos_sig", ("modos_ferro_aero_hidro" if a.startswith("3") else
                                             "infraestrutura_rodoviaria_pavimentos"), "mapa de referencia em pasta de modo"
    if a.startswith("3 - Ferrovias/"):
        return "modos_ferro_aero_hidro", None, "pasta 3 - Ferrovias (especificacao)"
    if a.startswith("1 - Aeroportos/"):
        return "modos_ferro_aero_hidro", None, "pasta 1 - Aeroportos (especificacao)"
    return None

saida = []
for r in v1:
    a = r["arquivo"]; c = v2.get(a, {}); o = {}
    o.update({"arquivo": a, "titulo": c.get("titulo") or r.get("titulo") or "",
              "autores": "; ".join(c.get("autores") or []), "ano": c.get("ano") or "",
              "veiculo": c.get("veiculo") or "", "idioma": c.get("idioma") or "",
              "natureza": c.get("natureza") or "", "paginas": c.get("paginas") or r.get("paginas") or "",
              "status": c.get("status") if c else "nao_catalogado_v2"})   # nunca herdar status da v1
    princ, sec, conf, orig, aj = c.get("subarea_principal"), c.get("subarea_secundaria"), c.get("confianca"), "modelo_texto_v2", []
    x = oc.get(a)
    if o["status"] in ("pendente_ocr", "erro_leitura") and x and x.get("status") == "ok" and x.get("subarea_principal"):
        # o OCR devolveu texto: classificacao pelo texto, que e melhor que pelo nome (40% de
        # concordancia medida). Os metadados (titulo, ano, autores) tambem vem do texto do OCR.
        princ, sec, conf, orig = x["subarea_principal"], x.get("subarea_secundaria"), x.get("confianca"), "modelo_texto_ocr_v2"
        for k in ("titulo", "ano", "veiculo", "idioma", "natureza"):
            o[k] = x.get(k) or o[k]
        o["autores"] = "; ".join(x.get("autores") or [])
        o["status"] = "ok_ocr"
        c = {**c, "motivo_secundaria": x.get("motivo_secundaria")}
    if o["status"] in ("pendente_ocr", "erro_leitura") or (c and not princ):
        s = st.get(a)
        if s and s.get("subarea_principal"):
            princ, sec, conf, orig = s["subarea_principal"], s.get("subarea_secundaria"), s["confianca"], "inferencia_caminho_titulo"
            aj.append("sem texto: " + (s.get("motivo_inferencia") or "")[:160])
        else:
            orig = "pendente"
    if a in co:
        x = co[a]
        if x.get("subarea_principal") and x["subarea_principal"] != princ:
            sec = secs(princ, sec, excluir=x["subarea_principal"])
            aj.append(f"correcao dirigida: {princ} -> {x['subarea_principal']} ({x.get('motivo','')[:120]})")
            princ, orig = x["subarea_principal"], "correcao_dirigida"
            conf = x.get("confianca") or conf
    rp = regra_pasta(a)
    if rp:
        alvo, sec_forcada, motivo = rp
        if princ != alvo:
            aj.append(f"regra de pasta: {princ} -> {alvo} ({motivo})")
            sec = secs(sec_forcada, princ, sec, excluir=alvo)
            princ = alvo
            if orig != "inferencia_caminho_titulo": orig = "regra_pasta_especificacao"
        elif sec_forcada:
            sec = secs(sec_forcada, sec, excluir=alvo)
    rev = (r.get("REVISAO_subarea") or "").strip()
    if rev in SUB:
        if rev != princ: aj.append(f"revisao manual: {princ} -> {rev}")
        sec = secs(sec, princ, excluir=rev); princ, orig, conf = rev, "revisao_manual", "alta"
    d = dup.get(a, {})
    o.update({"subarea_principal": princ or "", "subarea_secundaria": secs(sec, excluir=princ),
              "confianca": conf or "", "origem_classificacao": orig, "ajuste": " | ".join(aj),
              "subarea_v1": r.get("subarea_principal") or "",
              "recuperado_na_2a_v1": "sim" if str(r.get("recuperado_na_2a")).lower() in ("true", "1") else "",
              "motivo_secundaria": (c.get("motivo_secundaria") or "")[:300],
              "duplicata": d.get("papel", ""), "duplicata_tipo": d.get("tipo_grupo", ""),
              "duplicata_canonico": d.get("duplicata_canonico", ""),
              "REVISAO_subarea": r.get("REVISAO_subarea", ""), "REVISAO_excluir": r.get("REVISAO_excluir", ""),
              "REVISAO_nota": r.get("REVISAO_nota", "")})
    saida.append(o)

def prioridade(o):
    return (0 if o["recuperado_na_2a_v1"] else 1, 0 if o["subarea_principal"] == "fora_de_escopo" else 1,
            0 if o["origem_classificacao"] == "inferencia_caminho_titulo" else 1,
            {"baixa": 0, "media": 1}.get(o["confianca"], 2), 0 if o["ajuste"] else 1, o["arquivo"])
saida.sort(key=prioridade)
for i, o in enumerate(saida, 1): o["ordem_revisao"] = i
COLS = ["ordem_revisao", "arquivo", "titulo", "autores", "ano", "veiculo", "idioma", "natureza", "paginas",
        "status", "subarea_principal", "subarea_secundaria", "confianca", "origem_classificacao", "ajuste",
        "subarea_v1", "recuperado_na_2a_v1", "motivo_secundaria", "duplicata", "duplicata_tipo",
        "duplicata_canonico", "REVISAO_subarea", "REVISAO_excluir", "REVISAO_nota"]
sufixo = "_PARCIAL" if PARCIAL else ""
with open(BC/f"revisao_taxonomia_v2{sufixo}.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(saida)
json.dump({"cols": COLS, "linhas": saida}, open(BC/f"revisao_taxonomia_v2{sufixo}.json", "w"), ensure_ascii=False)
# catalogo para o indice: SO o que tem texto (original ou OCR) e classe final; o indexador le status ok
with open(BC/f"catalogo_indice_v2{sufixo}.jsonl", "w", encoding="utf-8") as f:
    for o in saida:
        if o["status"] in ("ok", "ok_ocr") and o["subarea_principal"]:
            f.write(json.dumps({**{k: o[k] for k in ("arquivo", "titulo", "ano", "natureza", "subarea_principal",
                     "subarea_secundaria", "veiculo", "duplicata", "duplicata_tipo")}, "status": "ok"}, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- conferencias
assert len(saida) == 1945
_fora = [(o["arquivo"], o["subarea_principal"], o["status"], o["origem_classificacao"]) for o in saida if o["origem_classificacao"] != "pendente" and o["status"] != "nao_catalogado_v2" and o["subarea_principal"] not in SUB]
assert not _fora, f"classe fora da taxonomia: {len(_fora)} ex. {_fora[:4]}"
assert not any(o["subarea_principal"] and o["subarea_principal"] in o["subarea_secundaria"].split(";") for o in saida), "secundaria repete principal"
assert all(len([s for s in o["subarea_secundaria"].split(";") if s]) <= 2 for o in saida)
validos = [o for o in saida if o["subarea_principal"]]
print(f"linhas {len(saida)} | com classe {len(validos)} | origem {dict(Counter(o['origem_classificacao'] for o in saida))}")
print(f"secundaria preenchida {sum(1 for o in validos if o['subarea_secundaria'])} de {len(validos)}")
print(f"duplicatas {dict(Counter(o['duplicata'] for o in saida if o['duplicata']))}")
print(f"ajustes {sum(1 for o in saida if o['ajuste'])}")
print("CONFERENCIAS OK")
