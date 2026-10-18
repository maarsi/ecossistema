#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Compara busca por IMAGEM de pagina (llama-nemotron-embed-vl) com busca por TEXTO (qwen3-embedding).
Gabarito extraido do proprio PDF (pagina que contem a legenda), nunca digitado."""
import re, time
from pathlib import Path
import numpy as np, pymupdf, requests
from PIL import Image

PDF = Path("/home/mateus/ecossistema/bench/dados/artigo_transformer.pdf")
DIR = Path("/tmp/paginas_vl"); DIR.mkdir(exist_ok=True)
doc = pymupdf.open(PDF)
textos = [p.get_text() for p in doc]

def pagina_com(padrao):
    for i, t in enumerate(textos, 1):
        if re.search(padrao, t, re.I | re.S): return i
    return None

PERGUNTAS = [
 ("Qual figura mostra a arquitetura completa do modelo, com codificador e decodificador?", r"Figure 1:\s*The Transformer\s*-\s*model architecture"),
 ("Em que pagina esta a tabela que compara pontuacao BLEU e custo de treinamento entre modelos?", r"Table 2:\s*The Transformer achieves better BLEU"),
 ("Onde esta a tabela com as variacoes da arquitetura, testando numero de cabecas de atencao?", r"Table 3:\s*Variations on the Transformer"),
 ("Qual tabela compara complexidade por camada e comprimento maximo de caminho entre tipos de camada?", r"Table 1:\s*Maximum path lengths"),
 ("Qual figura ilustra a atencao por produto escalar e a atencao multi-cabeca lado a lado?", r"Figure 2:\s*\(left\) Scaled Dot-Product|Scaled Dot-Product Attention\.\s*\(right\)"),
]
gab = [(q, pagina_com(p)) for q, p in PERGUNTAS]
print("=== GABARITO (pagina da legenda, extraida do PDF)")
for q, g in gab: print(f"  p.{g}  {q[:72]}")
validas = [(q, g) for q, g in gab if g]
print(f"  perguntas utilizaveis: {len(validas)}/{len(gab)} | paginas no documento: {len(textos)}\n")

# ---------- 1) IMAGEM
t0 = time.time()
imgs = []
for i in range(len(textos)):
    f = DIR / f"p{i+1:03d}.png"
    if not f.exists(): doc[i].get_pixmap(dpi=120).save(f)
    imgs.append(f)
t_render = time.time() - t0
from sentence_transformers import SentenceTransformer
t0 = time.time(); m = SentenceTransformer("nvidia/llama-nemotron-embed-vl-1b-v2", trust_remote_code=True, device="cuda")
t_load = time.time() - t0
t0 = time.time(); V = np.array(m.encode([Image.open(f) for f in imgs], batch_size=2, show_progress_bar=False)); t_idx = time.time() - t0
Q = np.array(m.encode([q for q, _ in validas], prompt_name="query", show_progress_bar=False))
norm = lambda A: A / np.linalg.norm(A, axis=1, keepdims=True)
S_img = norm(Q) @ norm(V).T

# ---------- 2) TEXTO (qwen3-embedding via Ollama)
def emb(lst, lote=8):
    out = []
    for k in range(0, len(lst), lote):
        r = requests.post("http://localhost:11434/api/embed", timeout=600,
                          json={"model": "qwen3-embedding:4b", "input": lst[k:k+lote], "keep_alive": "10m"}).json()
        out += r["embeddings"]
    return np.array(out)
t0 = time.time(); T = emb([t[:6000] for t in textos]); t_txt = time.time() - t0
QT = emb([q for q, _ in validas])
S_txt = norm(QT) @ norm(T).T

print("=== RESULTADO (posicao da pagina correta no ranking)")
print(f"{'PERGUNTA':58} {'GABARITO':>8} {'IMAGEM':>8} {'TEXTO':>8}")
acc = {"img1": 0, "img3": 0, "txt1": 0, "txt3": 0}
for j, (q, g) in enumerate(validas):
    oi = list(np.argsort(-S_img[j]) + 1); ot = list(np.argsort(-S_txt[j]) + 1)
    pi, pt = oi.index(g) + 1, ot.index(g) + 1
    acc["img1"] += pi == 1; acc["img3"] += pi <= 3; acc["txt1"] += pt == 1; acc["txt3"] += pt <= 3
    print(f"{q[:58]:58} {('p.'+str(g)):>8} {('1o' if pi==1 else str(pi)+'o'):>8} {('1o' if pt==1 else str(pt)+'o'):>8}")
n = len(validas)
print(f"\nACERTO EM 1o LUGAR  imagem {acc['img1']}/{n}   texto {acc['txt1']}/{n}")
print(f"ACERTO ATE 3o LUGAR imagem {acc['img3']}/{n}   texto {acc['txt3']}/{n}")
print(f"\nCUSTO: render {t_render:.1f}s | carga do modelo {t_load:.1f}s | indexar {len(imgs)} paginas por imagem {t_idx:.1f}s "
      f"({t_idx/len(imgs):.2f}s/pag) | por texto {t_txt:.1f}s ({t_txt/len(textos):.2f}s/pag)")
