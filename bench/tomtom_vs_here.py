#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tomtom_vs_here.py - comparacao medida entre TomTom e HERE para rede viaria.

Regra do ecossistema: ferramenta so entra por medicao. Este script compara as
duas fontes nas mesmas instancias, no mesmo instante, e grava o resultado em
JSON para registro.

Duas frentes:

  A. IMPEDANCIA. Para cada par dos polos de Salvador ja catalogados no
     tomtom_network_server.py, compara distancia, tempo em fluxo livre e tempo
     com transito. O TomTom devolve os dois tempos em uma chamada
     (travelTimeInSeconds e noTrafficTravelTimeInSeconds); a HERE resolve a
     matriz inteira em duas chamadas (com e sem transito). As duas coletas
     ocorrem na mesma janela de minutos, senao o tempo com transito nao e
     comparavel.

  B. GEOCODIFICACAO. Para cada polo, compara a coordenada catalogada com o que
     cada geocodificador devolve para o mesmo nome, em metros. Serve para achar
     coordenada de catalogo desatualizada, que contamina qualquer matriz
     construida a partir dela.

Chaves: TOMTOM_API_KEY e HERE_API_KEY no ambiente. Nada e impresso delas.
Uso: tomtom_vs_here.py <arquivo_de_saida.json> [--polos N]
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOMTOM = os.environ.get("TOMTOM_API_KEY", "")
HERE = os.environ.get("HERE_API_KEY", "")

# Catalogo do tomtom_network_server.py, tratado aqui como DADO A CONFERIR,
# nao como verdade: a frente B existe justamente para isso.
POLOS = {
    "Terminal da Lapa, Salvador, BA": (-12.9814, -38.5108),
    "Estacao Piraja, Salvador, BA": (-12.9152, -38.4552),
    "Estacao Acesso Norte, Salvador, BA": (-12.9687, -38.4877),
    "Estacao Mussurunga, Salvador, BA": (-12.9288, -38.3845),
    "Estacao Aeroporto, Salvador, BA": (-12.9069, -38.3346),
    "Shopping Iguatemi, Salvador, BA": (-12.9782, -38.4623),
    "Barra, Salvador, BA": (-13.0094, -38.5312),
    "Estacao Calcada, Salvador, BA": (-12.9467, -38.5028),
}


def _get(url, params, timeout=30):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=timeout) as r:
        return json.load(r)


def _post(url, params, corpo, timeout=120):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def haversine_m(a, b):
    """Distancia em linha reta, em metros, para comparar coordenadas."""
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ----------------------------------------------------------------- frente A
def tomtom_par(o, d):
    """Uma chamada: devolve distancia, tempo com transito e tempo em fluxo livre."""
    url = ("https://api.tomtom.com/routing/1/calculateRoute/"
           f"{o[0]},{o[1]}:{d[0]},{d[1]}/json")
    # computeTravelTimeFor=all e obrigatorio para vir noTrafficTravelTimeInSeconds.
    # Sem ele a API omite o campo, e usar travelTimeInSeconds como reserva
    # produz t0 contaminado com transito e atraso identicamente zero. Verificado
    # em 21/10/2026: mesmo par, 1.305 s com transito e 1.133 s em fluxo livre.
    dados = _get(url, {"key": TOMTOM, "traffic": "true", "travelMode": "car",
                       "routeType": "fastest", "computeTravelTimeFor": "all"})
    s = dados["routes"][0]["summary"]
    t0 = s.get("noTrafficTravelTimeInSeconds")
    return {
        "dist_m": s["lengthInMeters"],
        "t_transito_s": s["travelTimeInSeconds"],
        "t_livre_s": t0,                                  # None se a API omitir
        "t_livre_ausente": t0 is None,
        "trafficDelayInSeconds": s.get("trafficDelayInSeconds"),
    }


def here_matriz(pontos, com_transito):
    corpo = {
        "origins": [{"lat": p[0], "lng": p[1]} for p in pontos],
        "destinations": [{"lat": p[0], "lng": p[1]} for p in pontos],
        "regionDefinition": {"type": "world"},
        "matrixAttributes": ["travelTimes", "distances"],
    }
    if not com_transito:
        corpo["departureTime"] = "any"
    d = _post("https://matrix.router.hereapi.com/v8/matrix",
              {"async": "false", "apiKey": HERE}, corpo)
    return d["matrix"]


