#!/usr/bin/env python3
"""Checagens CARAS, para a rodada semanal. Importado por saude.py no modo completo.

Separado do leve de proposito: estas chamam rede, escrevem arquivo temporario, exercitam
cadeia de OCR e varrem disco. Rodar todo dia desperdicaria cota e enlace sem informar mais.
"""
import hashlib, json, os, re, subprocess, time
from pathlib import Path

import saude as S   # reaproveita anota(), sh(), le_env(), dig(), OK/MUDOU/AVISO/QUEBRADO

H = Path.home()
RAIZ = Path(__file__).resolve().parent.parent

LIBS = ["numpy", "pandas", "scipy", "statsmodels", "geopandas", "shapely",
        "pyproj", "pyogrio", "pyarrow", "sklearn", "matplotlib", "openpyxl"]


def _versoes_remotas(host):
    cod = ("import importlib,sys\\n"
           "for m in %r:\\n"
           "    try:\\n"
           "        mod=importlib.import_module('scikit-learn' if m=='sklearn' else m)\\n"
           "        print(m, getattr(mod,'__version__','?'))\\n"
           "    except Exception:\\n"
           "        print(m, 'AUSENTE')\\n") % LIBS
    rc, out = S.sh("timeout 45 tailscale ssh -- mateusaraujoesilva@%s "
                   "'~/venv_lote/bin/python -c %s'" % (host, json.dumps(cod)), 60)
    d = {}
    for l in out.split("\\n"):
        p = l.split()
        if len(p) == 2:
            d[p[0]] = p[1]
    return d


def c_paridade_pacotes():
    """Lote dividido entre duas maquinas com versoes diferentes produz resultado 'parecido',
    nao comparavel. A paridade das 12 bibliotecas e requisito, nao detalhe."""
    import importlib
    local = {}
    for m in LIBS:
        try:
            mod = importlib.import_module("sklearn" if m == "sklearn" else m)
            local[m] = getattr(mod, "__version__", "?")
        except Exception:
            local[m] = "AUSENTE"
    maquinas = {"workstation": local}
    for nome, host in (("geneve", "geneve"), ("zurich", "fedora")):
        v = _versoes_remotas(host)
        if v:
            maquinas[nome] = v
        else:
            S.anota("paridade", nome, S.QUEBRADO,
                    "nao consegui ler as versoes", "tailscale ssh -- mateusaraujoesilva@%s 'echo ok'" % host)
    nbs = [m for m in ("geneve", "zurich") if m in maquinas]
    divergentes = []
    for lib in LIBS:
        vals = {m: maquinas[m].get(lib, "?") for m in nbs}
        if len(set(vals.values())) > 1:
            divergentes.append("%s: %s" % (lib, ", ".join("%s=%s" % kv for kv in sorted(vals.items()))))
    if nbs:
        S.anota("paridade", "notebooks entre si", S.OK if not divergentes else S.QUEBRADO,
                "as %d bibliotecas iguais" % len(LIBS) if not divergentes
                else " | ".join(divergentes)[:280],
                "" if not divergentes else "igualar a versao antes de dividir lote entre as duas",
                valor=len(divergentes))
    ausentes = [l for l in LIBS if local.get(l) == "AUSENTE"]
    S.anota("paridade", "workstation", S.OK if not ausentes else S.AVISO,
            "ausentes no env_transporte: %s" % (", ".join(ausentes) or "nenhuma"))


def c_ocr_notebooks():
    """OCR conferido POR FUNCAO, nao por presenca de programa. Gera PDF, rasteriza, le com
    tesseract e confere as palavras. Duas vezes um teste assim reprovou maquina sadia por
    defeito do proprio teste: comparacao literal com acento, e PATH do venv."""
    cod = r"""
import os,subprocess,sys,tempfile,unicodedata
def sem(s): return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn').upper()
d=tempfile.mkdtemp()
pdf=os.path.join(d,'t.pdf'); png=os.path.join(d,'t.png')
subprocess.run(['python','-c','pass'],capture_output=True)
try:
    import fitz
    doc=fitz.open(); pg=doc.new_page(); pg.insert_text((72,120),'RELATORIO TECNICO DE TRAFEGO',fontsize=22); doc.save(pdf); doc.close()
except Exception as e:
    print('SEM_PYMUPDF',e); sys.exit(0)
subprocess.run(['pdftoppm','-r','300','-png','-singlefile',pdf,png[:-4]],capture_output=True)
t=subprocess.run(['tesseract',png,'stdout','-l','por'],capture_output=True,text=True).stdout
ok = 'RELATORIO' in sem(t) and 'TRAFEGO' in sem(t)
print('OCR_OK' if ok else 'OCR_FALHOU', repr(t.strip()[:60]))
"""
    for nome, host in (("geneve", "geneve"), ("zurich", "fedora")):
        rc, out = S.sh("timeout 90 tailscale ssh -- mateusaraujoesilva@%s "
                       "'~/venv_lote/bin/python -c %s'" % (host, json.dumps(cod)), 110)
        if "OCR_OK" in out:
            S.anota("ocr", nome, S.OK, "cadeia completa funcionando (PDF, 300 dpi, tesseract por)")
        elif "SEM_PYMUPDF" in out:
            S.anota("ocr", nome, S.AVISO, "pymupdf ausente no venv_lote, teste nao conclusivo",
                    "tailscale ssh -- mateusaraujoesilva@%s '~/venv_lote/bin/pip install pymupdf'" % host)
        else:
            S.anota("ocr", nome, S.QUEBRADO, out[-140:],
                    "sudo dnf install tesseract tesseract-langpack-por poppler-utils qpdf")


