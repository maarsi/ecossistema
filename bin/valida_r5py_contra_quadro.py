# -*- coding: utf-8 -*-
"""VALIDACAO v5. Terceira correcao de SELECAO, nao do motor.

v3: escolhi a opcao de menor duracao total. Deu exato no BRT por sorte.
v4: entre as opcoes da mesma linha, escolhi a de menor tempo EMBARCADO. Erro
    grosseiro: na mesma linha, menos tempo embarcado quer dizer que o R5
    caminhou ate um ponto mais adiante e pegou so um pedaco da viagem.
v5: exige coincidencia de LINHA, de PARADA DE EMBARQUE e de PARADA DE
    DESEMBARQUE com a viagem escriturada. So assim as duas grandezas sao a
    mesma coisa e a comparacao prova alguma coisa.
"""
import datetime, os, zipfile
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
import r5py

BASE = os.path.expanduser("~/r5_salvador")
OSM = os.path.join(BASE, "salvador.osm.pbf")
BRT = os.path.join(BASE, "gtfs", "brt.zip")
PLAT = os.path.join(BASE, "gtfs", "plataforma.zip")
ALVO = pd.Timestamp("2025-11-11")
MIN = lambda td: td.total_seconds() / 60.0
sec = lambda h: sum(int(x) * f for x, f in zip(str(h).split(":"), (3600, 60, 1)))


def tab(zp, n):
    zf = zipfile.ZipFile(zp)
    c = [x for x in zf.namelist() if x.endswith(n)]
    return pd.read_csv(zf.open(c[0]), dtype=str, low_memory=False) if c else None


def casos(zp, rotulo, quantos):
    st, tr = tab(zp, "stop_times.txt"), tab(zp, "trips.txt")
    sp = tab(zp, "stops.txt").drop_duplicates("stop_id").set_index("stop_id")
    ro = tab(zp, "routes.txt").set_index("route_id")
    cal = tab(zp, "calendar.txt")
    ini = pd.to_datetime(cal["start_date"], format="%Y%m%d")
    fim = pd.to_datetime(cal["end_date"], format="%Y%m%d")
    serv = set(cal.loc[(ini <= ALVO) & (fim >= ALVO) & (cal["tuesday"] == "1"),
                       "service_id"])
    tr = tr[tr["service_id"].isin(serv)]
    mapa = tr.set_index("trip_id")["route_id"].to_dict()
    st = st[st["trip_id"].isin(mapa)].copy()
    st["sq"] = st["stop_sequence"].astype(int)
    out, vistos = [], set()
    for tid, g in st.groupby("trip_id", sort=False):
        rid = mapa[tid]
        if rid in vistos:
            continue
        g = g.sort_values("sq")
        if len(g) < 6:
            continue
        a, b = g.iloc[0], g.iloc[-1]
        p0 = sec(a["departure_time"])
        if not (7 * 3600 <= p0 <= 8 * 3600):
            continue
        vistos.add(rid)
        out.append({"feed": rotulo, "rid": str(rid),
                    "linha": str(ro.loc[rid, "route_short_name"]),
                    "sid_o": str(a["stop_id"]), "sid_d": str(b["stop_id"]),
                    "o": sp.loc[a["stop_id"]], "d": sp.loc[b["stop_id"]],
                    "p0": p0, "escrit": (sec(b["arrival_time"]) - p0) / 60.0})
        if len(out) >= quantos:
            break
    return out


LISTA = casos(BRT, "BRT", 6) + casos(PLAT, "PLATAF", 14)
print("casos, um por linha: %d" % len(LISTA), flush=True)
rede = r5py.TransportNetwork(OSM, [BRT, PLAT])
MODOS = [r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK]
print("rede carregada", flush=True)
print("", flush=True)
print("=" * 96, flush=True)
print("%-7s %-6s %-28s %8s %10s %8s" % (
    "feed", "linha", "trecho", "quadro", "R5 igual", "dif"), flush=True)
print("=" * 96, flush=True)

res = []
for c in LISTA:
    o, d = c["o"], c["d"]
    go = gpd.GeoDataFrame({"id": ["O"]}, geometry=[Point(
        float(o["stop_lon"]), float(o["stop_lat"]))], crs="EPSG:4326")
    gd = gpd.GeoDataFrame({"id": ["D"]}, geometry=[Point(
        float(d["stop_lon"]), float(d["stop_lat"]))], crs="EPSG:4326")
    h, m = int(c["p0"] // 3600), int((c["p0"] % 3600) // 60)
    try:
        it = r5py.DetailedItineraries(
            rede, origins=go, destinations=gd,
            departure=datetime.datetime(2025, 11, 11, h, max(0, m - 5)),
            departure_time_window=datetime.timedelta(minutes=30),
            transport_modes=MODOS)
    except Exception as e:
        print("%-7s %-6s ERRO %s" % (c["feed"], c["linha"], str(e)[:50]), flush=True)
        continue
    if it is None or len(it) == 0:
        continue
    it = it.copy()
    it["onibus"] = it["transport_mode"].astype(str).str.contains("BUS|RAIL|SUBWAY|TRAM")
    tempos = []
    for opt, bloco in it.groupby("option"):
        bus = bloco[bloco["onibus"]]
        if len(bus) != 1:
            continue
        b = bus.iloc[0]
        if (str(b["route_id"]) == c["rid"]
                and str(b["start_stop_id"]) == c["sid_o"]
                and str(b["end_stop_id"]) == c["sid_d"]):
            tempos.append(MIN(b["travel_time"]))
    trecho = "%s>%s" % (str(o["stop_name"])[:13], str(d["stop_name"])[:13])
    if not tempos:
        print("%-7s %-6s %-28s %6.0f m %10s %8s" % (
            c["feed"], c["linha"], trecho, c["escrit"],
            "nao casou", "-"), flush=True)
        res.append({"feed": c["feed"], "linha": c["linha"], "casou": False})
        continue
    t = pd.Series(tempos)
    dif = t.median() - c["escrit"]
    res.append({"feed": c["feed"], "linha": c["linha"], "casou": True,
                "quadro": c["escrit"], "r5": t.median(), "dif": dif,
                "n_opcoes": len(t), "amplitude": t.max() - t.min()})
    print("%-7s %-6s %-28s %6.0f m %8.1f m %+7.2f   (%d opcoes, amplitude %.1f)"
          % (c["feed"], c["linha"], trecho, c["escrit"], t.median(), dif,
             len(t), t.max() - t.min()), flush=True)

df = pd.DataFrame(res)
u = df[df["casou"]] if len(df) else df
print("", flush=True)
print("=" * 96, flush=True)
print("MESMA LINHA, MESMA PARADA DE EMBARQUE, MESMA PARADA DE DESEMBARQUE:"
      " %d de %d casos" % (len(u), len(df)), flush=True)
if len(u):
    print("  R5 menos quadro:  mediana %+.2f min   min %+.2f   max %+.2f"
          % (u["dif"].median(), u["dif"].min(), u["dif"].max()), flush=True)
    print("  exatos (dif = 0) ....... %d de %d" % ((u["dif"].abs() < 0.01).sum(),
                                                   len(u)), flush=True)
    print("  dentro de +-1 min ...... %d de %d" % ((u["dif"].abs() <= 1).sum(),
                                                   len(u)), flush=True)
    u.to_csv(os.path.expanduser("~/.claude_jobs/validacao_r5py_final.csv"),
             index=False)
print("FIM", flush=True)
