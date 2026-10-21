#!/mnt/nvme_lexar/envs/cuopt/bin/python
# -*- coding: utf-8 -*-
"""cvrp_cuopt_ortools.py - comparacao cuOpt (GPU) x OR-Tools (CPU) em CVRP com instancia identica.

  cvrp_cuopt_ortools.py [--pontos 50,200,1000] [--orcamento 30] [--semente 42] [--capacidade 100]

Mesma matriz de distancias (inteira, euclidiana), mesma frota e mesmo orcamento de tempo para os dois
solvers. Toda solucao passa por validar(), que reconfere demanda, capacidade e cobertura SEM usar
nada interno do solver: so a matriz, as demandas e a sequencia de visitas devolvida.
Resultado em bench/resultados/<data>_cvrp_cuopt_ortools.json.
"""
import argparse, json, math, platform, subprocess, sys, time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "bench" / "resultados"


# ------------------------------------------------------------------ INSTANCIA
def instancia(n_clientes, capacidade, semente, frota_fixa=0):
    """Pontos uniformes em [0,1000]^2, deposito no indice 0. Matriz inteira (mesma para os dois solvers).

    frota_fixa trava a frota nos dois solvers (modo de comparacao justa): um numero, a string
    'kmin' para o minimo teorico da propria instancia (util ao variar a semente, porque o kmin
    muda com a demanda sorteada) ou 0 para a folga heuristica da primeira rodada.
    """
    rng = np.random.default_rng(semente + n_clientes)
    pts = rng.uniform(0, 1000, size=(n_clientes + 1, 2))
    dif = pts[:, None, :] - pts[None, :, :]
    D = np.rint(np.sqrt((dif ** 2).sum(-1))).astype(np.int64)
    np.fill_diagonal(D, 0)
    dem = np.zeros(n_clientes + 1, dtype=np.int64)
    dem[1:] = rng.integers(1, 11, size=n_clientes)          # demanda de 1 a 10
    k_min = math.ceil(dem.sum() / capacidade)
    if frota_fixa == "kmin":
        frota = k_min
    else:
        frota = int(frota_fixa) or k_min + max(2, round(0.2 * k_min))
    return dict(n=n_clientes, pts=pts, D=D, dem=dem, cap=capacidade,
                k_min=k_min, frota=frota, frota_travada=bool(frota_fixa and frota_fixa != "0"),
                semente=semente + n_clientes)


# ------------------------------------------------------------------ VALIDACAO INDEPENDENTE
def validar(rotas, inst, dist_reportada):
    """Reconfere a solucao do zero. rotas = lista de listas de indices de cliente (sem o deposito)."""
    n, D, dem, cap = inst["n"], inst["D"], inst["dem"], inst["cap"]
    visitas = [c for r in rotas for c in r]
    cobertura_ok = sorted(visitas) == list(range(1, n + 1))
    dup = len(visitas) - len(set(visitas))
    faltando = sorted(set(range(1, n + 1)) - set(visitas))

    cargas = [int(sum(dem[c] for c in r)) for r in rotas]
    excedidas = [(i, c) for i, c in enumerate(cargas) if c > cap]

    dist = 0
    for r in rotas:
        if not r:
            continue
        caminho = [0] + list(r) + [0]
        dist += int(sum(D[a][b] for a, b in zip(caminho, caminho[1:])))

    usados = sum(1 for r in rotas if r)
    bate = dist_reportada is None or abs(dist - dist_reportada) <= 1
    return dict(
        valida=bool(cobertura_ok and not excedidas and bate),
        cobertura_ok=bool(cobertura_ok), duplicados=int(dup), faltando=faltando[:10],
        capacidade_ok=not excedidas, rotas_acima_da_capacidade=excedidas[:5],
        demanda_atendida=int(sum(cargas)), demanda_total=int(dem.sum()),
        carga_maxima=max(cargas) if cargas else 0,
        distancia_recalculada=dist, distancia_reportada=dist_reportada,
        distancia_confere=bool(bate), veiculos_usados=usados,
    )


