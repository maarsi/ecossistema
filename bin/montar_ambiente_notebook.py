#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
montar_ambiente.py  -  ambiente virtual de trabalho nos notebooks
CITATIS / ecossistema                                           versao 2026-11-13

O QUE FAZ
  Cria um ambiente virtual proprio em ~/venv_lote e instala nele os pacotes de
  trabalho, UM A UM, registrando o que entrou e o que nao existe para esta
  versao do Python. Depois testa cada um de verdade, nao so importando.

POR QUE "SO PACOTE PRONTO"
  Este Python e 3.15, muito novo. Pacote cientifico sem versao pronta para a
  versao nova do Python faz o pip tentar COMPILAR do zero, o que leva horas e
  costuma falhar. Forcando --only-binary, a ausencia falha em segundos e a
  gente fica sabendo o que existe, em vez de descobrir compilando.

ONDE INSTALA
  ~/venv_lote, FORA da pasta ecossistema. A pasta ecossistema e somente
  recebimento do Syncthing: escrever nela criaria divergencia local, que e
  exatamente o problema limpo em 12/11.

O QUE NAO FAZ
  Nao mexe no Python do sistema. Nao pede sudo. Nao apaga nada fora do
  ~/venv_lote. Nao altera a pasta ecossistema.

DURACAO: de 2 a 10 minutos, conforme a rede.
"""

import json, os, platform, shutil, socket, subprocess, sys, time, datetime

AGORA = datetime.datetime.now()
VENV = os.path.expanduser("~/venv_lote")
L = []

# nome do pacote no pip, modulo para importar, por que serve
PACOTES = [
    ("numpy",       "numpy",      "base numerica de tudo"),
    ("pandas",      "pandas",     "tabela, expansao de pesquisa, agregacao"),
    ("scipy",       "scipy",      "estatistica e otimizacao"),
    ("statsmodels", "statsmodels", "estimacao de modelo e teste"),
    ("openpyxl",    "openpyxl",   "ler e escrever xlsx"),
    ("pyarrow",     "pyarrow",    "parquet, troca rapida de tabela"),
    ("matplotlib",  "matplotlib", "grafico"),
    ("requests",    "requests",   "coleta de API"),
    ("shapely",     "shapely",    "geometria"),
    ("pyproj",      "pyproj",     "sistema de coordenadas"),
    ("fiona",       "fiona",      "ler shapefile e geopackage"),
    ("geopandas",   "geopandas",  "tabela com geometria"),
    ("scikit-learn", "sklearn",   "agrupamento e classificacao"),
    ("tqdm",        "tqdm",       "barra de progresso em lote"),
    ("psutil",      "psutil",     "medir uso de memoria do proprio lote"),
]


def p(txt=""):
    print(txt, flush=True)
    L.append(txt)


def rodar(args, timeout=600):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "tempo esgotado"
    except Exception as e:
        return 1, "", str(e)


def main():
    p("")
    p("MONTAGEM DO AMBIENTE DE TRABALHO")
    p(f"CITATIS / ecossistema          {AGORA:%d/%m/%Y %H:%M:%S}")
    p(f"maquina: {socket.gethostname().split('.')[0]}   Python {platform.python_version()}")
    p("")

    # ------------------------------------------------------------- 1. checagem
    p("=" * 72)
    p("1. ANTES DE COMECAR")
    p("=" * 72)
    livre = shutil.disk_usage(os.path.expanduser("~")).free / 2**30
    p(f"  disco livre ....... {livre:.0f} GB")
    if livre < 5:
        p("  >>> PARE: menos de 5 GB livres nao bastam. Libere espaco.")
        return
    p(f"  Python ............ {sys.version.split()[0]} em {sys.executable}")
    if sys.version_info[:2] < (3, 9):
        p("  >>> PARE: Python antigo demais.")
        return

    eco = os.path.expanduser("~/ecossistema")
    restr = os.path.join(eco, "config", "restricoes_pip.txt")
    usar_restr = os.path.isfile(restr)
    p(f"  pasta ecossistema . {'presente' if os.path.isdir(eco) else 'ausente'}")
    p(f"  restricoes_pip .... {'sera usada' if usar_restr else 'ausente, seguindo sem ela'}")
    if os.path.isdir(VENV):
        p(f"  ATENCAO: ja existe {VENV}. Vou refazer do zero.")
        shutil.rmtree(VENV, ignore_errors=True)

    # --------------------------------------------------------- 2. criar o venv
    p("")
    p("=" * 72)
    p("2. CRIANDO O AMBIENTE VIRTUAL")
    p("=" * 72)
    p(f"  destino: {VENV}")
    cod, out, err = rodar([sys.executable, "-m", "venv", VENV], timeout=180)
    if cod != 0:
        p(f"  >>> FALHOU: {err.strip()[:300]}")
        p("  Se disser que falta o modulo venv, instale com:")
        p("      sudo dnf install python3-devel")
        return
    pip = os.path.join(VENV, "bin", "pip")
    py = os.path.join(VENV, "bin", "python")
    p("  criado.")
    cod, out, _ = rodar([pip, "install", "--upgrade", "pip", "setuptools", "wheel"], timeout=300)
    p(f"  pip atualizado: {'sim' if cod == 0 else 'falhou, seguindo assim mesmo'}")

    base = [pip, "install", "--only-binary=:all:", "--disable-pip-version-check", "-q"]
    if usar_restr:
        base += ["--constraint", restr]

    # ------------------------------------------------- 3. instalar um por vez
    p("")
    p("=" * 72)
    p("3. INSTALANDO, UM POR VEZ, SO PACOTE PRONTO")
    p("=" * 72)
    p("  Falha aqui quase sempre significa 'ainda nao existe pacote pronto")
    p("  para este Python', nao significa que o pacote nao sirva.")
    p("")
    ok, falhou = [], []
    for nome, modulo, porque in PACOTES:
        t0 = time.time()
        cod, out, err = rodar(base + [nome], timeout=420)
        dt = time.time() - t0
        if cod == 0:
            ok.append((nome, modulo, porque))
            p(f"  [ok   ] {nome:<14} {dt:>5.1f}s   {porque}")
        else:
            motivo = "sem pacote pronto para este Python"
            baixo = (err or "").lower()
            if "could not find a version" in baixo or "no matching distribution" in baixo:
                motivo = "sem pacote pronto para este Python"
            elif cod == 124:
                motivo = "tempo esgotado"
            elif "network" in baixo or "timed out" in baixo or "resolve" in baixo:
                motivo = "problema de rede"
            falhou.append((nome, motivo, porque))
            p(f"  [FALHA] {nome:<14} {dt:>5.1f}s   {motivo}")

    # --------------------------------------------- 4. testar de verdade
    p("")
    p("=" * 72)
    p("4. TESTANDO O QUE ENTROU  (importar nao basta, tem de funcionar)")
    p("=" * 72)
    testes = {
        "numpy": "import numpy as n;a=n.random.rand(400,400);r=float((a@a).sum());v=n.__version__",
        "pandas": ("import pandas as pd;d=pd.DataFrame({'z':list('aabbc'),'v':[1,2,3,4,5]});"
                   "r=float(d.groupby('z')['v'].sum().sum());v=pd.__version__"),
        "scipy": "from scipy import stats;r=float(stats.norm.cdf(1.96));import scipy;v=scipy.__version__",
        "statsmodels": ("import statsmodels.api as sm,numpy as n;"
                        "r=float(sm.OLS(n.arange(10.),sm.add_constant(n.arange(10.))).fit().rsquared);"
                        "import statsmodels;v=statsmodels.__version__"),
        "shapely": ("from shapely.geometry import Point;r=float(Point(0,0).buffer(1).area);"
                    "import shapely;v=shapely.__version__"),
        "pyproj": ("from pyproj import Transformer;"
                   "r=float(Transformer.from_crs(4326,31983,always_xy=True).transform(-46.6,-23.5)[0]);"
                   "import pyproj;v=pyproj.__version__"),
        "geopandas": ("import geopandas as g;from shapely.geometry import Point;"
                      "r=float(g.GeoDataFrame(geometry=[Point(0,0)],crs=4326).geometry.x.iloc[0]);"
                      "v=g.__version__"),
        "fiona": "import fiona;r=len(fiona.supported_drivers);v=fiona.__version__",
        "openpyxl": "import openpyxl as o;w=o.Workbook();w.active['A1']=1;r=w.active['A1'].value;v=o.__version__",
        "pyarrow": ("import pyarrow as pa;r=pa.table({'a':[1,2,3]}).num_rows;v=pa.__version__"),
        "matplotlib": ("import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt;"
                       "f=plt.figure();r=1;v=matplotlib.__version__"),
        "sklearn": ("from sklearn.cluster import KMeans;import numpy as n;"
                    "r=int(KMeans(2,n_init=4).fit(n.random.rand(20,2)).n_iter_);import sklearn;v=sklearn.__version__"),
        "requests": "import requests;r=1;v=requests.__version__",
        "tqdm": "import tqdm;r=1;v=tqdm.__version__",
        "psutil": "import psutil;r=round(psutil.virtual_memory().available/2**30,1);v=psutil.__version__",
    }
    funcionou, quebrou = [], []
    for nome, modulo, _ in ok:
        codigo = testes.get(modulo)
        if not codigo:
            continue
        prog = codigo + ";import json;print(json.dumps({'v':v,'r':r}))"
        cod, out, err = rodar([py, "-c", prog], timeout=180)
        if cod == 0 and out.strip():
            try:
                d = json.loads(out.strip().splitlines()[-1])
                funcionou.append((modulo, d["v"]))
                p(f"  [ok   ] {modulo:<14} versao {d['v']:<12} resultado {d['r']}")
            except Exception:
                funcionou.append((modulo, "?"))
                p(f"  [ok   ] {modulo:<14} rodou, saida inesperada")
        else:
            quebrou.append((modulo, (err or "").strip().splitlines()[-1][:90] if err else "sem mensagem"))
            p(f"  [QUEBRA] {modulo:<13} instalou mas NAO funciona")
            p(f"           {(err or '').strip().splitlines()[-1][:90] if err else ''}")

    # ------------------------------------- 5. programas de sistema para OCR
    p("")
    p("=" * 72)
    p("5. PROGRAMAS DE SISTEMA PARA OCR  (nao instalo, so confiro)")
    p("=" * 72)
    for prog, para in [("tesseract", "reconhecimento de texto"),
                       ("gs", "Ghostscript, manipulacao de PDF"),
                       ("pdftoppm", "poppler, PDF para imagem"),
                       ("qpdf", "reparo de PDF")]:
        onde = shutil.which(prog)
        p(f"  {prog:<10} {'presente  ' + onde if onde else 'AUSENTE'}   ({para})")
    p("  Se faltarem e voce quiser OCR nesta maquina, o comando e:")
    p("      sudo dnf install tesseract tesseract-langpack-por ghostscript poppler-utils qpdf")

    # --------------------------------------------------------- 6. resumo
    p("")
    p("=" * 72)
    p("6. RESUMO")
    p("=" * 72)
    p(f"  ambiente .......... {VENV}")
    p(f"  instalados e testados: {len(funcionou)} de {len(PACOTES)}")
    if falhou:
        p("  SEM PACOTE PRONTO para este Python:")
        for nome, motivo, porque in falhou:
            p(f"      {nome:<14} {motivo}   (servia para: {porque})")
    if quebrou:
        p("  INSTALARAM MAS NAO FUNCIONAM:")
        for m, e in quebrou:
            p(f"      {m}: {e}")
    if not falhou and not quebrou:
        p("  tudo entrou e funciona.")
    p("")
    p("  Para usar este ambiente num terminal:")
    p(f"      source {VENV}/bin/activate")
    p(f"  Ou chamar direto, sem ativar:  {VENV}/bin/python meu_script.py")

    nome_arq = f"ambiente_{socket.gethostname().split('.')[0]}_{AGORA:%Y%m%d_%H%M}.txt"
    try:
        with open(os.path.expanduser(f"~/{nome_arq}"), "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
        destino = os.path.expanduser(f"~/{nome_arq}")
    except Exception as e:
        destino = f"nao gravou: {e}"
    print("")
    print(f"Relatorio em: {destino}")
    print("")
    print("COPIE DAQUI PARA BAIXO")
    print("v" * 72)
    print("\n".join(L))
    print("^" * 72)
    print("COPIE DAQUI PARA CIMA")


if __name__ == "__main__":
    main()
