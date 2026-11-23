#!/home/mateus/env_transporte/bin/python
"""Consulta a base de conhecimento do acervo 40 - REFERENCIAS (colecoes ref40_<subarea>, uma por
subarea, decisao de Mateus em 17/11/2026). Item 6 da fila de 21/11.
  consulta_acervo.py "<pergunta>" [--subarea a,b] [-k 6] [--filtro SQL] [--json]
Sem --subarea, busca em TODAS as colecoes e une por similaridade: a pergunta e embutida UMA vez.
Le os k primeiros: versoes gemeas e trechos do mesmo documento disputam o topo (licao de 22/09),
por isso o resultado limita a 2 trechos por documento."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import indice as ix
ap = argparse.ArgumentParser(); ap.add_argument("pergunta"); ap.add_argument("--subarea", default="")
ap.add_argument("-k", type=int, default=6); ap.add_argument("--filtro"); ap.add_argument("--json", action="store_true")
ap.add_argument("--por-documento", type=int, default=2, help="maximo de trechos do mesmo arquivo")
a = ap.parse_args()
disp = sorted(p.name for p in ix.BASE.glob("ref40_*") if (p / "trechos.lance").exists())
alvo = [f"ref40_{s.strip()}" for s in a.subarea.split(",") if s.strip()] or disp
falta = [c for c in alvo if c not in disp]
if falta: sys.exit(f"ERRO: colecao inexistente {falta}. Disponiveis: {', '.join(d[6:] for d in disp) or 'nenhuma ainda'}")
if not alvo: sys.exit("ERRO: nenhuma colecao ref40_* indexada ainda.")
v = ix.embed([a.pergunta])[0]
res = []
for c in alvo:
    t = ix.abrir(c).open_table("trechos").search(v, vector_column_name="vetor")
    try: t = t.distance_type("cosine")
    except AttributeError: t = t.metric("cosine")
    if a.filtro: t = t.where(a.filtro, prefilter=True)
    for r in t.limit(a.k * 3).to_list():
        r.pop("vetor", None); r["colecao"] = c[6:]; r["similaridade"] = round(1 - r.pop("_distance"), 4); res.append(r)
res.sort(key=lambda r: -r["similaridade"]); vistos, out, paginas = {}, [], set()
for r in res:
    # uma linha por PAGINA: dois trechos da mesma pagina, ou a mesma obra em dois arquivos (copia provavel,
    # nao exata, que o indice nao pulou), ocupavam duas vagas do top-k com a mesma referencia (medido 22/11).
    chave_pag = ((r.get("titulo") or r["arquivo"]).strip().lower(), r["pagina"])
    if chave_pag in paginas: continue
    if vistos.get(r["arquivo"], 0) < a.por_documento:
        vistos[r["arquivo"]] = vistos.get(r["arquivo"], 0) + 1; out.append(r); paginas.add(chave_pag)
    if len(out) == a.k: break
if a.json:
    print(json.dumps(out, ensure_ascii=False, default=str)); sys.exit()
print(f"{len(alvo)} colecoes consultadas, {len(out)} trechos\n")
for i, r in enumerate(out, 1):
    pg = f", p. {r['pagina']}" if r["pagina"] > 0 else ""; ano = f" ({r['ano']})" if r.get("ano") else ""
    vc = f". {r['veiculo']}" if r.get("veiculo") else ""
    print(f"[{i}] {r['similaridade']:.3f} [{r['colecao']} | {r.get('natureza') or '?'}] {r.get('titulo') or r['arquivo']}{ano}{vc}{pg}")
    print(f"    arquivo: {r['arquivo']}\n    {r['trecho'][:400].replace(chr(10), ' ')}\n")