def c_pino_mcp():
    """O pino mcp<2 e trava, nao anotacao: um upgrade distraido derruba os nove servidores.
    Conferir com --dry-run, NUNCA com o comando real. Em 24/10 eu testei com o comando real
    em producao e mudei o estado que estava medindo."""
    for venv in (H/"TransportMCP/.venv", H/"env_transporte"):
        pip = venv/"bin/pip"
        if not pip.exists():
            S.anota("pinos", venv.name, S.AVISO, "pip nao encontrado em %s" % venv, "")
            continue
        conf = venv/"pip.conf"
        tem = conf.exists() and "constraint" in conf.read_text(encoding="utf-8", errors="replace")
        # PROVA POR DIFERENCA, as duas pontas com --dry-run. Rodar o comando REAL para testar
        # a guarda mudaria o estado que se esta medindo: erro cometido em 24/10, que subiu o
        # mcp de 1.29 para 1.30 em producao e quebrou a paridade com o Windows.
        def alvo(prefixo):
            rc, o = S.sh("%s%s install --dry-run -U mcp 2>&1 | "
                         "grep -oE 'mcp-[0-9]+\\.[0-9]+(\\.[0-9]+)?' | head -1" % (prefixo, pip), 120)
            return o.strip()
        com = alvo("")
        sem = alvo("PIP_CONFIG_FILE=/dev/null ")
        # sem saida com a trava significa "nada a instalar", que e o comportamento desejado
        seguro = tem and (com == "" or com.startswith("mcp-1"))
        S.anota("pinos", "%s: mcp" % venv.name, S.OK if seguro else S.QUEBRADO,
                "arquivo de restricao: %s | com a trava: %s | sem a trava: %s"
                % ("sim" if tem else "NAO", com or "nada a instalar", sem or "?"),
                "" if seguro else "echo -e '[install]\\nconstraint = "
                                  "~/ecossistema/config/restricoes_pip.txt' > %s" % conf,
                valor="%s|%s" % (com or "-", sem or "-"))


def c_espelho_producao():
    """Espelho de versionamento NAO e producao. Comparar com fim de linha NORMALIZADO: em
    23/10 341 linhas 'diferentes' eram exatamente 341 bytes de CRLF contra LF."""
    esp = RAIZ/"mcp"/"windows"
    prods = [Path("/media/mateus/DADOS_01/TransportMCP")]
    if not esp.is_dir():
        S.anota("espelho", "pasta", S.AVISO, "nao encontrada", "")
        return
    def h(p):
        try:
            t = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            t = "\n".join(l.rstrip() for l in t.split("\n"))
            return hashlib.sha256(t.encode()).hexdigest()[:12]
        except Exception:
            return None
    for prod in prods:
        if not prod.is_dir():
            S.anota("espelho", str(prod), S.AVISO, "nao acessivel agora (D: desmontado?)", "")
            continue
        # EXCECAO DELIBERADA, registrada no CLAUDE.md: o argon_mcp.py roda da copia
        # sincronizada pelo Syncthing, e nao de D:\\TransportMCP, porque foi configurado
        # assim de proposito. Marcar como divergencia seria falso positivo, e guarda que
        # acusa o que esta certo vira guarda ignorada.
        EXCECOES = {"argon_mcp.py"}
        difs = []
        for f in sorted(esp.glob("*.py")):
            if f.name in EXCECOES:
                S.anota("espelho", f.name, S.OK, "excecao deliberada: roda da copia sincronizada")
                continue
            alvo = prod/f.name
            if not alvo.exists():
                difs.append(f.name + " (ausente na producao)")
            elif h(f) != h(alvo):
                difs.append(f.name + " (conteudo diferente)")
        S.anota("espelho", prod.name, S.OK if not difs else S.QUEBRADO,
                "todos iguais" if not difs else " | ".join(difs)[:260],
                "" if not difs else "copiar do espelho para a producao com o Claude Desktop FECHADO",
                valor=len(difs))


