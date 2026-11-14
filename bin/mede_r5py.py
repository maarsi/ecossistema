# -*- coding: utf-8 -*-
"""Medicao correta do r5py. A versao anterior errou a construcao a frio:
o cache do r5py e indexado por hash do CONTEUDO, entao copiar o arquivo com
outro nome cai no mesmo cache. Aqui o cache inteiro e desviado para um
diretorio temporario via XDG_CACHE_HOME, sem tocar no cache real de ~/.cache.
O JAR do R5 e copiado para o cache novo para nao rebaixar 64 MB a toa.
"""
import os, shutil, tempfile

CACHE_REAL = os.path.expanduser("~/.cache/r5py")
TMPCACHE = tempfile.mkdtemp(prefix="cache_r5py_")
os.makedirs(os.path.join(TMPCACHE, "r5py"), exist_ok=True)
for j in os.listdir(CACHE_REAL):
    if j.endswith(".jar"):
        shutil.copy2(os.path.join(CACHE_REAL, j),
                     os.path.join(TMPCACHE, "r5py", j))
os.environ["XDG_CACHE_HOME"] = TMPCACHE

import datetime, resource, time, zipfile
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
import r5py

BASE = os.path.expanduser("~/r5_salvador")
OSM = os.path.join(BASE, "salvador.osm.pbf")
FEEDS = [os.path.join(BASE, "gtfs", "brt.zip"),
         os.path.join(BASE, "gtfs", "plataforma.zip")]

pico = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
print("cache desviado para %s" % TMPCACHE, flush=True)
print("arquivos no cache novo: %s" % os.listdir(os.path.join(TMPCACHE, "r5py")),
      flush=True)

t0 = time.time()
rede = r5py.TransportNetwork(OSM, FEEDS)
t_frio = time.time() - t0
print("1. construcao A FRIO (cache vazio) .... %6.1f s   (pico %.2f GB)"
      % (t_frio, pico()), flush=True)

z = zipfile.ZipFile(FEEDS[1])
nome = [n for n in z.namelist() if n.endswith("stops.txt")][0]
stops = pd.read_csv(z.open(nome)).dropna(
    subset=["stop_lat", "stop_lon"]).drop_duplicates("stop_id")
pontos = gpd.GeoDataFrame(
    {"id": stops["stop_id"].astype(str).values},
    geometry=[Point(x, y) for x, y in zip(stops["stop_lon"], stops["stop_lat"])],
    crs="EPSG:4326")
print("   paradas: %d" % len(pontos), flush=True)

MODOS = [r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK]
PARTIDA = datetime.datetime(2025, 11, 11, 7, 0)

for n in (200, 600, len(pontos)):
    sub = pontos.head(n)
    t0 = time.time()
    r = r5py.TravelTimeMatrix(rede, origins=sub, destinations=sub,
                              departure=PARTIDA,
                              departure_time_window=datetime.timedelta(minutes=60),
                              percentiles=[50], transport_modes=MODOS)
    dt = time.time() - t0
    col = "travel_time" if "travel_time" in r.columns else r.columns[-1]
    v = r[col].dropna()
    print("2. matriz %4dx%-4d ... %7.1f s  %9d pares  %5.1f%% alcancados  "
          "mediana %3.0f min  %8.0f pares/s  (pico %.2f GB)"
          % (n, n, dt, len(r), 100.0 * len(v) / max(len(r), 1),
             v.median() if len(v) else float("nan"), len(r) / dt, pico()),
          flush=True)

print("", flush=True)
print("PICO DE MEMORIA: %.2f GB" % pico(), flush=True)
print("CABE NO GENEVE (7 GB de RAM)? %s" % ("SIM" if pico() < 5 else "RISCO"),
      flush=True)
shutil.rmtree(TMPCACHE, ignore_errors=True)
print("cache temporario removido. FIM", flush=True)
