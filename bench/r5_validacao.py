#!/usr/bin/env python3
"""
r5_salvador.py - valida o r5py com GTFS real de um sistema urbano e recorte OSM local.

O QUE MEDE. Matriz 8x8 de tempo de viagem por transporte publico entre os polos da RMS,
porta a porta, com caminhada de acesso e egresso.

DEFINICAO DECLARADA, porque sem ela o numero nao significa nada:
  - A oferta e a de BRT + PLATAFORMA em 11/11/2025. Um dos operadores esta AUSENTE por defeito
    de vigencia do feed entregue (ver nota abaixo), entao isto NAO e a oferta total.
  - A oferta e a VIGENTE EM NOVEMBRO DE 2025. Os dois GTFS estao vencidos (BRT ate
    22/01/2026, OPB ate 19/02/2026), entao a data de partida tem de cair dentro da
    vigencia comum. Nao e acessibilidade de hoje.
  - Terça-feira 11/11/2025, partida entre 07:00 e 08:00, percentil 50.
  - Tempo porta a porta: caminhada ate a parada, espera, viagem, transbordo, caminhada final.
  - SO ONIBUS E CORREDOR. Conferido em routes.txt: as 510 linhas dos tres feeds sao
    route_type 3. NAO ha metro, travessia nem ascensor no pacote, embora cinco dos oito
    polos SEJAM estacoes de metro. Logo isto e tempo POR ONIBUS, nao tempo por transporte
    publico, e chamar de transporte publico seria erro de definicao, nao de arredondamento.

VERIFICACAO INDEPENDENTE, e por que nao e contra o Google. O Google pode estar usando o
MESMO GTFS do gestor; comparar com ele mediria reimplementacao, nao correcao. O controle
usado e interno e mais forte: a rede e construida DUAS vezes, so com o BRT e com BRT mais
OPB. ACRESCENTAR OFERTA NAO PODE AUMENTAR TEMPO DE VIAGEM em nenhum par. Se aumentar, ha
defeito, e isso nao depende de fonte externa nenhuma.
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")

RAIZ = pathlib.Path.home() / "ecossistema"
TRAB = pathlib.Path.home() / "r5_salvador"
PBF_ORIG = pathlib.Path.home() / "osrm" / "nordeste-latest.osm.pbf"
PBF_REC = TRAB / "salvador.osm.pbf"
# OS FEEDS ENTREGUES PELO GESTOR PRECISARAM SER REEMPACOTADOS, e o motivo importa:
# O pacote do sistema NAO e um feed valido. E um pacote com DOIS feeds de operador em
# subpastas (dois consorcios operadores). A especificacao exige
# os arquivos na raiz do zip, e o R5 recusa. O gtfs_kit, mais permissivo, leu o arquivo sem
# reclamar e devolveu os numeros de apenas UM dos dois, mascarando o problema.
#
# DEFEITO DE VIGENCIA NO DADO ENTREGUE, confirmado no calendar.txt e nao inferido:
#   operador A  229 servicos, TODOS de 20251014 a 20251015, nenhum em fim de semana
#   operador B  576 servicos, 20251019 a 20260219, com fim de semana
#   corredor      6 servicos, 20251022 a 20260122, com fim de semana
# NAO EXISTE DATA EM QUE OS TRES TENHAM SERVICO. Analise datada em novembro perde as 237
# linhas e 2509 paradas do operador A, e o resultado sai plausivel, que e o pior caso.
# Por isso o experimento roda com corredor + operador B e DECLARA a ausencia do A.
GTFS_DIR = pathlib.Path.home() / "r5_salvador" / "gtfs"
BRT = GTFS_DIR / "brt.zip"
OPB = GTFS_DIR / "operador_b.zip"
BBOX = "-38.59,-13.07,-38.25,-12.76"
PARTIDA = dt.datetime(2025, 11, 11, 7, 0)   # terca dentro da vigencia dos dois feeds
JANELA = dt.timedelta(hours=1)

POLOS = {
    "LAPA":         (-12.982789, -38.512129),
    "PIRAJA":       (-12.924230, -38.467533),
    "ACESSO NORTE": (-12.968857, -38.477203),
    "MUSSURUNGA":   (-12.921483, -38.359063),
    "AEROPORTO":    (-12.904211, -38.341187),
    "IGUATEMI":     (-12.979461, -38.463487),
    "BARRA":        (-13.008207, -38.526692),
    "CALCADA":      (-12.945981, -38.500265),
}


def diz(*a):
    print(*a, flush=True)


def recortar():
    TRAB.mkdir(exist_ok=True)
    if PBF_REC.exists():
        diz(f"[1] recorte ja existe: {PBF_REC.stat().st_size/1e6:.1f} MB")
        return
    diz(f"[1] recortando {PBF_ORIG.name} ({PBF_ORIG.stat().st_size/1e6:.0f} MB) para {BBOX}")
    r = subprocess.run(["osmium", "extract", "-b", BBOX, "--overwrite",
                        "-o", str(PBF_REC), str(PBF_ORIG)],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode:
        diz("    FALHOU:", r.stderr.strip()[:300]); sys.exit(1)
    diz(f"    recorte: {PBF_REC.stat().st_size/1e6:.1f} MB")


def matriz(feeds, rotulo):
    import geopandas as gpd
    from shapely.geometry import Point
    # API do r5py 1.1.7, conferida por introspeccao e nao por memoria: a classe e
    # TravelTimeMatrix, construida direto, e os modos vem todos de TransportMode.
    from r5py import TransportNetwork, TravelTimeMatrix, TransportMode

    diz(f"[2] construindo rede R5 ({rotulo}): {len(feeds)} feed(s)")
    t0 = dt.datetime.now()
    rede = TransportNetwork(str(PBF_REC), [str(f) for f in feeds])
    diz(f"    rede pronta em {(dt.datetime.now()-t0).total_seconds():.0f} s")

    pontos = gpd.GeoDataFrame(
        {"id": list(POLOS)},
        geometry=[Point(lon, lat) for lat, lon in POLOS.values()],
        crs="EPSG:4326")

    t0 = dt.datetime.now()
    # snap_to_network: polo cuja coordenada nao cai sobre a rede devolveria vazio sem isso
    df = TravelTimeMatrix(
        rede, origins=pontos, destinations=pontos, snap_to_network=True,
        departure=PARTIDA, departure_time_window=JANELA,
        percentiles=[50],
        transport_modes=[TransportMode.TRANSIT, TransportMode.WALK],
        max_time=dt.timedelta(hours=3))
    diz(f"    matriz calculada em {(dt.datetime.now()-t0).total_seconds():.0f} s")
    diz(f"    colunas devolvidas: {list(df.columns)}")
    col = next(c for c in df.columns if "travel_time" in c)
    m = df.pivot(index="from_id", columns="to_id", values=col)
    m = m.reindex(index=list(POLOS), columns=list(POLOS))
    return m


def main():
    recortar()
    m_brt = matriz([BRT], "so BRT")
    m_tudo = matriz([BRT, OPB], "BRT + operador B")

    diz("")
    diz("=" * 74)
    diz("MATRIZ DE TEMPO POR TRANSPORTE PUBLICO, minutos, percentil 50")
    diz("oferta de 11/11/2025, partida 07:00-08:00, porta a porta")
    diz("=" * 74)
    cab = "origem \\ destino".ljust(14) + "".join(f"{c[:8]:>9s}" for c in POLOS)
    diz(cab)
    for o in POLOS:
        linha = o[:13].ljust(14)
        for d in POLOS:
            v = m_tudo.loc[o, d]
            linha += ("        -" if v != v else f"{v:9.0f}")
        diz(linha)

    diz("")
    diz("ASSERCOES")
    falhas = []
    # 1. diagonal zero
    diag = [m_tudo.loc[o, o] for o in POLOS]
    ok = all((v == 0 or v != v) for v in diag)
    diz(f"  [{'OK ' if ok else 'FALHA'}] diagonal nula ou ausente: {diag}")
    falhas += [] if ok else ["diagonal"]

    # 2. MONOTONICIDADE: mais oferta nao pode piorar
    piores = []
    for o in POLOS:
        for d in POLOS:
            a, b = m_brt.loc[o, d], m_tudo.loc[o, d]
            if a == a and b == b and b > a + 1:      # tolerancia de 1 min
                piores.append((o, d, a, b))
    ok = not piores
    diz(f"  [{'OK ' if ok else 'FALHA'}] acrescentar o OPB nao aumentou tempo em nenhum par "
        f"({len(piores)} violacao(oes))")
    for o, d, a, b in piores[:5]:
        diz(f"        {o} -> {d}: so BRT {a:.0f} min, com operador B {b:.0f} min")
    falhas += [] if ok else ["monotonicidade"]

    # 3. cobertura: com mais oferta, mais pares alcancaveis
    n_brt = int((m_brt == m_brt).sum().sum())
    n_tudo = int((m_tudo == m_tudo).sum().sum())
    ok = n_tudo >= n_brt
    diz(f"  [{'OK ' if ok else 'FALHA'}] pares alcancaveis: so BRT {n_brt}/64, "
        f"com operador B {n_tudo}/64")
    falhas += [] if ok else ["cobertura"]

    # 4. plausibilidade de velocidade aparente
    from math import radians, sin, cos, asin, sqrt
    def hav(a, b):
        la1, lo1 = map(radians, a); la2, lo2 = map(radians, b)
        return 2*6371*asin(sqrt(sin((la2-la1)/2)**2 +
                                cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2))
    vel = []
    for o in POLOS:
        for d in POLOS:
            if o == d: continue
            v = m_tudo.loc[o, d]
            if v != v or v <= 0: continue
            km = hav(POLOS[o], POLOS[d])
            vel.append((o, d, km/(v/60)))
    fora = [x for x in vel if not (2 <= x[2] <= 60)]
    ok = not fora
    diz(f"  [{'OK ' if ok else 'FALHA'}] velocidade aparente em linha reta entre 2 e 60 km/h "
        f"({len(fora)} fora de {len(vel)})")
    for o, d, s in fora[:5]:
        diz(f"        {o} -> {d}: {s:.1f} km/h")
    falhas += [] if ok else ["velocidade"]

    saida = TRAB / f"matriz_{dt.datetime.now():%Y%m%d_%H%M}.json"
    saida.write_text(json.dumps({
        "definicao": "oferta de 11/11/2025, 07:00-08:00, percentil 50, porta a porta",
        "feeds": [BRT.name, OPB.name],
        "assercoes_falhas": falhas,
        "matriz_min": {o: {d: (None if m_tudo.loc[o, d] != m_tudo.loc[o, d]
                               else float(m_tudo.loc[o, d])) for d in POLOS} for o in POLOS},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    diz("")
    diz(f"RESULTADO: {'TODAS AS ASSERCOES PASSARAM' if not falhas else 'FALHAS: ' + ', '.join(falhas)}")
    diz(f"saida: {saida}")
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