def c_indices():
    base = Path("/mnt/nvme_lexar/datasets_sig/indices")
    if not base.is_dir():
        S.anota("indices", "pasta", S.AVISO, "nao encontrada", "")
        return
    cols = sorted(p.name for p in base.glob("*.lance"))
    if not cols:
        cols = sorted(p.name for p in base.iterdir() if p.is_dir())
    S.anota("indices", "colecoes", S.OK, "%d: %s" % (len(cols), ", ".join(cols)[:160]),
            valor=len(cols))
    cat = H/"base_conhecimento"/"catalogo.jsonl"
    if cat.exists():
        rc, n = S.sh("wc -l < %s" % cat)
        S.anota("indices", "catalogo do acervo", S.OK, "%s documentos" % n.strip(), valor=n.strip())


def c_higiene_disco():
    """MEDE e PROPOE, nunca apaga. Entrega manifesto com tamanho e motivo, para Mateus aprovar.
    Todo find usa -xdev: sem isso a varredura atravessa a montagem do Drive e nao termina."""
    SAIDA = H/"base_conhecimento"/"saude"
    SAIDA.mkdir(parents=True, exist_ok=True)
    manifesto, total = [], 0
    regras = [
        ("cache de pip",        "%s -xdev -path '*/.cache/pip' -prune" % H,            "reconstruivel"),
        ("cache de pre-commit", "%s/.cache/pre-commit" % H,                            "reconstruivel"),
        ("__pycache__",         None,                                                  "reconstruivel"),
        ("log antigo (>90d)",   None,                                                  "historico ja consolidado"),
        ("tmp do scratch",      "/mnt/nvme_lexar/scratch_tmp",                         "temporario"),
    ]
    # __pycache__ e .pyc
    rc, out = S.sh("find %s -xdev -type d -name __pycache__ -printf '%%s\\n' 2>/dev/null | "
                   "awk '{s+=$1} END{print s+0}'" % H, 90)
    try:
        b = int(out.strip() or 0)
    except Exception:
        b = 0
    if b > 0:
        manifesto.append(("__pycache__ na pasta pessoal", b, "reconstruivel pelo proprio Python",
                          "find ~ -xdev -type d -name __pycache__ -exec rm -rf {} +"))
        total += b
    # caches conhecidos
    for rot, cam in (("cache do pip", "%s/.cache/pip" % H),
                     ("cache do Docling", "%s/ecossistema/cache" % H),
                     ("scratch do NVMe", "/mnt/nvme_lexar/scratch_tmp"),
                     ("cache do restic", "%s/.cache/restic" % H)):
        rc, out = S.sh("du -sb '%s' 2>/dev/null | cut -f1" % cam, 60)
        try:
            b = int(out.strip() or 0)
        except Exception:
            b = 0
        if b > 50 * 1048576:
            manifesto.append((rot, b, "cache reconstruivel", "rm -rf '%s'/*" % cam))
            total += b
    # logs antigos
    rc, out = S.sh("find %s -xdev -maxdepth 3 -name '*.log' -mtime +90 -printf '%%s\\n' 2>/dev/null | "
                   "awk '{s+=$1} END{print s+0}'" % H, 60)
    try:
        b = int(out.strip() or 0)
    except Exception:
        b = 0
    if b > 10 * 1048576:
        manifesto.append(("logs com mais de 90 dias", b, "historico ja consolidado no CLAUDE.md",
                          "find ~ -xdev -maxdepth 3 -name '*.log' -mtime +90 -delete"))
        total += b
    # dez maiores diretorios, para o caso de nada casar com as regras
    rc, maiores = S.sh("du -xh --max-depth=1 %s 2>/dev/null | sort -rh | head -11 | tail -10" % H, 120)
    arq = SAIDA/("higiene_%s.md" % time.strftime("%Y%m%d"))
    L = ["# Higiene de disco, proposta", "",
         time.strftime("%d/%m/%Y %H:%M") + "  |  NADA foi apagado: esta e uma proposta para aprovacao",
         "", "## Candidatos", "", "| item | tamanho | motivo |", "|---|---|---|"]
    for rot, b, motivo, _cmd in manifesto:
        L.append("| %s | %.2f GB | %s |" % (rot, b/1073741824.0, motivo))
    L += ["", "**Total liberavel: %.2f GB**" % (total/1073741824.0), "",
          "## Comandos, um por item, para rodar conferindo antes", ""]
    for rot, b, _m, cmd in manifesto:
        L += ["%s (%.2f GB):" % (rot, b/1073741824.0), "```", cmd, "```", ""]
    L += ["## Dez maiores diretorios da pasta pessoal", "", "```", maiores, "```", "",
          "Varredura feita com -xdev: nao atravessa a montagem do Google Drive nem o D:."]
    arq.write_text("\n".join(L), encoding="utf-8")
    S.anota("higiene", "proposta", S.OK if total == 0 else S.AVISO,
            "%.2f GB em %d itens candidatos" % (total/1073741824.0, len(manifesto)),
            "cat %s" % arq, valor=round(total/1073741824.0, 2))


CHECAGENS = [c_paridade_pacotes, c_ocr_notebooks, c_pino_mcp, c_espelho_producao,
             c_indices, c_higiene_disco]
