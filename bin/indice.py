#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""indice.py - indice semantico local de acervo documental (LanceDB + papel 'embeddings' via Ollama).

  indice.py indexar <pasta> --nome <colecao> [--incluir-codigo]
  indice.py buscar <colecao> "<pergunta>" [-k 6]
  indice.py validar <colecao> [-n 20]      valida com perguntas geradas sobre trechos sorteados
  indice.py listar

Manuais de software e referencias genericas: excluir com --excluir e indexar em colecao propria.
Tudo local. Cada trecho guarda arquivo e pagina. Reindexacao incremental por hash: so reprocessa o que mudou.
Formatos: PDF (PyMuPDF, por pagina), DOCX, DOC (via LibreOffice), MD, TXT; --incluir-codigo acrescenta .py e .sql.
Dados (CSV, XLSX, SHP, ZIP) ficam de fora de proposito. PDF sem camada de texto e listado como pendente de OCR.
"""
import argparse, hashlib, json, os, random, re, subprocess, sys, tempfile, time
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parent.parent
BASE = Path("/mnt/nvme_lexar/datasets_sig/indices")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
MODELO = json.loads((RAIZ / "config" / "papeis.json").read_text(encoding="utf-8"))["embeddings"]["modelo"]
TAM, SOBRE, LOTE = 1200, 200, 32
EXCLUIR = ["_archive", "_to_delete", ".git", "__pycache__", ".venv"]
DOCS, CODIGO = {".pdf", ".docx", ".doc", ".md", ".txt"}, {".py", ".sql"}


def caminho_ubuntu(c):
    c = c.replace("\\", "/")
    return "/media/mateus/DADOS_01/" + c[3:] if c.lower().startswith("d:/") else c


def hash_arq(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:24]


def docx_texto(p):
    import docx
    d = docx.Document(p)
    partes = [x.text for x in d.paragraphs if x.text.strip()]
    for t in d.tables:
        for lin in t.rows:
            partes.append(" | ".join(c.text.strip() for c in lin.cells))
    return "\n".join(partes)


def extrair_docling(p):
    """Lista de (pagina, texto) vinda do converter.py, que usa Docling com TableFormer.

    POR QUE EXISTE: a extracao por PyMuPDF devolve o texto corrido da pagina e PERDE a
    estrutura de tabela. Em manual de orgao, norma e EVTEA o dado esta na tabela, nao no
    paragrafo, entao o indice ficava cego justamente onde mais importa. O converter.py ja
    fazia reconhecimento de estrutura de tabela na GPU desde sempre; faltava o indice usa-lo.

    De brinde, o converter devolve suspeita_digitalizado e sabe rodar OCR: documento sem
    camada de texto e reprocessado com OCR automaticamente, em vez de virar pendencia.

    O markdown traz marcadores <!-- pagina N: inicio/fim -->, entao a pagina da citacao e
    preservada e o resto do indice.py nao muda.
    """
    sys.path.insert(0, str(RAIZ / "bin"))
    import converter as conv
    md, info = conv.converter(str(p), ocr=False)
    if info.get("suspeita_digitalizado"):
        md, info = conv.converter(str(p), ocr=True)
    texto = Path(md).read_text(encoding="utf-8", errors="replace")
    blocos = re.findall(r"<!-- pagina (\d+): inicio -->(.*?)<!-- pagina \1: fim -->",
                        texto, re.S)
    if blocos:
        return [(int(n), t) for n, t in blocos]
    # formato sem paginas (DOCX, XLSX, HTML) ou PDF sem paginas detectadas
    corpo = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    return [(-1, corpo)]


def pdf_ocr_no_cache(p):
    """PDF ja processado por OCR no cache do converter.py (bin/ocr_lote.py grava ali), ou None."""
    sys.path.insert(0, str(RAIZ / "bin"))
    import converter as conv
    q = conv.CACHE / f"{conv.chave_cache(p, ocr=True)}_ocr.pdf"
    return q if q.exists() and conv._ocr_valido(p, q) else None


_PAL = re.compile(r"^[A-Za-z\u00C0-\u00FF]{2,}$"); _VOG = re.compile(r"[aeiouAEIOU\u00E1\u00E9\u00ED\u00F3\u00FA\u00E2\u00EA\u00F4\u00E3\u00F5\u00E0\u00C1\u00C9\u00CD\u00D3\u00DA\u00C2\u00CA\u00D4\u00C3\u00D5]")


def legibilidade(pags):
    """Mediana, por pagina com 20+ palavras, da fracao de palavras plausiveis (so letras, 2+, com vogal).
    Texto normal fica entre 0,7 e 0,95; camada corrompida perto de 0. None se nao ha pagina avaliavel."""
    v = []
    for _, t in pags:
        tk = t.split()
        if len(tk) >= 20:
            v.append(sum(1 for x in tk if _PAL.match(x.strip('.,;:()"\'')) and _VOG.search(x)) / len(tk))
    if not v:
        return None
    v.sort()
    return v[len(v) // 2]


def extrair(p):
    """Lista de (pagina, texto). pagina = -1 quando o formato nao tem paginas.
    PDF sem camada de texto usa o PDF ja processado por OCR do cache, quando existe: assim o
    OCR distribuido de 21/11/2026 (141 documentos, 24 mil paginas) nao vira pendencia de novo."""
    s = p.suffix.lower()
    if s == ".pdf":
        import pymupdf
        with pymupdf.open(p) as d:
            pags = [(i + 1, pg.get_text()) for i, pg in enumerate(d)]
        # 22/11/2026: "tem texto" nao e "tem texto legivel". PDF com codificacao de fonte quebrada devolve
        # texto ilegivel ("$ +cF!AF/:=NL", Ferraz e Torres); 61 de 1.780 documentos. Usa o OCR do cache
        # tanto para o que nao tem texto quanto para o que tem texto ilegivel.
        leg = legibilidade(pags)
        if sum(len(t.strip()) for _, t in pags) < 100 * max(1, len(pags)) or (leg is not None and leg < 0.5):
            q = pdf_ocr_no_cache(p)
            if q is not None:
                with pymupdf.open(q) as d:
                    return [(i + 1, pg.get_text()) for i, pg in enumerate(d)]
        return pags
    if s == ".docx":
        return [(-1, docx_texto(p))]
    if s == ".doc":
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["soffice", "--headless", "--convert-to", "docx", "--outdir", tmp, str(p)],
                           capture_output=True, timeout=180)
            out = Path(tmp) / (p.stem + ".docx")
            return [(-1, docx_texto(out))] if out.exists() else []
    return [(-1, p.read_text(encoding="utf-8", errors="replace"))]


def fatiar(texto):
    texto = re.sub(r"[ \t]+", " ", texto).strip()
    if len(texto) <= TAM:
        return [texto] if len(texto) > 40 else []
    out, i = [], 0
    while i < len(texto):
        fim = min(len(texto), i + TAM)
        if fim < len(texto):
            q = texto.rfind("\n", i + TAM // 2, fim)
            fim = q if q > 0 else fim
        out.append(texto[i:fim].strip())
        if fim >= len(texto):
            break
        i = max(fim - SOBRE, i + 1)
    return [x for x in out if len(x) > 40]


def embed(textos):
    vs = []
    for k in range(0, len(textos), LOTE):
        r = requests.post(f"{OLLAMA}/api/embed", timeout=600,
                          json={"model": MODELO, "input": textos[k:k + LOTE], "keep_alive": "30m"}).json()
        if r.get("error"):
            sys.exit(f"ERRO embeddings: {r['error'][:150]}")
        vs += r["embeddings"]
    return vs


def abrir(nome):
    import lancedb
    return lancedb.connect(str(BASE / nome))


META = ("titulo", "ano", "natureza", "subarea_principal", "subarea_secundaria", "veiculo")


def tabela(registros):
    """Tabela Arrow com o vetor como lista de tamanho fixo (formato que o LanceDB reconhece).

    Quando ha catalogo, acrescenta colunas de metadado por trecho, para a busca aceitar
    filtro (natureza, subarea, ano). Sem catalogo o esquema e o antigo, de quatro colunas,
    para nao quebrar colecao ja existente."""
    import pyarrow as pa
    dim = len(registros[0]["vetor"])
    cols = {"arquivo": [r["arquivo"] for r in registros],
            "pagina": pa.array([r["pagina"] for r in registros], pa.int32()),
            "trecho": [r["trecho"] for r in registros],
            "vetor": pa.array([r["vetor"] for r in registros], type=pa.list_(pa.float32(), dim))}
    # ano chega como int, None, ou '' quando o catalogo nao tem: '' derrubava a indexacao inteira
    # (medido em 21/11/2026, abortou no terceiro arquivo). Qualquer coisa que nao seja ano vira nulo.
    def _ano(x):
        try:
            a = int(str(x).strip()); return a if 1800 <= a <= 2100 else None
        except (TypeError, ValueError):
            return None
    if any(k in registros[0] for k in META):
        cols["ano"] = pa.array([_ano(r.get("ano")) for r in registros], pa.int32())
        for k in ("titulo", "natureza", "subarea_principal", "subarea_secundaria", "veiculo"):
            cols[k] = [(r.get(k) or "") for r in registros]
    return pa.table(cols)


def carregar_catalogo(caminho):
    """{arquivo relativo: metadado}. O catalogo decide DOIS usos: o metadado que vai para o
    indice e o roteamento do extrator (Docling so onde a tabela importa)."""
    if not caminho:
        return {}
    cat = {}
    for lin in Path(os.path.expanduser(caminho)).read_text(encoding="utf-8").splitlines():
        if not lin.strip():
            continue
        try:
            r = json.loads(lin)
        except Exception:
            continue
        if r.get("status") == "ok":
            cat[r["arquivo"]] = {k: r.get(k) for k in META}
            cat[r["arquivo"]]["_duplicata"] = r.get("duplicata_tipo") == "exata" and \
                r.get("duplicata") in ("duplicata_raiz", "duplicata")
    return cat


def q(s):
    return s.replace("'", "''")


def indexar(pasta, nome, incluir_codigo, excluir_extra=(), via_docling=False,
            catalogo=None, docling_para=("norma_manual", "relatorio_institucional"),
            subarea=None, pular_duplicatas=False, sem_docling=False, refazer_docling=False, refazer=()):
    """subarea: indexa SO os arquivos cuja subarea_principal no catalogo e esta (colecao por
    subarea, decisao de Mateus em 17/11/2026). pular_duplicatas: pula copia EXATA (sha256 igual).
    sem_docling: adia o Docling (fase 1 rapida); o manifesto guarda o extrator usado.
    refazer_docling: fase 2, reextrai com Docling o que a fase 1 fez por PyMuPDF e o roteamento
    manda para o Docling, mesmo com hash inalterado."""
    raiz = Path(caminho_ubuntu(pasta))
    if not raiz.exists():
        sys.exit(f"ERRO: pasta nao encontrada: {raiz}")
    exts = DOCS | (CODIGO if incluir_codigo else set())
    arqs = sorted(p for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in exts
                  and not any(x in p.relative_to(raiz).parts for x in EXCLUIR)
                  and not any(e.replace('\\', '/').strip('/') in p.relative_to(raiz).as_posix() for e in excluir_extra))
    cat = carregar_catalogo(catalogo)
    if subarea or pular_duplicatas:
        if not cat:
            sys.exit("ERRO: --subarea e --pular-duplicatas exigem --catalogo")
        arqs = [p for p in arqs if (rel := str(p.relative_to(raiz))) in cat
                and (not subarea or cat[rel].get("subarea_principal") == subarea)
                and not (pular_duplicatas and cat[rel].get("_duplicata"))]
        print(f"filtro: {len(arqs)} arquivos (subarea={subarea or 'todas'}, duplicatas exatas "
              f"{'puladas' if pular_duplicatas else 'mantidas'})", flush=True)
    if cat:
        print(f"catalogo: {len(cat)} documentos; Docling para {', '.join(docling_para)}", flush=True)
    BASE.mkdir(parents=True, exist_ok=True)
    db = abrir(nome)
    man = {}
    if "arquivos" in db.table_names():
        man = {r["arquivo"]: r for r in db.open_table("arquivos").to_arrow().to_pylist()}
    tbl = db.open_table("trechos") if "trechos" in db.table_names() else None
    t0, novos, pend, puladas, n_trechos = time.time(), [], [], 0, 0
    atuais = set()
    for p in arqs:
        rel = str(p.relative_to(raiz)); atuais.add(rel)
        h = hash_arq(p)
        meta = {k: v for k, v in cat.get(rel, {}).items() if not k.startswith("_")}
        rota_docling = via_docling or (meta.get("natureza") in docling_para)
        refazer_este = rel in refazer   # lista explicita: reextrai mesmo com hash inalterado, sem Docling
        if rel in man and man[rel]["hash"] == h and not refazer_este:
            if not (refazer_docling and rota_docling and man[rel].get("extrator") == "pymupdf"):
                puladas += 1; continue
        # ROTEAMENTO MEDIDO: Docling custa 0,81 s/pagina contra milissegundos do PyMuPDF, e
        # recupera de 27% a 62% mais caracteres em documento normativo, onde o dado esta na
        # tabela. Passar o acervo inteiro por ele custaria 46 h; passar so onde a tabela
        # importa custa uma fracao disso. Medido em 17/11/2026.
        usar_docling = rota_docling and not sem_docling and not refazer_este
        try:
            paginas = extrair_docling(p) if usar_docling else extrair(p)
        except Exception as e:
            pend.append({"arquivo": rel, "hash": h, "n_trechos": 0, "status": f"erro {type(e).__name__}"}); continue
        total = sum(len(t.strip()) for _, t in paginas)
        if p.suffix.lower() == ".pdf" and total < 100 * max(1, len(paginas)):
            pend.append({"arquivo": rel, "hash": h, "n_trechos": 0, "status": "pendente_ocr"}); continue
        registros = [{"arquivo": rel, "pagina": pg, "trecho": tr, **meta}
                     for pg, txt in paginas for tr in fatiar(txt)]
        if not registros:
            pend.append({"arquivo": rel, "hash": h, "n_trechos": 0, "status": "sem_texto"}); continue
        vetores = embed([f"Arquivo: {p.name}" + (f" | pagina {r['pagina']}" if r["pagina"] > 0 else "") + f"\n{r['trecho']}"
                         for r in registros])
        for r, v in zip(registros, vetores):
            r["vetor"] = v
        if tbl is not None:  # sempre substitui trechos antigos do arquivo: seguro contra interrupcao
            tbl.delete(f"arquivo = '{q(rel)}'")
        if tbl is None:
            tbl = db.create_table("trechos", data=tabela(registros))
        else:
            tbl.add(tabela(registros))
        novos.append({"arquivo": rel, "hash": h, "n_trechos": len(registros), "status": "ok",
                      "extrator": "docling" if usar_docling else ("ocr_forcado" if refazer_este else "pymupdf")})
        n_trechos += len(registros)
        print(f"  + {rel[:90]} ({len(registros)} trechos)", flush=True)
        # MANIFESTO PARCIAL a cada 25 arquivos. Antes so era gravado no fim: medido em 21/11/2026,
        # um corte por timeout deixou 175 trechos sem manifesto, e a proxima rodada refaria tudo.
        if len(novos) % 25 == 0:
            parcial = {**man, **{r["arquivo"]: r for r in novos + pend}}
            db.create_table("arquivos", data=list(parcial.values()), mode="overwrite")
    removidos = [a for a in man if a not in atuais]
    for a in removidos:
        if tbl is not None:
            tbl.delete(f"arquivo = '{q(a)}'")
    novo_man = {**{k: v for k, v in man.items() if k in atuais}, **{r["arquivo"]: r for r in novos + pend}}
    if novo_man:
        db.create_table("arquivos", data=list(novo_man.values()), mode="overwrite")
    (BASE / nome / "origem.txt").write_text(str(raiz), encoding="utf-8")
    print(f"INDICE '{nome}': {len(novos)} arquivos indexados ({n_trechos} trechos), {puladas} inalterados, "
          f"{len(removidos)} removidos, {len(pend)} pendentes, {time.time() - t0:.0f} s")
    for r in pend:
        print(f"  pendente: {r['arquivo'][:90]} [{r['status']}]")


def buscar(nome, pergunta, k=6, imprimir=True, filtro=None):
    """filtro: expressao SQL sobre as colunas de metadado, por exemplo
    "natureza = 'norma_manual' AND ano >= 2015". So funciona em colecao indexada com catalogo."""
    db = abrir(nome)
    if "trechos" not in db.table_names():
        sys.exit(f"ERRO: indice '{nome}' vazio ou inexistente.")
    v = embed([pergunta])[0]
    busca = db.open_table("trechos").search(v, vector_column_name="vetor")
    try:
        busca = busca.distance_type("cosine")
    except AttributeError:
        busca = busca.metric("cosine")
    if filtro:
        busca = busca.where(filtro, prefilter=True)
    res = busca.limit(k).to_list()
    if imprimir:
        for i, r in enumerate(res, 1):
            pg = f", p. {r['pagina']}" if r["pagina"] > 0 else ""
            cit = r.get("titulo") or r["arquivo"]
            ano = f" ({r['ano']})" if r.get("ano") else ""
            veic = f". {r['veiculo']}" if r.get("veiculo") else ""
            nat = f" [{r['natureza']}]" if r.get("natureza") else ""
            print(f"[{i}] {1 - r['_distance']:.3f}{nat} | {cit}{ano}{veic}{pg}")
            print(f"    arquivo: {r['arquivo']}")
            print(f"    {r['trecho'][:350].replace(chr(10), ' ')}\n")
    return res


def validar(nome, n):
    sys.path.insert(0, str(RAIZ / "bin")); import llm
    cfg = llm.PAPEIS["doc"]
    linhas = [r for r in abrir(nome).open_table("trechos").to_arrow().select(["arquivo", "pagina", "trecho"]).to_pylist()
              if len(r["trecho"]) > 500]
    random.seed(42); amostra = random.sample(linhas, min(n, len(linhas)))
    top1 = top5 = 0
    for r in amostra:
        pedido = ("Escreva UMA pergunta em portugues que o trecho abaixo responde. Use outras palavras, sem copiar frases, "
                  "sem numeros exatos e sem citar nomes de arquivo. Responda apenas com a pergunta.\n\nTRECHO:\n" + r["trecho"])
        perg, _, _ = llm.chamar_local(cfg["modelo"], pedido, 8192, 80, 0.2)
        perg = llm.limpar_raciocinio(perg).strip().splitlines()[0]
        res = buscar(nome, perg, 5, imprimir=False)
        pos = next((i for i, x in enumerate(res, 1) if x["arquivo"] == r["arquivo"] and x["pagina"] == r["pagina"]), None)
        top1 += pos == 1; top5 += pos is not None
        print(f"  {'OK ' if pos else 'ERR'} pos={pos} | {perg[:95]}")
    print(f"VALIDACAO '{nome}': origem em 1o lugar {top1}/{len(amostra)} | entre os 5 primeiros {top5}/{len(amostra)}")


def listar():
    if not BASE.exists():
        print("nenhum indice"); return
    for d in sorted(BASE.iterdir()):
        try:
            db = abrir(d.name); n = db.open_table("trechos").count_rows()
            origem = (d / "origem.txt").read_text() if (d / "origem.txt").exists() else "?"
            print(f"{d.name:24} {n:7} trechos | {origem}")
        except Exception:
            print(f"{d.name:24} (vazio)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Indice semantico local do ecossistema")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("indexar"); a1.add_argument("pasta"); a1.add_argument("--nome", required=True)
    a1.add_argument("--incluir-codigo", action="store_true")
    a1.add_argument("--excluir", action="append", default=[], help="trecho de caminho a ignorar (repetivel)")
    a1.add_argument("--via-docling", action="store_true",
                    help="forca Docling para TODOS os documentos (custa 0,81 s/pagina)")
    a1.add_argument("--catalogo", help="catalogo .jsonl: acrescenta metadado e roteia o extrator")
    a1.add_argument("--subarea", help="so arquivos desta subarea_principal do catalogo")
    a1.add_argument("--pular-duplicatas", action="store_true", help="pula copia exata (campo duplicata do catalogo)")
    a1.add_argument("--sem-docling", action="store_true", help="fase 1: adia o Docling, registra o extrator")
    a1.add_argument("--refazer-docling", action="store_true", help="fase 2: reextrai com Docling o que foi por PyMuPDF")
    a1.add_argument("--refazer-lista", help="arquivo com caminhos relativos a reextrair mesmo inalterados (sem Docling)")
    a1.add_argument("--docling-para", default="norma_manual,relatorio_institucional",
                    help="naturezas que passam pelo Docling quando ha catalogo")
    a2 = sub.add_parser("buscar"); a2.add_argument("nome"); a2.add_argument("pergunta"); a2.add_argument("-k", type=int, default=6)
    a2.add_argument("--filtro", help="SQL sobre metadado, ex: \"natureza = 'norma_manual' AND ano >= 2015\"")
    a3 = sub.add_parser("validar"); a3.add_argument("nome"); a3.add_argument("-n", type=int, default=20)
    sub.add_parser("listar")
    a = ap.parse_args()
    if a.cmd == "indexar":
        indexar(a.pasta, a.nome, a.incluir_codigo, a.excluir, a.via_docling, a.catalogo,
                tuple(x.strip() for x in a.docling_para.split(",") if x.strip()),
                a.subarea, a.pular_duplicatas, a.sem_docling, a.refazer_docling,
                set(l.strip() for l in open(a.refazer_lista) if l.strip()) if a.refazer_lista else set())
    elif a.cmd == "buscar": buscar(a.nome, a.pergunta, a.k, filtro=a.filtro)
    elif a.cmd == "validar": validar(a.nome, a.n)
    else: listar()
