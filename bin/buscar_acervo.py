#!/usr/bin/env python3
"""Busca semantica no acervo indexado. Uso: python buscar_acervo.py "sua pergunta" [top N]"""
import json, sys, urllib.request
from pathlib import Path
import numpy as np

pergunta = sys.argv[1] if len(sys.argv) > 1 else input("pergunta: ")
top = int(sys.argv[2]) if len(sys.argv) > 2 else 8
DEST = Path.home() / "acervo_divorcio_index"
emb = np.load(DEST / "emb.npy")
metas = [json.loads(l) for l in (DEST / "meta.jsonl").read_text().splitlines()]
payload = json.dumps({"model": "qwen3-embedding:4b", "input": [pergunta]}).encode()
req = urllib.request.Request("http://localhost:11434/api/embed", data=payload, headers={"Content-Type": "application/json"})
vq = np.asarray(json.loads(urllib.request.urlopen(req, timeout=60).read())["embeddings"][0], dtype=np.float32)
sims = emb @ vq / (np.linalg.norm(emb, axis=1) * np.linalg.norm(vq))
for rank, idx in enumerate(np.argsort(sims)[::-1][:top], 1):
    m = metas[idx]
    pag = f" p.{m['pagina']}" if m["pagina"] else ""
    print(f"{rank}. [{sims[idx]:.3f}] {m['arquivo']}{pag}")
    print(f"   {m['trecho'][:220]}...\n")
