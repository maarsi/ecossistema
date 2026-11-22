#!/mnt/nvme_lexar/envs/cuopt/bin/python
# -*- coding: utf-8 -*-
"""vrptw_cuopt_ortools.py - cuOpt (GPU) x OR-Tools (CPU) no VRPTW de Solomon (56 instancias de 100 clientes).

Autorizado por Mateus em 22/11/2026 (bloco II, proposta a). Pre-registro: bench/vrptw/PRE_REGISTRO.md.

  vrptw_cuopt_ortools.py [--instancias c101,r101] [--orcamento 30] [--rep-cuopt 3] [--saida arq.json]

CONDICOES IGUALADAS NAS DUAS PONTAS
- Mesma matriz. Distancia euclidiana em dupla precisao, escalada por 1000: CUSTO arredondado, TEMPO de
  deslocamento ARREDONDADO PARA CIMA (ceil), para que viavel no inteiro implique viavel no real.
- Mesmo objetivo, o da literatura de Solomon: primeiro numero de veiculos, depois distancia. O cuOpt ja
  minimiza veiculos antes do custo (docstring de set_objective_function); no OR-Tools isso se faz com custo
  fixo por veiculo maior que qualquer distancia possivel (FIXO = 10^7).
  O MESMO custo fixo e declarado no cuOpt (set_vehicle_fixed_costs, pesos COST=1 e VEHICLE_FIXED_COST=1
  explicitos): o objetivo fica escrito igual nas duas pontas, em vez de depender do comportamento interno.
- Mesma frota disponivel (K da instancia), mesma capacidade, janelas, tempo de servico e janela do deposito.
- Mesmo orcamento de parede por resolucao.
VALIDACAO INDEPENDENTE: validar() recalcula tudo a partir das COORDENADAS em dupla precisao (nao da matriz
escalada): cobertura, duplicidade, capacidade, chegada <= fim da janela (espera permitida), retorno ao
deposito dentro da janela, e distancia total. A distancia reportada e a do validador.
"""
import argparse, json, math, time, sys, platform, subprocess
from pathlib import Path
import numpy as np

AQUI = Path(__file__).resolve().parent
ESC, FIXO, TOL = 1000, 10**7, 1e-6   # FIXO > qualquer distancia total escalada (max ~3,5e6)