# ------------------------------------------------------------------ OR-TOOLS
def rodar_ortools(inst, orcamento, curva=()):
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    D, dem, cap, K = inst["D"], inst["dem"], inst["cap"], inst["frota"]
    n_loc = inst["n"] + 1

    man = pywrapcp.RoutingIndexManager(n_loc, K, 0)
    mod = pywrapcp.RoutingModel(man)
    cb = mod.RegisterTransitCallback(
        lambda i, j: int(D[man.IndexToNode(i)][man.IndexToNode(j)]))
    mod.SetArcCostEvaluatorOfAllVehicles(cb)
    cbd = mod.RegisterUnaryTransitCallback(lambda i: int(dem[man.IndexToNode(i)]))
    mod.AddDimensionWithVehicleCapacity(cbd, 0, [int(cap)] * K, True, "Capacidade")

    t0 = time.perf_counter()
    historico = []

    def ao_melhorar():
        historico.append((time.perf_counter() - t0, int(mod.CostVar().Max())))

    mod.AddAtSolutionCallback(ao_melhorar)

    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.FromSeconds(orcamento)
    sol = mod.SolveWithParameters(p)
    t_total = time.perf_counter() - t0

    if sol is None:
        return dict(solver="OR-Tools", ok=False, erro="sem solucao", tempo_total_s=round(t_total, 2))

    rotas = []
    for v in range(K):
        idx, r = mod.Start(v), []
        while not mod.IsEnd(idx):
            no = man.IndexToNode(idx)
            if no != 0:
                r.append(no)
            idx = sol.Value(mod.NextVar(idx))
        rotas.append(r)

    melhor = min(h[1] for h in historico) if historico else None
    t_melhor = next((t for t, c in historico if c == melhor), t_total) if historico else None
    # mesmo perfil anytime do cuOpt, mas lido do historico real de incumbentes
    perfil = {}
    for b in sorted(set(list(curva) + [orcamento])):
        ate = [c for t, c in historico if t <= b]
        perfil[b] = min(ate) if ate else None

    return dict(solver="OR-Tools", ok=True, rotas=rotas, custo_reportado=int(sol.ObjectiveValue()),
                tempo_total_s=round(t_total, 2),
                tempo_ate_melhor_s=round(t_melhor, 2) if t_melhor is not None else None,
                metodo_tempo_ate_melhor="callback AddAtSolutionCallback (instante real da ultima melhoria)",
                curva_custo_por_orcamento_s={str(k): v for k, v in sorted(perfil.items())},
                melhorias=len(historico),
                primeira_solucao_s=round(historico[0][0], 2) if historico else None,
                objetivo="distancia total (frota fixa, veiculo vazio custa 0)")


# ------------------------------------------------------------------ cuOPT
def _resolver_cuopt(inst, orcamento, so_distancia=False):
    """Uma resolucao cuOpt. Devolve (custo, rotas, veiculos, t_preparo, t_solve) ou levanta.

    so_distancia=True iguala o objetivo ao do OR-Tools. O cuOpt minimiza numero de veiculos ANTES
    do objetivo (esta no docstring de set_objective_function, nao e um peso que se possa zerar);
    a forma de neutralizar isso e travar a frota: set_min_vehicles(K) com n_fleet=K deixa so K
    viavel, o termo de contagem vira constante e sobra COST. O peso e declarado explicitamente
    (COST=1, VEHICLE_FIXED_COST=0) para nao depender de default.
    """
    import cudf
    from cuopt import routing
    D, dem, cap, K, n = inst["D"], inst["dem"], inst["cap"], inst["frota"], inst["n"]

    t0 = time.perf_counter()
    dm = routing.DataModel(n_locations=n + 1, n_fleet=K, n_orders=n)
    dm.add_cost_matrix(cudf.DataFrame(D.astype(np.float32)))
    dm.set_order_locations(cudf.Series(np.arange(1, n + 1, dtype=np.int32)))
    dm.add_capacity_dimension(
        "demanda",
        cudf.Series(dem[1:].astype(np.int32)),
        cudf.Series(np.full(K, cap, dtype=np.int32)),
    )
    if so_distancia:
        dm.set_min_vehicles(K)
        dm.set_objective_function(
            cudf.Series([routing.Objective.COST, routing.Objective.VEHICLE_FIXED_COST]),
            cudf.Series([1.0, 0.0], dtype=np.float32),
        )
    ss = routing.SolverSettings()
    ss.set_time_limit(orcamento)
    t_prep = time.perf_counter() - t0

    t1 = time.perf_counter()
    sol = routing.Solve(dm, ss)
    t_solve = time.perf_counter() - t1

    if sol.get_status() != 0:
        raise RuntimeError(f"status {sol.get_status()}: {sol.get_error_message()}")

    df = sol.get_route().to_pandas()
    rotas = []
    for _, g in df.groupby("truck_id", sort=True):
        rotas.append([int(l) for l, t in zip(g["location"], g["type"])
                      if str(t).lower() != "depot" and int(l) != 0])
    return (int(round(float(sol.get_total_objective()))), rotas,
            int(sol.get_vehicle_count()), t_prep, t_solve)


