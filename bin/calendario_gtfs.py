# -*- coding: utf-8 -*-
"""Conta viagens por DIA em cada feed, para achar se existe alguma data em que
os tres operadores estejam vivos ao mesmo tempo."""
import os, zipfile
import pandas as pd

BASE = os.path.expanduser("~/r5_salvador/gtfs")
FEEDS = ["brt.zip", "ottrans.zip", "plataforma.zip"]
DIAS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]


def tab(z, nome):
    zf = zipfile.ZipFile(os.path.join(BASE, z))
    c = [n for n in zf.namelist() if n.endswith(nome)]
    return pd.read_csv(zf.open(c[0]), dtype=str, low_memory=False) if c else None


def viagens_no_dia(f, data):
    cal, cd, tr = tab(f, "calendar.txt"), tab(f, "calendar_dates.txt"), tab(f, "trips.txt")
    val = set()
    if cal is not None:
        ini = pd.to_datetime(cal["start_date"], format="%Y%m%d", errors="coerce")
        fim = pd.to_datetime(cal["end_date"], format="%Y%m%d", errors="coerce")
        ok = (ini <= data) & (fim >= data) & (cal[DIAS[data.dayofweek]] == "1")
        val |= set(cal.loc[ok, "service_id"])
    if cd is not None and not cd.empty:
        d = pd.to_datetime(cd["date"], format="%Y%m%d", errors="coerce")
        val |= set(cd.loc[(d == data) & (cd["exception_type"] == "1"), "service_id"])
        val -= set(cd.loc[(d == data) & (cd["exception_type"] == "2"), "service_id"])
    return int(tr["service_id"].isin(val).sum()) if tr is not None else 0


cache = {f: {} for f in FEEDS}
datas = pd.date_range("2025-10-10", "2025-12-20", freq="D")
linhas = []
for d in datas:
    linhas.append([d] + [viagens_no_dia(f, d) for f in FEEDS])
df = pd.DataFrame(linhas, columns=["data"] + FEEDS)

print("=" * 78)
print("VIAGENS POR DIA EM CADA FEED  (so dias uteis, amostra)")
print("=" * 78)
uteis = df[df["data"].dt.dayofweek < 5]
print("  %-12s %8s %10s %12s   %s" % ("data", "brt", "ottrans", "plataforma", "status"))
for _, r in uteis.head(22).iterrows():
    vivos = sum(1 for f in FEEDS if r[f] > 0)
    print("  %-12s %8d %10d %12d   %d de 3 operadores"
          % (r["data"].date(), r["brt.zip"], r["ottrans.zip"],
             r["plataforma.zip"], vivos))

print()
print("=" * 78)
print("EXISTE ALGUMA DATA COM OS TRES VIVOS?")
print("=" * 78)
tres = df[(df["brt.zip"] > 0) & (df["ottrans.zip"] > 0) & (df["plataforma.zip"] > 0)]
print("  datas com os TRES feeds servindo: %d" % len(tres))
if len(tres):
    print("  %s" % ", ".join(str(x.date()) for x in tres["data"].head(10)))
dois = df[(df["ottrans.zip"] > 0) & (df["plataforma.zip"] > 0)]
print("  datas com ottrans E plataforma juntos: %d" % len(dois))
print()
for f in FEEDS:
    v = df[df[f] > 0]["data"]
    if len(v):
        print("  %-16s serve de %s a %s   (%d dias no periodo analisado)"
              % (f, v.min().date(), v.max().date(), len(v)))
    else:
        print("  %-16s nao serve nenhum dia do periodo" % f)
