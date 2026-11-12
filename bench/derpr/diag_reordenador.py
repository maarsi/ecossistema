"""Testa a hipotese: o reordenador VL discrimina bem em pagina de prosa e mal em
pagina de tabela. Se confirmada, explica por que o braco E piora o acerto@1 do D."""
import json, pathlib, torch, numpy as np, statistics as st
from PIL import Image
from sentence_transformers import CrossEncoder
B = pathlib.Path.home()/"ecossistema/bench"
perg = {p["id"]: p["texto"] for p in json.loads((B/"suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}
a4 = json.loads((B/"suites/recuperacao_anuario_derpr_ADENDO_04.json").read_text())
gab = {r["id"]: (r["gabarito_pagina"], r["onde"]) for r in a4["respostas"] if r["gabarito_pagina"]}
rD = json.loads((B/"derpr/rank/D_p1.json").read_text())["rank"]
rE = json.loads((B/"derpr/rank/E_p1.json").read_text())["rank"]
ce = CrossEncoder("nvidia/llama-nemotron-rerank-vl-1b-v2", trust_remote_code=True,
                  model_kwargs={"dtype": torch.bfloat16}, device="cuda")
L=[]
for q,(pg,onde) in gab.items():
    topo = rD[q][:10]
    sc = np.asarray(ce.predict([(perg[q], Image.open(B/f"derpr/paginas/p{p:02d}.png").convert("RGB")) for p in topo],
                               batch_size=4), dtype=float)
    L.append({"q":q,"onde":onde,"amp":float(sc.max()-sc.min()),"certa_no_topo":pg in topo,
              "D":rD[q][0]==pg,"E":rE[q][0]==pg})
out=[]
out.append(f"{'grupo':<24}{'n':>4}{'amplitude media':>18}{'acerto@1 D':>12}{'acerto@1 E':>12}")
out.append("-"*72)
for g_ in ("texto","imagem"):
    g=[l for l in L if l["onde"]==g_]
    if g: out.append(f"resposta em {g_:<12}{len(g):>4}{st.mean(l['amp'] for l in g):>18.2f}"
                     f"{100*sum(l['D'] for l in g)/len(g):>11.0f}%{100*sum(l['E'] for l in g)/len(g):>11.0f}%")
out.append(f"{'TODAS':<24}{len(L):>4}{st.mean(l['amp'] for l in L):>18.2f}"
           f"{100*sum(l['D'] for l in L)/len(L):>11.0f}%{100*sum(l['E'] for l in L)/len(L):>11.0f}%")
pior=[l['q'] for l in L if l['D'] and not l['E']]; mel=[l['q'] for l in L if not l['D'] and l['E']]
out.append(""); out.append(f"o reordenador ESTRAGOU: {pior}")
out.append(f"o reordenador CONSERTOU: {mel}")
if pior: out.append(f"amplitude media quando estragou: {st.mean(l['amp'] for l in L if l['q'] in pior):.2f}")
if mel:  out.append(f"amplitude media quando consertou: {st.mean(l['amp'] for l in L if l['q'] in mel):.2f}")
out.append(f"paginas certas que estavam no top-10 do D: {sum(l['certa_no_topo'] for l in L)} de {len(L)}")
txt="\n".join(out)
(B/"derpr/resultados/diag_reordenador.txt").write_text(txt)
json.dump(L, open(B/"derpr/resultados/diag_reordenador.json","w"), ensure_ascii=False, indent=1)
print(txt)
