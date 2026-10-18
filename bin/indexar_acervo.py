#!/usr/bin/env python3
"""Indexa o acervo juridico com embeddings locais (ollama qwen3-embedding:4b).
Ancoras: arquivo + pagina (PDF) / bloco (docx, md, txt). Somente leitura no acervo.
Retomavel: pula arquivos ja indexados (mesmo caminho+mtime). PDFs sem texto viram SCAN."""
import json, sys, time, urllib.request
from pathlib import Path
import numpy as np

RAIZ = Path.home() / "divorcio_local"
DEST = Path.home() / "acervo_divorcio_index"; DEST.mkdir(exist_ok=True)
META, EMBED = DEST / "meta.jsonl", DEST / "emb.npy"
OLLAMA = "http://localhost:11434/api/embed"
LOTE = 32

def extrair(caminho):
    ext = caminho.suffix.lower()
    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(str(caminho))
            paginas = [(i + 1, p.get_text().strip()) for i, p in enumerate(doc)]
            doc.close()
            return paginas
        if ext == ".docx":
            import zipfile, re
            xml = zipfile.ZipFile(str(caminho)).read("word/document.xml").decode("utf-8", "ignore")
            partes = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S)
            texto = " ".join(partes).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            return [(0, texto)]
        if ext in (".md", ".txt"):
            return [(0, caminho.read_text(encoding="utf-8", errors="ignore"))]
    except Exception as e:
        print(f"  [erro extracao] {caminho.name}: {type(e).__name__}")
    return []

def fatiar(pagina, texto, limite=900):
    t = " ".join(texto.split())
    if len(t) < 80: return []
    paso = limite - 150
    return [(pagina, t[i:i + limite]) for i in range(0, len(t), paso)]

def emb_lote(textos):
    payload = json.dumps({"model": "qwen3-embedding:4b", "input": textos}).encode()
    req = urllib.request.Request(OLLAMA, data=payload, headers={"Content-Type": "application/json"})
    for tent in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return np.asarray(json.loads(r.read())["embeddings"], dtype=np.float32)
        except Exception:
            if tent == 2: raise
            time.sleep(5)

indexados = {}
if META.exists():
    for lin in META.read_text().splitlines():
        try:
            r = json.loads(lin); indexados[r["arquivo"]] = r["mtime"]
        except Exception: pass

emb_global = np.load(EMBED) if EMBED.exists() else np.zeros((0, 1024), dtype=np.float32)
pend, scans = [], []
n_arq = 0
for caminho in sorted(RAIZ.rglob("*")):
    if not caminho.is_file(): continue
    n_arq += 1
    if n_arq % 50 == 0: print(f"  ...{n_arq} arquivos na extracao", flush=True)
    if caminho.suffix.lower() in (".jpg", ".jpeg", ".png", ".mp4", ".m4a", ".aac", ".zip", ".rar", ".pptx", ".xlsx", ".xls", ".doc", ".heic"):
        continue
    rel = str(caminho.relative_to(RAIZ)); mtime = caminho.stat().st_mtime
    if indexados.get(rel) == mtime: continue
    paginas = extrair(caminho)
    if caminho.suffix.lower() == ".pdf" and all(len(t.strip()) < 20 for _, t in paginas):
        scans.append(rel); continue
    for pagina, texto in paginas:
        for pag, trecho in fatiar(pagina, texto):
            pend.append((rel, pag, trecho))

print(f"chunks pendentes: {len(pend)} | PDFs sem texto (SCAN): {len(scans)} | ja indexados: {len(indexados)}")
if EMBED.exists() is False and emb_global.shape[0] == 0 and pend:
    pass
for i in range(0, len(pend), LOTE):
    lote = pend[i:i + LOTE]
    vetores = emb_lote([t for _, _, t in lote])
    emb_global = np.vstack([emb_global, vetores]) if emb_global.size else vetores
    with open(META, "a") as f:
        for (rel, pagina, trecho), v in zip(lote, vetores):
            f.write(json.dumps({"arquivo": rel, "pagina": pagina, "trecho": trecho[:400], "mtime": Path(RAIZ / rel).stat().st_mtime}, ensure_ascii=False) + "\n")
    if (i // LOTE) % 10 == 0:
        np.save(EMBED, emb_global)
        print(f"  {i + len(lote)}/{len(pend)} chunks indexados...")
    time.sleep(0.2)
np.save(EMBED, emb_global)
(DEST / "scans.txt").write_text("\n".join(scans))
print(f"CONCLUIDO: {emb_global.shape[0]} chunks no indice | {len(scans)} PDFs p/ OCR futuro")