def rodar_cuopt(inst, orcamento, curva=(), so_distancia=False):
    """cuOpt 26.10 nao expoe trace de incumbentes pelo Python (dump_best_results grava arquivo
    vazio e set_verbose_mode nao imprime nada neste build), entao o perfil anytime e obtido
    resolvendo de novo com orcamentos menores. 'tempo_ate_melhor_s' e o menor orcamento da
    varredura que ja chega a 1% do melhor custo observado."""
    try:
        custo, rotas, veic, t_prep, t_solve = _resolver_cuopt(inst, orcamento, so_distancia)
    except Exception as e:
        return dict(solver="cuOpt", ok=False, erro=f"{type(e).__name__}: {e}")

    perfil = {}
    for b in sorted(x for x in curva if x < orcamento):
        try:
            perfil[b] = _resolver_cuopt(inst, b, so_distancia)[0]
        except Exception:
            perfil[b] = None
    perfil[orcamento] = custo

    bons = {b: c for b, c in perfil.items() if c is not None}
    melhor = min(bons.values())
    t_melhor = min((b for b, c in bons.items() if c <= melhor * 1.01), default=orcamento)

    return dict(solver="cuOpt", ok=True, rotas=rotas, custo_reportado=custo,
                tempo_total_s=round(t_prep + t_solve, 2),
                tempo_preparo_s=round(t_prep, 2), tempo_solve_s=round(t_solve, 2),
                tempo_ate_melhor_s=t_melhor,
                metodo_tempo_ate_melhor="varredura de orcamentos (sem trace no build 26.10)",
                curva_custo_por_orcamento_s={str(k): v for k, v in sorted(perfil.items())},
                veiculos_reportados=veic,
                objetivo=("distancia total, frota travada em %d por set_min_vehicles" % inst["frota"]
                          if so_distancia else "padrao do cuOpt (minimiza veiculos, depois custo)"),
                nota="solver estocastico: repeticoes com o mesmo orcamento variam alguns decimos de %")


# ------------------------------------------------------------------ MAIN
def principal():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pontos", default="50,200,1000")
    ap.add_argument("--orcamento", type=int, default=30, help="segundos por instancia, por solver")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--capacidade", type=int, default=100)
    ap.add_argument("--curva", default="1,2,5,10,20",
                    help="orcamentos menores para o perfil anytime (vazio desliga)")
    ap.add_argument("--frota-fixa", default="0",
                    help="trava a frota nos dois solvers: numero, 'kmin' (minimo teorico da "
                         "instancia) ou 0 para a folga heuristica")
    ap.add_argument("--cuopt-so-distancia", action="store_true",
                    help="cuOpt otimiza so distancia (exige --frota-fixa para ter efeito pleno)")
    a = ap.parse_args()
    curva = [int(x) for x in a.curva.split(",") if x.strip()]

    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        gpu = "indisponivel"

    saida = dict(gerado_em=time.strftime("%Y-%m-%d %H:%M:%S"),
                 maquina=dict(gpu=gpu, python=platform.python_version()),
                 parametros=dict(capacidade=a.capacidade, demanda="1..10 inteira",
                                 orcamento_s=a.orcamento, semente=a.semente,
                                 curva_orcamentos_s=curva,
                                 frota_fixa=(a.frota_fixa if a.frota_fixa != "0" else None),
                                 cuopt_so_distancia=a.cuopt_so_distancia,
                                 matriz="euclidiana inteira, identica para os dois solvers"),
                 instancias=[])

    for n in [int(x) for x in a.pontos.split(",")]:
        inst = instancia(n, a.capacidade, a.semente, a.frota_fixa)
        print(f"\n=== {n} clientes | demanda total {inst['dem'].sum()} | "
              f"frota {inst['frota']}{' TRAVADA' if inst['frota_travada'] else ''} "
              f"(minimo teorico {inst['k_min']})", flush=True)
        reg = dict(clientes=n, demanda_total=int(inst["dem"].sum()), frota=inst["frota"],
                   frota_travada=inst["frota_travada"],
                   veiculos_minimo_teorico=inst["k_min"], semente_efetiva=inst["semente"],
                   resultados=[])

        for runner in (rodar_ortools, rodar_cuopt):
            nome = "OR-Tools" if runner is rodar_ortools else "cuOpt"
            try:
                r = (rodar_cuopt(inst, a.orcamento, curva, a.cuopt_so_distancia)
                     if runner is rodar_cuopt else rodar_ortools(inst, a.orcamento, curva))
            except Exception as e:
                r = dict(solver=nome, ok=False, erro=f"{type(e).__name__}: {e}")
            if r.get("ok"):
                r["validacao"] = validar(r.pop("rotas"), inst, r.get("custo_reportado"))
                v = r["validacao"]
                print(f"  {nome:9s} dist={v['distancia_recalculada']:>9d} "
                      f"veiculos={v['veiculos_usados']:>3d} "
                      f"t_melhor={r.get('tempo_ate_melhor_s')}s "
                      f"valida={v['valida']}", flush=True)
            else:
                print(f"  {nome:9s} FALHOU: {r.get('erro')}", flush=True)
            reg["resultados"].append(r)
        saida["instancias"].append(reg)

    RES.mkdir(parents=True, exist_ok=True)
    sufixo = "_justo" if (a.frota_fixa != "0" and a.cuopt_so_distancia) else ""
    arq = RES / f"{time.strftime('%Y%m%d_%H%M')}_cvrp_cuopt_ortools{sufixo}.json"
    arq.write_text(json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {arq}")
    return saida


if __name__ == "__main__":
    principal()
