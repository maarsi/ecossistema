"""Fase 6: pontuador UNICO. Le os rankings de todos os bracos e calcula as metricas
declaradas na suite: acerto@1, acerto@5 e posicao do certo, granularidade de pagina."""
import json, pathlib, statistics as st, hashlib, datetime as dt
import numpy as np
B = pathlib.Path.home()/"ecossistema/bench"

# ---- autoteste: o pontuador precisa provar que funciona antes de medir qualquer coisa
def metricas(rank, gab):
    pos = []
    for q, pg in gab.items():
        if q not in rank: continue
        r = rank[q]
        pos.append(r.index(pg)+1 if pg in r else len(r)+1)
    n = len(pos)
    return {"n": n, "acerto1": sum(p==1 for p in pos)/n, "acerto5": sum(p<=5 for p in pos)/n,
            "pos_mediana": st.median(pos), "pos_media": round(sum(pos)/n,2)}
g = {"Q1": 3, "Q2": 7}
assert metricas({"Q1":[3,1,2],"Q2":[7,1,2]}, g)["acerto1"] == 1.0
assert metricas({"Q1":[1,2,3],"Q2":[1,2,7]}, g)["acerto1"] == 0.0
assert metricas({"Q1":[1,2,3],"Q2":[1,2,7]}, g)["acerto5"] == 1.0
assert metricas({"Q1":[1,2,3],"Q2":[1,2,7]}, g)["pos_mediana"] == 3
print("  autoteste do pontuador: PASSOU (3 assercoes)")

# ---- gabarito
a4 = json.loads((B/"suites/recuperacao_anuario_derpr_ADENDO_04.json").read_text())
gab = {r["id"]: r["gabarito_pagina"] for r in a4["respostas"] if r["gabarito_pagina"] is not None}
ausentes = [r["id"] for r in a4["respostas"] if r["gabarito_pagina"] is None]
assert len(gab) == 28, f"esperava 28 pontuaveis, achei {len(gab)}"
print(f"  gabarito: {len(gab)} perguntas pontuaveis, {len(ausentes)} ausentes ({', '.join(ausentes)})")

LIMITE_GB = 200          # confirmado pelo Mateus em 11/11, antes de executar
NOMES = {"A":"Docling sem OCR","B":"Docling com OCR","C":"ColQwen2.5 (interacao tardia)",
         "D":"nemotron embed-vl (denso)","E":"D + reordenador VL","G":"Nemotron-3.5-Parse"}
res = {}
for br in "ABCDEG":
    passadas = []
    for p in (1,2,3):
        f = B/f"derpr/rank/{br}_p{p}.json"
        if f.exists(): passadas.append(json.loads(f.read_text()))
    if not passadas: res[br] = {"status":"NAO EXECUTADO"}; continue
    ms = [metricas(x["rank"], gab) for x in passadas]
    iguais = len({json.dumps(x["rank"], sort_keys=True) for x in passadas}) == 1
    bp = passadas[0]["bytes_indice"]/58
    res[br] = {"status":"OK","nome":NOMES[br],"passadas":len(ms),
      "acerto1": round(100*st.mean(m["acerto1"] for m in ms),1),
      "acerto5": round(100*st.mean(m["acerto5"] for m in ms),1),
      "acerto1_desvio": round(100*(st.stdev([m["acerto1"] for m in ms]) if len(ms)>1 else 0),1),
      "pos_mediana": st.median([m["pos_mediana"] for m in ms]),
      "pos_media": round(st.mean(m["pos_media"] for m in ms),2),
      "rankings_identicos_entre_passadas": iguais,
      "bytes_por_pagina": int(bp), "vetores_por_pagina": passadas[0].get("vetores_por_pagina"),
      "dim": passadas[0].get("dim"),
      "proj_10k_GB": round(bp*10_000/2**30, 3), "proj_50k_GB": round(bp*50_000/2**30, 3),
      "cabe_no_limite": bp*50_000/2**30 <= LIMITE_GB,
      "seg_indexacao": passadas[0].get("seg_indexacao"), "seg_consulta": passadas[0].get("seg_consulta")}

elegiveis = {k:v for k,v in res.items() if v.get("status")=="OK" and v.get("cabe_no_limite")}
venc = max(elegiveis, key=lambda k: elegiveis[k]["acerto5"]) if elegiveis else None
saida = {"gerado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
 "corpus_sha256":"c19be5398997a7ae18117ac9cdd48ee866757a293652e5f4b26f7e689368649c",
 "gabarito_sha256": hashlib.sha256((B/"suites/recuperacao_anuario_derpr_ADENDO_04.json").read_bytes()).hexdigest(),
 "perguntas_pontuaveis": len(gab), "ausentes": ausentes,
 "criterio":{"regra":"maior acerto@5 entre os bracos cuja projecao para 50 mil paginas caiba em 200 GB",
   "limite_GB": LIMITE_GB, "confirmado_por":"Mateus, 11/11/2026, antes de executar"},
 "ADVERTENCIA_ARMAZENAMENTO":"o corpus tem 58 paginas e nessa escala o indice cabe em qualquer braco. "
   "Esta bateria E INCAPAZ de revelar o problema de armazenamento. As projecoes sao calculo declarado, nao medicao.",
 "vencedor_pelo_criterio": venc, "bracos": res}
(B/"derpr/resultados/resultado.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1))

print(f"\n  {'braco':<6}{'ferramenta':<30}{'acerto@1':>9}{'acerto@5':>9}{'pos.med':>8}{'indice 50k':>12}{'cabe':>6}")
print("  "+"-"*82)
for br in "ABCDEG":
    v = res[br]
    if v.get("status") != "OK": print(f"  {br:<6}{'':<30}{'NAO EXECUTADO':>30}"); continue
    print(f"  {br:<6}{v['nome']:<30}{v['acerto1']:>8.0f}%{v['acerto5']:>8.0f}%{v['pos_media']:>8.1f}"
          f"{v['proj_50k_GB']:>10.1f} GB{'sim' if v['cabe_no_limite'] else 'NAO':>6}")
print(f"\n  vencedor pelo criterio declarado: {venc or 'nenhum braco elegivel'}")
nid = [k for k,v in res.items() if v.get("status")=="OK" and not v["rankings_identicos_entre_passadas"]]
print(f"  bracos com ranking diferente entre as 3 passadas: {nid or 'nenhum (pipeline deterministico)'}")
