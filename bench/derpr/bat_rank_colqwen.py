"""Fase 4: braco C, ColQwen2.5, interacao tardia com MaxSim."""
import sys, json, pathlib, time, torch, numpy as np
from PIL import Image
B = pathlib.Path.home()/"ecossistema/bench"
passada = sys.argv[1]
alvo = B/f"derpr/rank/C_p{passada}.json"
if alvo.exists(): print(f"  braco C passada {passada}: ja existe"); raise SystemExit
perg = {p["id"]: p["texto"] for p in json.loads((B/"suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}
try:
    from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
except Exception as e:
    import colpali_engine.models as m
    print("  classes disponiveis:", [x for x in dir(m) if "Col" in x]); raise
M = "vidore/colqwen2.5-v0.2"
t0 = time.time()
mod = ColQwen2_5.from_pretrained(M, torch_dtype=torch.bfloat16, device_map="cuda").eval()
proc = ColQwen2_5_Processor.from_pretrained(M)
carga = time.time()-t0
docs, nb = [], 0
t1 = time.time()
for i in range(1, 59):
    bi = proc.process_images([Image.open(B/f"derpr/paginas/p{i:02d}.png").convert("RGB")]).to("cuda")
    with torch.inference_mode(): e = mod(**bi)
    docs.append(e[0].float().cpu()); nb += e[0].numel()*2
dt = time.time()-t1
ids = sorted(perg)
bq = proc.process_queries([perg[k] for k in ids]).to("cuda")
with torch.inference_mode(): qe = mod(**bq)
qe = qe.float().cpu()
rank = {}
for i, qid in enumerate(ids):
    sc = [float((qe[i] @ d.T).max(dim=1).values.sum()) for d in docs]
    rank[qid] = (np.argsort(-np.array(sc))+1).tolist()
alvo.write_text(json.dumps({"braco":"C","passada":int(passada),"rank":rank,
    "bytes_indice":int(nb),"dim":int(docs[0].shape[1]),
    "vetores_por_pagina":round(sum(d.shape[0] for d in docs)/58,1),
    "seg_consulta":round(carga,2),"seg_indexacao":round(dt,2)}, ensure_ascii=False))
print(f"  braco C passada {passada}: indice {nb/1048576:.0f} MB, {sum(d.shape[0] for d in docs)/58:.0f} vetores/pagina, {dt:.0f}s")