def ler_solomon(p):
    L = Path(p).read_text().splitlines()
    i = next(k for k, l in enumerate(L) if l.strip().startswith("NUMBER"))
    K, Q = map(int, L[i + 1].split())
    rows = [list(map(float, l.split())) for l in L[i + 2:] if len(l.split()) == 7 and l.split()[0].isdigit()]
    a = np.array(rows)
    assert (a[:, 0] == np.arange(len(a))).all(), "numeracao de clientes fora de ordem"
    x, y = a[:, 1], a[:, 2]
    D = np.sqrt((x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2)
    return dict(nome=L[0].strip(), K=K, Q=Q, x=x, y=y, D=D, dem=a[:, 3].astype(int),
                ini=a[:, 4], fim=a[:, 5], serv=a[:, 6],
                Dc=np.rint(D * ESC).astype(np.int64), Tt=np.ceil(D * ESC - 1e-9).astype(np.int64),
                inii=np.rint(a[:, 4] * ESC).astype(np.int64), fimi=np.rint(a[:, 5] * ESC).astype(np.int64),
                servi=np.rint(a[:, 6] * ESC).astype(np.int64))

def validar(rotas, I):
    n = len(I["x"]); vistos = []; dist = 0.0; erros = []
    for r in rotas:
        if not r: continue
        carga = sum(I["dem"][c] for c in r)
        if carga > I["Q"]: erros.append(f"capacidade {carga}>{I['Q']}")
        t, ant = I["ini"][0], 0
        for c in r:
            t = max(t + I["serv"][ant] + I["D"][ant, c], I["ini"][c])
            if t > I["fim"][c] + TOL: erros.append(f"janela cliente {c}: {t:.3f}>{I['fim'][c]}")
            dist += I["D"][ant, c]; ant = c
        t += I["serv"][ant] + I["D"][ant, 0]; dist += I["D"][ant, 0]
        if t > I["fim"][0] + TOL: erros.append(f"retorno ao deposito {t:.3f}>{I['fim'][0]}")
        vistos += r
    if sorted(vistos) != list(range(1, n)):
        erros.append(f"cobertura: {len(set(vistos))} de {n-1}, duplicados {len(vistos)-len(set(vistos))}")
    return dict(ok=not erros, veiculos=sum(1 for r in rotas if r), distancia=round(dist, 2), erros=erros[:5])

def rodar_ortools(I, orc, primeira="PATH_CHEAPEST_ARC"):
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    n, K = len(I["x"]), I["K"]
    Dc, Tt, sv, dem = I["Dc"].tolist(), I["Tt"].tolist(), I["servi"].tolist(), I["dem"].tolist()
    m = pywrapcp.RoutingIndexManager(n, K, 0); r = pywrapcp.RoutingModel(m)
    cb = r.RegisterTransitCallback(lambda i, j: Dc[m.IndexToNode(i)][m.IndexToNode(j)])
    r.SetArcCostEvaluatorOfAllVehicles(cb); r.SetFixedCostOfAllVehicles(FIXO)
    dcb = r.RegisterUnaryTransitCallback(lambda i: dem[m.IndexToNode(i)])
    r.AddDimensionWithVehicleCapacity(dcb, 0, [I["Q"]] * K, True, "Cap")
    tcb = r.RegisterTransitCallback(lambda i, j: sv[m.IndexToNode(i)] + Tt[m.IndexToNode(i)][m.IndexToNode(j)])
    H = int(I["fimi"][0]); r.AddDimension(tcb, H, H, False, "Tempo"); td = r.GetDimensionOrDie("Tempo")
    for no in range(1, n): td.CumulVar(m.NodeToIndex(no)).SetRange(int(I["inii"][no]), int(I["fimi"][no]))
    for v in range(K):
        for idx in (r.Start(v), r.End(v)): td.CumulVar(idx).SetRange(int(I["inii"][0]), H)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = getattr(routing_enums_pb2.FirstSolutionStrategy, primeira)
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.FromSeconds(int(orc))
    t = time.perf_counter(); s = r.SolveWithParameters(p); dt = time.perf_counter() - t
    if not s: return dict(status="sem_solucao", t=dt)
    rotas = []
    for v in range(K):
        i, rt = r.Start(v), []
        while not r.IsEnd(i):
            no = m.IndexToNode(i)
            if no: rt.append(no)
            i = s.Value(r.NextVar(i))
        rotas.append(rt)
    return dict(status="ok", t=dt, rotas=rotas)

def rodar_cuopt(I, orc):
    import cudf
    from cuopt import routing
    n, K = len(I["x"]), I["K"]
    t0 = time.perf_counter()
    dm = routing.DataModel(n_locations=n, n_fleet=K, n_orders=n - 1)
    dm.add_cost_matrix(cudf.DataFrame(I["Dc"].astype(np.float32)))
    dm.add_transit_time_matrix(cudf.DataFrame(I["Tt"].astype(np.float32)))
    dm.set_order_locations(cudf.Series(np.arange(1, n, dtype=np.int32)))
    dm.add_capacity_dimension("demanda", cudf.Series(I["dem"][1:].astype(np.int32)),
                              cudf.Series(np.full(K, I["Q"], dtype=np.int32)))
    dm.set_order_time_windows(cudf.Series(I["inii"][1:].astype(np.int32)), cudf.Series(I["fimi"][1:].astype(np.int32)))
    dm.set_order_service_times(cudf.Series(I["servi"][1:].astype(np.int32)))
    dm.set_vehicle_time_windows(cudf.Series(np.full(K, I["inii"][0], dtype=np.int32)),
                                cudf.Series(np.full(K, I["fimi"][0], dtype=np.int32)))
    dm.set_vehicle_fixed_costs(cudf.Series(np.full(K, FIXO, dtype=np.float32)))
    dm.set_objective_function(cudf.Series([routing.Objective.COST, routing.Objective.VEHICLE_FIXED_COST]),
                              cudf.Series([1.0, 1.0], dtype=np.float32))
    ss = routing.SolverSettings(); ss.set_time_limit(orc)
    t = time.perf_counter(); sol = routing.Solve(dm, ss); dt = time.perf_counter() - t
    if sol.get_status() != 0:
        return dict(status=f"status {sol.get_status()}: {sol.get_error_message()}", t=dt)
    df = sol.get_route().to_pandas(); rotas = []
    for _, g in df.groupby("truck_id", sort=True):
        rotas.append([int(l) for l, ty in zip(g["location"], g["type"]) if str(ty).lower() != "depot" and int(l) != 0])
    return dict(status="ok", t=dt, t_preparo=t - t0, rotas=rotas)

def bks(nome):
    p = AQUI / "bks_sintef" / f"{nome.lower()}.txt"
    if not p.exists(): return None
    rotas = [list(map(int, l.split(":", 1)[1].split())) for l in p.read_text().splitlines() if l.startswith("Route")]
    return rotas

def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instancias", default=""); ap.add_argument("--orcamento", type=int, default=30)
    ap.add_argument("--rep-cuopt", type=int, default=3); ap.add_argument("--saida", default="")
    ap.add_argument("--primeira", default="PATH_CHEAPEST_ARC", help="estrategia de 1a solucao do OR-Tools")
    a = ap.parse_args()
    arqs = sorted((AQUI / "solomon").glob("*.txt"))
    if a.instancias: arqs = [p for p in arqs if p.stem.lower() in a.instancias.lower().split(",")]
    saida = Path(a.saida or AQUI.parent / "resultados" / f"{time.strftime('%Y%m%d')}_vrptw_cuopt_ortools.jsonl")
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    print(f"# {len(arqs)} instancias, orcamento {a.orcamento} s, cuOpt x{a.rep_cuopt}, GPU no inicio: {gpu}", flush=True)
    feitos = set()
    if saida.exists():
        feitos = {json.loads(l)["instancia"] for l in saida.read_text().splitlines() if l.strip()}
    for p in arqs:
        I = ler_solomon(p)
        if I["nome"] in feitos: continue
        lin = dict(instancia=I["nome"], K=I["K"], Q=I["Q"], orcamento=a.orcamento, gpu_inicio=gpu)
        b = bks(I["nome"]); lin["bks"] = validar(b, I) if b else None
        o = rodar_ortools(I, a.orcamento, a.primeira); lin["ortools_primeira"] = a.primeira
        lin["ortools"] = {**{k: v for k, v in o.items() if k != "rotas"}, **(validar(o["rotas"], I) if o.get("rotas") else {})}
        lin["cuopt"] = []
        for _ in range(a.rep_cuopt):
            c = rodar_cuopt(I, a.orcamento)
            lin["cuopt"].append({**{k: v for k, v in c.items() if k != "rotas"}, **(validar(c["rotas"], I) if c.get("rotas") else {})})
        with open(saida, "a") as f: f.write(json.dumps(lin, ensure_ascii=False) + "\n")
        cu = " ".join(f"{x.get('veiculos','-')}/{x.get('distancia','-')}{'' if x.get('ok') else '!'}" for x in lin["cuopt"])
        bk = f"{lin['bks']['veiculos']}/{lin['bks']['distancia']}" if lin["bks"] else "-"
        print(f"{I['nome']:6s} BKS {bk:14s} OR {lin['ortools'].get('veiculos','-')}/{lin['ortools'].get('distancia','-')}"
              f"{'' if lin['ortools'].get('ok') else '!'}  cuOpt {cu}", flush=True)
    print("FIM", flush=True)

if __name__ == "__main__":
    principal()
