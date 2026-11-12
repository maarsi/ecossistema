"""Fase 3: bracos A, B e G. MESMO embedder para os tres, de proposito:
assim a unica variavel entre eles e o extrator, nao o buscador."""
import sys, json, pathlib, time, requests, numpy as np
B = pathlib.Path.home()/"ecossistema/bench"
passada = sys.argv[1]
perg = {p["id"]: p["texto"] for p in json.loads((B/"suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}
URL = "http://localhost:11434/api/embed"; MOD = "qwen3-embedding:4b"
def emb(textos, lote=8):
    v = []
    for i in range(0, len(textos), lote):
        r = requests.post(URL, json={"model": MOD, "input": [t[:8000] if t.strip() else " " for t in textos[i:i+lote]]}, timeout=600)
        r.raise_for_status(); v.extend(r.json()["embeddings"])
    a = np.array(v, dtype=np.float32)
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
t0 = time.time(); Q = emb([perg[k] for k in sorted(perg)]); carga = time.time()-t0
for braco in ("A", "B", "G"):
    f = B/f"derpr/textos/{braco}_p{passada}.json"
    if not f.exists(): print(f"  braco {braco}: sem texto, pulando"); continue
    alvo = B/f"derpr/rank/{braco}_p{passada}.json"
    if alvo.exists(): print(f"  braco {braco} passada {passada}: ja existe"); continue
    txt = json.loads(f.read_text())
    t1 = time.time(); Pv = emb([txt.get(str(i), "") for i in range(1, 59)]); dt = time.time()-t1
    S = Q @ Pv.T                                  # 30 x 58
    rank = {qid: (np.argsort(-S[i])+1).tolist() for i, qid in enumerate(sorted(perg))}
    alvo.write_text(json.dumps({"braco": braco, "passada": int(passada), "rank": rank,
        "bytes_indice": int(Pv.nbytes), "dim": int(Pv.shape[1]), "vetores_por_pagina": 1,
        "seg_consulta": round(carga,2), "seg_indexacao": round(dt,2)}, ensure_ascii=False))
    print(f"  braco {braco} passada {passada}: indice {Pv.nbytes/1024:.0f} KB, dim {Pv.shape[1]}, {dt:.0f}s")
