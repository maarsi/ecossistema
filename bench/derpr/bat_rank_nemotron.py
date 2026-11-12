"""Fase 5: bracos D (denso) e E (D mais reordenacao)."""
import sys, json, pathlib, time, torch, numpy as np
from PIL import Image
B = pathlib.Path.home()/"ecossistema/bench"
passada = sys.argv[1]
perg = {p["id"]: p["texto"] for p in json.loads((B/"suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}
ids = sorted(perg); IMGS = [B/f"derpr/paginas/p{i:02d}.png" for i in range(1,59)]
from sentence_transformers import SentenceTransformer
t0=time.time()
m = SentenceTransformer("nvidia/llama-nemotron-embed-vl-1b-v2", trust_remote_code=True,
                        model_kwargs={"dtype": torch.bfloat16}, device="cuda")
carga=time.time()-t0
t1=time.time()
Pv = m.encode_document([Image.open(p).convert("RGB") for p in IMGS], batch_size=4, convert_to_numpy=True,
                       normalize_embeddings=True); dt=time.time()-t1
Q = m.encode_query([perg[k] for k in ids], convert_to_numpy=True, normalize_embeddings=True)
S = Q @ Pv.T
rankD = {q: (np.argsort(-S[i])+1).tolist() for i,q in enumerate(ids)}
(B/f"derpr/rank/D_p{passada}.json").write_text(json.dumps({"braco":"D","passada":int(passada),
  "rank":rankD,"bytes_indice":int(Pv.nbytes),"dim":int(Pv.shape[1]),"vetores_por_pagina":1,
  "seg_consulta":round(carga,2),"seg_indexacao":round(dt,2)}, ensure_ascii=False))
print(f"  braco D passada {passada}: indice {Pv.nbytes/1024:.0f} KB, dim {Pv.shape[1]}, {dt:.0f}s")
del m; torch.cuda.empty_cache()
try:
    from sentence_transformers import CrossEncoder
    t2=time.time()
    ce = CrossEncoder("nvidia/llama-nemotron-rerank-vl-1b-v2", trust_remote_code=True,
                      model_kwargs={"dtype": torch.bfloat16}, device="cuda")
    K=10; rankE={}
    for i,q in enumerate(ids):
        topo = rankD[q][:K]
        pares = [(perg[q], Image.open(B/f"derpr/paginas/p{p:02d}.png").convert("RGB")) for p in topo]
        sc = ce.predict(pares, batch_size=4)
        ordem = [topo[j] for j in np.argsort(-np.asarray(sc))]
        rankE[q] = ordem + [p for p in rankD[q] if p not in topo]
    (B/f"derpr/rank/E_p{passada}.json").write_text(json.dumps({"braco":"E","passada":int(passada),
      "rank":rankE,"bytes_indice":int(Pv.nbytes),"dim":int(Pv.shape[1]),"vetores_por_pagina":1,
      "seg_consulta":round(time.time()-t2,2),"seg_indexacao":round(dt,2),"k_reordenado":K}, ensure_ascii=False))
    print(f"  braco E passada {passada}: reordenou o top-{K}, {time.time()-t2:.0f}s")
except Exception as e:
    print(f"  braco E FALHOU: {type(e).__name__}: {str(e)[:200]}")
