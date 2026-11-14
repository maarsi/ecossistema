# -*- coding: utf-8 -*-
"""Compara os tres feeds GTFS da RMS para responder uma pergunta objetiva:
o ottrans.zip acrescenta oferta que o plataforma.zip nao tem?
Nao decide por nome de arquivo nem por tamanho: compara conteudo."""
import os, zipfile
import pandas as pd

BASE = os.path.expanduser("~/r5_salvador/gtfs")
FEEDS = ["brt.zip", "ottrans.zip", "plataforma.zip"]
ALVO = pd.Timestamp("2025-11-11")


def tabela(zpath, nome):
    z = zipfile.ZipFile(zpath)
    cand = [n for n in z.namelist() if n.endswith(nome) and not n.startswith("__")]
    if not cand:
        return None
    return pd.read_csv(z.open(cand[0]), dtype=str, low_memory=False)


dados = {}
print("=" * 78)
print("1. TAMANHO DE CADA FEED")
print("=" * 78)
print("  %-16s %8s %8s %9s %10s %9s" %
      ("feed", "agencias", "linhas", "paradas", "viagens", "horarios"))
for f in FEEDS:
    p = os.path.join(BASE, f)
    d = {n: tabela(p, n + ".txt") for n in
         ("agency", "routes", "stops", "trips", "stop_times", "calendar",
          "calendar_dates")}
    dados[f] = d
    print("  %-16s %8s %8s %9s %10s %9s" % (
        f,
        len(d["agency"]) if d["agency"] is not None else "-",
        len(d["routes"]) if d["routes"] is not None else "-",
        len(d["stops"]) if d["stops"] is not None else "-",
        len(d["trips"]) if d["trips"] is not None else "-",
        len(d["stop_times"]) if d["stop_times"] is not None else "-"))

print()
print("=" * 78)
print("2. QUEM SAO AS AGENCIAS")
print("=" * 78)
for f in FEEDS:
    a = dados[f]["agency"]
    if a is None:
        print("  %-16s sem agency.txt" % f)
        continue
    col = "agency_name" if "agency_name" in a.columns else a.columns[0]
    print("  %-16s %s" % (f, " | ".join(sorted(a[col].astype(str).unique()))[:95]))

print()
print("=" * 78)
print("3. O CALENDARIO COBRE 11/11/2025 (terca-feira)?")
print("=" * 78)
for f in FEEDS:
    c = dados[f]["calendar"]
    if c is None:
        print("  %-16s sem calendar.txt" % f)
        continue
    ini = pd.to_datetime(c["start_date"], format="%Y%m%d", errors="coerce")
    fim = pd.to_datetime(c["end_date"], format="%Y%m%d", errors="coerce")
    dentro = ((ini <= ALVO) & (fim >= ALVO) & (c["tuesday"] == "1")).sum()
    print("  %-16s periodo %s a %s   servicos validos na terca: %d de %d" % (
        f, ini.min().date(), fim.max().date(), dentro, len(c)))

print()
print("=" * 78)
print("4. O OTTRANS ESTA CONTIDO NO PLATAFORMA?")
print("=" * 78)


def conjunto(d, tab, col):
    t = d[tab]
    if t is None or col not in t.columns:
        return set()
    return set(t[col].astype(str).str.strip().str.upper())


for chave, (tab, col) in {
        "nome de linha (route_long_name)": ("routes", "route_long_name"),
        "sigla de linha (route_short_name)": ("routes", "route_short_name"),
        "nome de parada (stop_name)": ("stops", "stop_name")}.items():
    o = conjunto(dados["ottrans.zip"], tab, col)
    p = conjunto(dados["plataforma.zip"], tab, col)
    if not o:
        print("  %-34s ottrans nao tem essa coluna" % chave)
        continue
    so_ottrans = o - p
    print("  %-34s ottrans %5d   tambem no plataforma %5d   SO no ottrans %5d"
          % (chave, len(o), len(o & p), len(so_ottrans)))
    if so_ottrans and tab == "routes":
        print("        exemplos so do ottrans: %s"
              % " ; ".join(sorted(so_ottrans)[:6])[:110])

print()
print("=" * 78)
print("5. VEREDITO PRELIMINAR")
print("=" * 78)
o = conjunto(dados["ottrans.zip"], "routes", "route_long_name")
p = conjunto(dados["plataforma.zip"], "routes", "route_long_name")
if o and not (o - p):
    print("  Toda linha do ottrans tem nome igual a alguma do plataforma.")
    print("  Indicio de contencao, NAO prova: nome igual nao garante mesmo")
    print("  itinerario nem mesmo quadro de horarios. Confirmar pela medicao.")
elif o:
    print("  %d linhas do ottrans NAO aparecem no plataforma." % len(o - p))
    print("  A oferta usada em 24/10 estava incompleta. Refazer com os tres.")
else:
    print("  Nao foi possivel comparar por nome de linha.")