# ----------------------------------------------------------------- frente B
def here_geocode(nome):
    d = _get("https://geocode.search.hereapi.com/v1/geocode",
             {"q": nome, "limit": 1, "lang": "pt-BR", "apiKey": HERE})
    it = (d.get("items") or [None])[0]
    if not it:
        return None
    p = it["position"]
    return {"lat": p["lat"], "lon": p["lng"], "titulo": it.get("title"),
            "tipo": it.get("resultType"),
            "escore": (it.get("scoring") or {}).get("queryScore")}


def tomtom_geocode(nome):
    url = "https://api.tomtom.com/search/2/geocode/" + urllib.parse.quote(nome) + ".json"
    d = _get(url, {"key": TOMTOM, "limit": 1, "countrySet": "BR"})
    r = (d.get("results") or [None])[0]
    if not r:
        return None
    p = r["position"]
    return {"lat": p["lat"], "lon": p["lon"],
            "titulo": (r.get("poi") or {}).get("name") or (r.get("address") or {}).get("freeformAddress"),
            "tipo": r.get("type"), "escore": r.get("score")}


def resumo(valores):
    """Estatistica minima de um conjunto de divergencias relativas, em %."""
    if not valores:
        return None
    v = sorted(valores)
    n = len(v)
    return {"n": n, "media_pct": round(sum(v) / n, 2),
            "mediana_pct": round(v[n // 2], 2),
            "p90_pct": round(v[int(0.9 * (n - 1))], 2),
            "maximo_pct": round(v[-1], 2)}


def principal():
    if not TOMTOM or not HERE:
        print("Erro: TOMTOM_API_KEY e HERE_API_KEY precisam estar no ambiente.")
        return 1
    saida = sys.argv[1] if len(sys.argv) > 1 else "tomtom_vs_here.json"
    limite = 8
    if "--polos" in sys.argv:
        limite = int(sys.argv[sys.argv.index("--polos") + 1])

    nomes = list(POLOS)[:limite]
    pontos = [POLOS[n] for n in nomes]
    t_inicio = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- A: HERE em duas chamadas, TomTom par a par
    m_livre = here_matriz(pontos, com_transito=False)
    m_transito = here_matriz(pontos, com_transito=True)
    nd = len(pontos)

    pares, falhas = [], []
    for i in range(nd):
        for j in range(nd):
            if i >= j:                      # um sentido por par, sem diagonal
                continue
            k = i * nd + j
            try:
                tt = tomtom_par(pontos[i], pontos[j])
            except Exception as e:
                falhas.append({"par": [nomes[i], nomes[j]], "erro": f"{type(e).__name__}: {e}"})
                continue
            h = {"dist_m": m_livre["distances"][k],
                 "t_livre_s": m_livre["travelTimes"][k],
                 "t_transito_s": m_transito["travelTimes"][k],
                 "dist_transito_m": m_transito["distances"][k]}

            def div(a, b):
                return round((a - b) / b * 100.0, 2) if b else None

            pares.append({
                "origem": nomes[i], "destino": nomes[j],
                "tomtom": tt, "here": h,
                "div_dist_pct": div(h["dist_m"], tt["dist_m"]),
                "div_t_livre_pct": div(h["t_livre_s"], tt["t_livre_s"]),
                "div_t_transito_pct": div(h["t_transito_s"], tt["t_transito_s"]),
                "atraso_tomtom_pct": div(tt["t_transito_s"], tt["t_livre_s"]),
                "atraso_here_pct": div(h["t_transito_s"], h["t_livre_s"]),
            })
            time.sleep(0.2)                 # folga para o limite de requisicoes

    # --- B: geocodificacao contra o catalogo
    geo = []
    for n in nomes:
        cat = POLOS[n]
        linha = {"polo": n, "catalogo": {"lat": cat[0], "lon": cat[1]}}
        for rotulo, fn in (("here", here_geocode), ("tomtom", tomtom_geocode)):
            try:
                r = fn(n)
                if r:
                    r["desvio_do_catalogo_m"] = round(haversine_m(cat, (r["lat"], r["lon"])), 1)
                linha[rotulo] = r
            except Exception as e:
                linha[rotulo] = {"erro": f"{type(e).__name__}: {e}"}
        if isinstance(linha.get("here"), dict) and isinstance(linha.get("tomtom"), dict) \
                and "lat" in linha["here"] and "lat" in linha["tomtom"]:
            linha["distancia_entre_geocodificadores_m"] = round(
                haversine_m((linha["here"]["lat"], linha["here"]["lon"]),
                            (linha["tomtom"]["lat"], linha["tomtom"]["lon"])), 1)
        geo.append(linha)
        time.sleep(0.2)

    res = {
        "titulo": "TomTom x HERE: impedancia e geocodificacao, polos de Salvador",
        "inicio": t_inicio, "fim": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "observacao_transito": ("os tempos com transito das duas fontes foram coletados na mesma "
                                "janela de minutos; fora dela nao sao comparaveis"),
        "convencao_here": ("omitir departureTime devolve tempo COM transito; departureTime=any "
                           "devolve fluxo livre (verificado em 21/10/2026)"),
        "polos": nomes,
        "frente_a_impedancia": {
            "pares": pares,
            "falhas": falhas,
            "pares_sem_t0_no_tomtom": sum(1 for p in pares if p["tomtom"].get("t_livre_ausente")),
            "divergencia_relativa_here_sobre_tomtom": {
                "distancia": resumo([abs(p["div_dist_pct"]) for p in pares if p["div_dist_pct"] is not None]),
                "tempo_fluxo_livre": resumo([abs(p["div_t_livre_pct"]) for p in pares if p["div_t_livre_pct"] is not None]),
                "tempo_com_transito": resumo([abs(p["div_t_transito_pct"]) for p in pares if p["div_t_transito_pct"] is not None]),
            },
            "atraso_medio_declarado_pct": {
                "tomtom": resumo([p["atraso_tomtom_pct"] for p in pares if p["atraso_tomtom_pct"] is not None]),
                "here": resumo([p["atraso_here_pct"] for p in pares if p["atraso_here_pct"] is not None]),
            },
        },
        "frente_b_geocodificacao": geo,
    }
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)

    # ---- relatorio curto na tela
    d = res["frente_a_impedancia"]
    print("=== A. IMPEDANCIA (%d pares, %d falhas) ===" % (len(pares), len(falhas)))
    for chave, rot in (("distancia", "distância"), ("tempo_fluxo_livre", "tempo fluxo livre"),
                       ("tempo_com_transito", "tempo com trânsito")):
        r = d["divergencia_relativa_here_sobre_tomtom"][chave]
        if r:
            print("  %-20s mediana %5.1f%%  p90 %5.1f%%  máximo %5.1f%%"
                  % (rot, r["mediana_pct"], r["p90_pct"], r["maximo_pct"]))
    for fonte in ("tomtom", "here"):
        r = d["atraso_medio_declarado_pct"][fonte]
        if r:
            print("  atraso declarado %-6s mediana %5.1f%% sobre o fluxo livre" % (fonte, r["mediana_pct"]))

    piores = sorted([p for p in pares if p["div_t_livre_pct"] is not None],
                    key=lambda p: abs(p["div_t_livre_pct"]), reverse=True)[:3]
    print("\n  maiores divergências de tempo em fluxo livre:")
    for p in piores:
        print("    %s -> %s: TomTom %.1f min, HERE %.1f min (%+.1f%%)"
              % (p["origem"].split(",")[0], p["destino"].split(",")[0],
                 p["tomtom"]["t_livre_s"] / 60, p["here"]["t_livre_s"] / 60, p["div_t_livre_pct"]))

    print("\n=== B. GEOCODIFICACAO contra o catalogo ===")
    for g in res["frente_b_geocodificacao"]:
        h, t = g.get("here") or {}, g.get("tomtom") or {}
        print("  %-38s HERE %7s m | TomTom %7s m | entre as duas %7s m"
              % (g["polo"].split(",")[0],
                 h.get("desvio_do_catalogo_m", "erro"), t.get("desvio_do_catalogo_m", "erro"),
                 g.get("distancia_entre_geocodificadores_m", "-")))
    print("\nresultado em", saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
