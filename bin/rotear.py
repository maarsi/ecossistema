#!/usr/bin/env python3
"""rotear.py - Roteamento de frota: matriz real (OSRM local) + cuOpt (GPU).

Uso:  ~/env_cuopt/bin/python ~/ecossistema/bin/rotear.py pontos.csv [opcoes]
CSV:  nome,lat,lon,demanda,janela_inicio_min,janela_fim_min   (1a linha = base)
Requisitos: OSRM em localhost:5000 (container 'osrm'), env_cuopt.
"""
import argparse, csv, json, sys, urllib.request
import cudf
from cuopt import routing

def osrm_table(coords):
    url = f"http://localhost:5000/table/v1/driving/{coords}?annotations=duration"
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)["durations"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--carros", type=int, default=2)
    ap.add_argument("--capacidade", type=int, default=8)
    ap.add_argument("--servico", type=int, default=15, help="min por ponto")
    ap.add_argument("--inicio", type=int, default=450, help="saida da base (min)")
    ap.add_argument("--fim", type=int, default=780, help="retorno maximo (min)")
    ap.add_argument("--saida", default="", help="CSV de saida das rotas")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
    pts = [(r["nome"], float(r["lat"]), float(r["lon"]), int(r["demanda"]),
            int(r["janela_inicio_min"]), int(r["janela_fim_min"])) for r in rows]

    coords = ";".join(f"{p[2]},{p[1]}" for p in pts)
    dur = osrm_table(coords)
    matriz = [[int(round(v/60)) if v is not None else 9999 for v in linha] for linha in dur]

    n = len(pts); ordens = list(range(1, n))
    dm = routing.DataModel(n_locations=n, n_fleet=a.carros, n_orders=len(ordens))
    m = cudf.DataFrame(matriz, dtype="float32")
    dm.add_cost_matrix(m); dm.add_transit_time_matrix(m)
    dm.set_order_locations(cudf.Series(ordens, dtype="int32"))
    dm.add_capacity_dimension("demanda",
        cudf.Series([pts[i][3] for i in ordens], dtype="int32"),
        cudf.Series([a.capacidade]*a.carros, dtype="int32"))
    dm.set_order_time_windows(
        cudf.Series([pts[i][4] for i in ordens], dtype="int32"),
        cudf.Series([pts[i][5] for i in ordens], dtype="int32"))
    dm.set_order_service_times(cudf.Series([a.servico]*len(ordens), dtype="int32"))
    dm.set_vehicle_time_windows(
        cudf.Series([a.inicio]*a.carros, dtype="int32"),
        cudf.Series([a.fim]*a.carros, dtype="int32"))

    sol = routing.Solve(dm, routing.SolverSettings())
    if sol.get_status() != 0:
        print("FALHA no solve, status", sol.get_status()); sys.exit(1)

    df = sol.get_route().to_pandas()
    df["nome"] = df["location"].map(lambda i: pts[int(i)][0])
    df["horario"] = df["arrival_stamp"].map(lambda mm: f"{int(mm)//60:02d}h{int(mm)%60:02d}")
    print(df[["truck_id", "nome", "type", "horario"]].to_string(index=False))
    if a.saida:
        df.to_csv(a.saida, index=False); print("\nsalvo em", a.saida)

if __name__ == "__main__":
    main()
