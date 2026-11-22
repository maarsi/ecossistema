#!/usr/bin/env python3
"""Busca no acervo indexado.
Uso: buscar_acervo.py "pergunta" [top N] [--exato]
  padrao:  busca semantica (embeddings, qwen3-embedding:4b)
  --exato: busca literal por trecho exato (numeros de processo, DARE, valores)"""
import json, re, sys, urllib.request
from pathlib import Path
import numpy as np

args = [a for a in sys.argv[1:] if not a.startswith("--")]
exato = "--exato" in sys.argv
pergunta = args[0] if args else input("pergunta: ")
top = int(args[1]) if len(args) > 1 else 8
DEST = Path.home() / "acervo_divorcio_index"
metas = [json.loads(l) for l in (DEST / "meta.jsonl").read_text().splitlines()]

if exato:
    padrao = re.compile(re.escape(pergunta), re.IGNORECASE)
    hits = [m for m in metas if padrao.search(m["trecho"])]
    print(f'{len(hits)} ocorrencias literais de "{pergunta}" (amostra de trecho por chunk):')
    for m in hits[:top]:
        pag = f" p.{m['pagina']}" if m.get("pagina") else ""
        print(f"- {m['arquivo']}{pag}")
        print(f"  {m['trecho'][:220]}...\n")
    sys.exit(0)

emb = np.load(DEST / "emb.npy")
payload = json.dumps({"model": "qwen3-embedding:4b", "input": [pergunta]}).encode()
req = urllib.request.Request("http://localhost:11434/api/embed", data=payload,
                             headers={"Content-Type": "application/json"})
vq = np.asarray(json.loads(urllib.request.urlopen(req, timeout=60).read())["embeddings"][0], dtype=np.float32)
sims = emb @ vq / (np.linalg.norm(emb, axis=1) * np.linalg.norm(vq))
for rank, i in enumerate(np.argsort(sims)[::-1][:top], 1):
    m = metas[i]
    pag = f" p.{m['pagina']}" if m.get("pagina") else ""
    print(f"{rank}. [{sims[i]:.3f}] {m['arquivo']}{pag}")
    print(f"   {m['trecho'][:220]}...\n")
