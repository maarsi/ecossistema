#!/usr/bin/env python3
"""
ciencia_liberar.py - trava de entrada da pasta de agregados do Claude Science

POR QUE EXISTE. O Claude Science executa codigo na workstation, mas o modelo e remoto:
o que ele le sai da maquina. A protecao nao e "rodar local", e o modelo nao alcancar o
microdado. A sandbox dele exige cartao de aprovacao por caminho, entao basta que so
~/ciencia esteja aprovada. Esta rotina e o que impede microdado de chegar ali por
descuido, e recusa em vez de avisar.

USO
  ciencia_liberar.py --origem <microdado> --candidato <agregado> --projeto <nome>
                     [--limiar-linhas 0.1] [--celula-minima 5] [--forcar "<justificativa>"]

RECUSA, e nao libera, quando:
  1. nome de coluna parece identificador
  2. coluna de texto com alta unicidade e comprimento tipico de nome ou endereco
  3. o candidato nao e suficientemente menor que a origem (parece copia, nao agregado)
  4. existe celula de contagem menor que --celula-minima
Em todos os casos a decisao, o motivo e as contagens vao para o manifesto.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import sys

RAIZ = pathlib.Path.home() / "ciencia"
MANIFESTOS = RAIZ / "_manifestos"

# Padroes de nome de coluna que identificam respondente. Lista explicita, nao heuristica
# de prefixo: guarda sobre palpite nao e guarda.
IDENT = re.compile(
    r"(^|_)(nome|sobrenome|cpf|cnpj|rg|documento|doc|telefone|fone|celular|email|"
    r"e_mail|endereco|logradouro|numero_casa|complemento|cep|matricula|cadastro|"
    r"respondente|entrevistado|motorista|placa|chassi|prontuario|titulo_eleitor|"
    r"lat_domicilio|lon_domicilio|latitude_origem_exata|id_pessoa|id_individuo)($|_)",
    re.IGNORECASE,
)

COLUNAS_CONTAGEM = re.compile(r"(^|_)(n|freq|frequencia|contagem|count|qtd|quantidade|"
                              r"casos|obs|observacoes)($|_)", re.IGNORECASE)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ler_tabela(p):
    """Devolve (colunas, linhas) ou (None, None) se nao for tabela reconhecida."""
    suf = p.suffix.lower()
    if suf in (".csv", ".txt", ".tsv"):
        import csv
        sep = "\t" if suf == ".tsv" else None
        with open(p, newline="", encoding="utf-8-sig", errors="replace") as f:
            amostra = f.read(64 * 1024)
            f.seek(0)
            if sep is None:
                try:
                    sep = csv.Sniffer().sniff(amostra, delimiters=",;\t|").delimiter
                except Exception:
                    sep = ","
            r = csv.reader(f, delimiter=sep)
            try:
                cols = next(r)
            except StopIteration:
                return [], []
            return cols, list(r)
    if suf in (".xlsx", ".xls"):
        try:
            import openpyxl
        except ImportError:
            return None, None
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        cols = [str(c) if c is not None else "" for c in next(it, ())]
        return cols, [list(x) for x in it]
    return None, None


def varrer(pasta, celula_minima):
    """Confere uma PASTA antes de ela receber cartao de aprovacao no Claude Science.

    O criterio NAO e "e de cliente", que seria juizo caso a caso e por isso regra
    descumprida de rotina. O criterio e "contem registro individual". Esta varredura le
    APENAS o cabecalho de cada tabela e nao devolve nome de coluna nem valor: so o nome
    do arquivo e o tipo de marca, para a propria varredura nao virar vazamento.
    """
    pasta = pathlib.Path(pasta).expanduser()
    if not pasta.is_dir():
        print(f"ERRO: nao e pasta: {pasta}")
        return 2
    tabelas, marcados, ilegiveis, outros = 0, [], 0, 0
    for f in sorted(pasta.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".csv", ".tsv", ".txt", ".xlsx", ".xls"):
            outros += 1
            continue
        tabelas += 1
        try:
            cols, linhas = ler_tabela(f)
        except Exception:
            ilegiveis += 1
            continue
        if cols is None:
            ilegiveis += 1
            continue
        marcas = []
        if any(IDENT.search(str(c)) for c in cols):
            marcas.append("coluna identificadora")
        for i, c in enumerate(cols):
            vals = [str(r[i]) for r in linhas[:500] if i < len(r) and r[i] not in (None, "")]
            if len(vals) < 20:
                continue
            unic = len(set(vals)) / len(vals)
            comp = sum(len(v) for v in vals) / len(vals)
            nao_num = sum(1 for v in vals if not re.fullmatch(r"[-+0-9.,eE ]+", v))
            if unic > 0.8 and comp > 12 and nao_num > len(vals) * 0.5:
                marcas.append("texto livre de alta unicidade")
                break
        if marcas:
            marcados.append((f.relative_to(pasta), sorted(set(marcas))))

    print("=" * 74)
    print(f"VARREDURA DE PASTA - {pasta}")
    print("=" * 74)
    print(f"  tabelas examinadas : {tabelas}")
    print(f"  outros arquivos    : {outros} (nao examinados: a varredura so le tabela)")
    print(f"  ilegiveis          : {ilegiveis}")
    print(f"  COM MARCA          : {len(marcados)}")
    for rel, marcas in marcados[:40]:
        print(f"    {str(rel)[:70]:72s} {', '.join(marcas)}")
    if len(marcados) > 40:
        print(f"    ... e mais {len(marcados)-40}")
    print()
    if marcados:
        print("  NAO conceder cartao de aprovacao a esta pasta como ela esta. Ou mover os")
        print("  arquivos marcados para fora, ou conceder so a subpasta sem eles, ou passar")
        print("  o material por --origem/--candidato.")
    else:
        print("  Nenhuma marca de registro individual nas tabelas examinadas. ATENCAO: os")
        print(f"  {outros} arquivos de outro tipo (pdf, docx, shp, imagem) NAO foram examinados;")
        print("  a ausencia de marca aqui nao e atestado sobre eles.")
    print("=" * 74)
    return 1 if marcados else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--varrer", default=None,
                    help="confere uma pasta antes de ela receber cartao de aprovacao")
    ap.add_argument("--origem", required=False)
    ap.add_argument("--candidato", required=False)
    ap.add_argument("--projeto", required=False)
    ap.add_argument("--limiar-linhas", type=float, default=0.10)
    ap.add_argument("--celula-minima", type=int, default=5)
    ap.add_argument("--forcar", default="")
    a = ap.parse_args()

    if a.varrer:
        return varrer(a.varrer, a.celula_minima)
    for obrig in ("origem", "candidato", "projeto"):
        if not getattr(a, obrig):
            print(f"ERRO: --{obrig} e obrigatorio fora do modo --varrer")
            return 2

    org = pathlib.Path(a.origem).expanduser()
    cand = pathlib.Path(a.candidato).expanduser()
    for p, r in ((org, "origem"), (cand, "candidato")):
        if not p.is_file():
            print(f"ERRO: {r} nao e arquivo: {p}")
            return 2

    # O candidato nao pode estar dentro da pasta aprovada antes de passar pela trava.
    if RAIZ in cand.resolve().parents:
        print(f"ERRO: o candidato ja esta dentro de {RAIZ}. Produza fora e libere por aqui.")
        return 2

    recusas = []
    cols_c, linhas_c = ler_tabela(cand)
    cols_o, linhas_o = ler_tabela(org)

    if cols_c is None:
        recusas.append("candidato nao e tabela reconhecida (csv, tsv, xlsx): a trava nao "
                       "sabe conferir identificador nem celula pequena neste formato")
    else:
        # 1. nome de coluna
        marcadas = [c for c in cols_c if IDENT.search(str(c))]
        if marcadas:
            recusas.append(f"coluna com nome de identificador: {marcadas}")

        # 2. texto com alta unicidade
        for i, c in enumerate(cols_c):
            vals = [str(r[i]) for r in linhas_c if i < len(r) and r[i] not in (None, "")]
            if len(vals) < 20:
                continue
            unic = len(set(vals)) / len(vals)
            comp = sum(len(v) for v in vals) / len(vals)
            nao_num = sum(1 for v in vals[:200] if not re.fullmatch(r"[-+0-9.,eE ]+", v))
            if unic > 0.8 and comp > 12 and nao_num > len(vals[:200]) * 0.5:
                recusas.append(f"coluna '{c}' com unicidade {unic:.2f} e comprimento medio "
                               f"{comp:.0f}: parece texto livre identificavel")

        # 3. tamanho relativo
        if linhas_o is not None and len(linhas_o) > 0:
            raz = len(linhas_c) / len(linhas_o)
            if raz > a.limiar_linhas:
                recusas.append(f"candidato tem {len(linhas_c)} linhas contra {len(linhas_o)} "
                               f"da origem, razao {raz:.3f} acima do limiar "
                               f"{a.limiar_linhas}: parece copia ou recorte, nao agregado")

        # 4. celula pequena, controle de divulgacao estatistica
        for i, c in enumerate(cols_c):
            if not COLUNAS_CONTAGEM.search(str(c)):
                continue
            peq = []
            for r in linhas_c:
                if i >= len(r):
                    continue
                try:
                    v = float(str(r[i]).replace(",", "."))
                except (TypeError, ValueError):
                    continue
                if 0 < v < a.celula_minima:
                    peq.append(v)
            if peq:
                recusas.append(f"coluna de contagem '{c}' tem {len(peq)} celula(s) com "
                               f"valor abaixo de {a.celula_minima}: risco de reidentificacao")

    agora = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    liberado = not recusas or bool(a.forcar)

    manifesto = {
        "quando": agora,
        "projeto": a.projeto,
        "origem": {"caminho": str(org), "sha256": sha(org),
                   "linhas": None if linhas_o is None else len(linhas_o)},
        "candidato": {"caminho": str(cand), "sha256": sha(cand),
                      "linhas": None if linhas_c is None else len(linhas_c),
                      "colunas": cols_c},
        "parametros": {"limiar_linhas": a.limiar_linhas, "celula_minima": a.celula_minima},
        "recusas": recusas,
        "liberado": liberado,
        "forcado": a.forcar or None,
    }

    print("=" * 74)
    print(f"TRAVA DE LIBERACAO PARA O CLAUDE SCIENCE - projeto {a.projeto}")
    print("=" * 74)
    print(f"  origem   : {org.name}  sha256={manifesto['origem']['sha256'][:12]}  "
          f"linhas={manifesto['origem']['linhas']}")
    print(f"  candidato: {cand.name}  sha256={manifesto['candidato']['sha256'][:12]}  "
          f"linhas={manifesto['candidato']['linhas']}")
    print()
    if recusas:
        print(f"  {len(recusas)} RECUSA(S):")
        for r in recusas:
            print(f"    - {r}")
    else:
        print("  nenhuma recusa.")

    destino = None
    if liberado:
        pasta = RAIZ / a.projeto
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / cand.name
        shutil.copy2(cand, destino)
        manifesto["destino"] = str(destino)
        print()
        if a.forcar:
            print("  LIBERADO SOB JUSTIFICATIVA EXPLICITA, com as recusas acima registradas:")
            print(f"    {a.forcar}")
        print(f"  copiado para {destino}")
    else:
        print()
        print("  NAO LIBERADO. Corrija o agregado, ou libere com --forcar e a justificativa,")
        print("  que fica gravada no manifesto e deve ser citada no entregavel.")

    MANIFESTOS.mkdir(parents=True, exist_ok=True)
    # O nome do manifesto NAO pode colidir. A primeira versao usava so o horario em
    # segundos mais o nome do candidato: duas decisoes sobre o mesmo arquivo no mesmo
    # segundo se sobrescreviam em silencio, e a trilha de auditoria perdia um registro
    # sem erro nenhum. A bateria sintetica so pegou isso porque conferiu a CONTAGEM de
    # manifestos contra a de casos, nao o conteudo do ultimo.
    base = f"{agora.replace(':', '').replace('-', '')}_{a.projeto}_{cand.stem}"
    alvo = MANIFESTOS / f"{base}.json"
    seq = 1
    while alvo.exists():
        alvo = MANIFESTOS / f"{base}_{seq:02d}.json"
        seq += 1
    alvo.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  manifesto: {alvo}")
    print("=" * 74)
    return 0 if liberado else 1


if __name__ == "__main__":
    sys.exit(main())
