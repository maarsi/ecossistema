"""Braco H (nemotron-ocr-v2 -> qwen3-embedding:4b), pre-registrado no ADENDO_02 em 11/11/2026 e
NAO EXECUTADO em 12/11 por falha de compilacao. Executado em 21/11 depois que a extensao compilou
em C++20 (ver CLAUDE.md). Fase 0: pre-voo de validade com a MESMA lambda de prevoo2.sh. Fase 1:
texto das 58 paginas, 3 passadas. O ranking usa o MESMO embedder dos bracos A, B e G."""
import json, pathlib, sys, time, unicodedata, requests, numpy as np
from collections import Counter
B = pathlib.Path.home()/"ecossistema/bench"; P = B/"derpr/prevoo"
from nemotron_ocr.inference.pipeline_v2 import NemotronOCRV2
fase = sys.argv[1]
if fase == "prevoo":
    for lang, arq in (("en", "ocr_en"), ("multi", "ocr_multi")):
        ocr = NemotronOCRV2(lang=lang)
        for pg in (10, 21, 13):
            r = ocr(str(P/f"paginas/pagina_{pg:02d}.png"))
            (P/f"saidas/{arq}_p{pg:02d}.txt").write_text(" ".join(x["text"] for x in r))
    ref = json.loads((P/"camada_texto.json").read_text())["10"]
    ac = lambda t: [c for c in t if unicodedata.combining(unicodedata.normalize("NFD",c)[-1]) or c in "cCçÇ" and c in "çÇ"]
    A = ac(ref); cA = Counter(A); res = {}
    print(f"referencia p10: {len(A)} acentuados")
    for nome, arq in (("Docling (B)", "docling_p10.txt"), ("Parse (G)", "parse_p10.txt"),
                      ("ocr-v2 ingles", "ocr_en_p10.txt"), ("ocr-v2 multilingue", "ocr_multi_p10.txt")):
        Bc = ac((P/"saidas"/arq).read_text()); cB = Counter(Bc)
        tipos = 100*sum(min(cB[k], v) for k, v in cA.items())/len(A)
        ver = "APROVADO" if tipos >= 95 else ("COM RESSALVA" if tipos >= 80 else "REPROVADO")
        res[nome] = {"acentuados": len(Bc), "taxa": round(100*len(Bc)/len(A)), "tipos_preservados": round(tipos), "veredito": ver}
        print(f"  {nome:22s} {len(Bc):4d} acentuados  taxa {100*len(Bc)/len(A):4.0f}%  tipos {tipos:4.0f}%  {ver}")
    json.dump(res, open(P/"prevoo_H_20261121.json", "w"), ensure_ascii=False, indent=1)
else:
    lang = sys.argv[2]; passada = fase
    T = B/f"derpr/textos/H_p{passada}.json"
    ocr = NemotronOCRV2(lang=lang); out = {}; t0 = time.time()
    for i in range(1, 59):
        r = ocr(str(B/f"derpr/paginas/p{i:02d}.png")); out[str(i)] = " ".join(x["text"] for x in r)
    T.write_text(json.dumps(out, ensure_ascii=False)); dt_ocr = time.time() - t0
    perg = {p["id"]: p["texto"] for p in json.loads((B/"suites/recuperacao_anuario_derpr.json").read_text())["perguntas"]}
    def emb(textos, lote=8):
        v = []
        for k in range(0, len(textos), lote):
            rr = requests.post("http://localhost:11434/api/embed", json={"model": "qwen3-embedding:4b",
                 "input": [t[:8000] if t.strip() else " " for t in textos[k:k+lote]]}, timeout=600)
            rr.raise_for_status(); v.extend(rr.json()["embeddings"])
        a = np.array(v, dtype=np.float32); return a/(np.linalg.norm(a, axis=1, keepdims=True)+1e-9)
    t1 = time.time(); Q = emb([perg[k] for k in sorted(perg)]); carga = time.time()-t1
    t2 = time.time(); Pv = emb([out.get(str(i), "") for i in range(1, 59)]); dt = time.time()-t2
    S = Q @ Pv.T
    rank = {q: (np.argsort(-S[i])+1).tolist() for i, q in enumerate(sorted(perg))}
    (B/f"derpr/rank/H_p{passada}.json").write_text(json.dumps({"braco": "H", "passada": int(passada), "rank": rank,
        "bytes_indice": int(Pv.nbytes), "dim": int(Pv.shape[1]), "vetores_por_pagina": 1, "lang": lang,
        "seg_consulta": round(carga, 2), "seg_indexacao": round(dt + dt_ocr, 2), "seg_ocr": round(dt_ocr, 2)}))
    vaz = sum(1 for t in out.values() if len(t.strip()) < 20)
    print(f"H passada {passada} ({lang}): OCR {dt_ocr:.0f}s, {vaz} paginas quase vazias, embedding {dt:.0f}s")
