#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
google_maps_server.py - Servidor MCP do Google Maps Platform

Terceira fonte de rede viaria, ao lado do TomTom e da HERE. Entrou no
ecossistema por medicao, em 21/10/2026: no desempate de coordenadas dos polos
de Salvador, o Google concordou com a HERE dentro de 29 m em Piraja, 79 m em
Mussurunga e 152 m em Acesso Norte, e foi o unico a acertar o Iguatemi, onde o
nome mudou para Shopping da Bahia e as outras duas fontes foram parar a 5,6 km
e 14,1 km do ponto certo.

APIs habilitadas na chave (conferido em 21/10/2026): Geocoding, Places (New),
Routes e Street View Static.

CONVENCOES VERIFICADAS CONTRA A API, nao supostas:
  - Routes: `duration` e o tempo com transito do momento; `staticDuration` e o
    tempo SEM transito ao vivo. ATENCAO: o estatico do Google NAO equivale ao
    fluxo livre do TomTom (`noTrafficTravelTimeInSeconds`) nem ao da HERE
    (`baseDuration`). Medido as 22h15 no par Piraja-Lapa: duration 949 s contra
    staticDuration 1.006 s, ou seja, o tempo real ficou MENOR que o estatico,
    o que indica condicao tipica embutida no estatico, nao condicao ideal.
    Ao comparar t0 entre as tres fontes, declarar essa diferenca de definicao.
  - computeRouteMatrix devolve uma LISTA de itens com originIndex,
    destinationIndex, duration, staticDuration, distanceMeters e condition.
    A ordem nao e garantida: usar os indices, nunca a posicao na lista.
    `condition` diferente de ROUTE_EXISTS significa par sem rota.
  - Geocoding devolve `location_type`: ROOFTOP e o ponto exato da edificacao;
    GEOMETRIC_CENTER e centroide; APPROXIMATE nao serve como ponto de parada.
  - Places (New) devolve o TIPO do lugar, o que separa, no mesmo nome, a
    estacao de metro do terminal de onibus. Em Piraja os dois distam 277 m; no
    Aeroporto, 1.116 m. Essa distincao muda tempo de acesso e nao pode ser
    resolvida por nome.

A chave NUNCA fica no codigo: vem do bloco "env" do servidor google-maps em
claude_desktop_config.json, na variavel GOOGLE_MAPS_API_KEY. A Geocoding leva a
chave na query string, entao TODO texto de erro passa por _sem_chave antes de
sair (licao de 21/10: uma mensagem de erro com a URL crua vazou a chave do
TomTom para a conversa).
"""
import json
import os
import re
import sys
import warnings
import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

CHAVE = os.environ.get("GOOGLE_MAPS_API_KEY", "")

GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES = "https://places.googleapis.com/v1/places:searchText"
ROTAS = "https://routes.googleapis.com/directions/v2:computeRoutes"
MATRIZ = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"

# TLS: verificacao ativa, com o conjunto de certificados informado
# EXPLICITAMENTE. Isso tem precedencia sobre SSL_CERT_FILE e REQUESTS_CA_BUNDLE
# herdados do processo que lanca o servidor, que foi a causa investigada na
# falha do servidor do TomTom.
_INSEGURO = os.environ.get("GOOGLE_MCP_INSECURE_SSL", "0") == "1"
_BUNDLE = os.environ.get("GOOGLE_CA_BUNDLE", "").strip()
if not _BUNDLE:
    try:
        import certifi
        _BUNDLE = certifi.where()
    except Exception:
        _BUNDLE = ""
_VERIFICAR = False if _INSEGURO else (_BUNDLE or True)
if _INSEGURO:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn("GOOGLE_MCP_INSECURE_SSL=1: verificacao de certificado desativada.", RuntimeWarning)

_ERRO_SEM_CHAVE = (
    "Erro: variavel de ambiente GOOGLE_MAPS_API_KEY nao definida. Configure-a no bloco 'env' "
    "do servidor google-maps em claude_desktop_config.json e reinicie o Claude Desktop."
)
if not CHAVE:
    print("AVISO: GOOGLE_MAPS_API_KEY ausente; as ferramentas do Google retornarao erro.",
          file=sys.stderr)

mcp = FastMCP("GoogleMapsMCP")


def _sem_chave(texto: str) -> str:
    """Remove a chave de qualquer texto antes de devolve-lo a conversa."""
    return re.sub(r"(?i)(key=)[^&\s'\"]+", r"\1<chave_censurada>", texto or "")


def _erro_http(status: int, detalhe: str) -> str:
    extra = ""
    if status in (401, 403):
        extra = (" Isso e credencial ou API nao habilitada no projeto: conferir em "
                 "Google Cloud Console > APIs e servicos, e as restricoes da chave.")
    elif status == 429:
        extra = " Cota da API excedida no projeto."
    return f"Erro Google ({status}): {_sem_chave(detalhe)[:300]}{extra}"


def _pedir(url, *, params=None, corpo=None, mask=None, timeout=45):
    """Devolve (dados, None) ou (None, mensagem). Places e Routes usam cabecalho;
    a Geocoding usa query string, por isso a censura da chave em todo erro."""
    if not CHAVE:
        return None, _ERRO_SEM_CHAVE
    try:
        if corpo is None:
            p = dict(params or {})
            p["key"] = CHAVE
            r = requests.get(url, params=p, timeout=timeout, verify=_VERIFICAR)
        else:
            cab = {"Content-Type": "application/json", "X-Goog-Api-Key": CHAVE}
            if mask:
                cab["X-Goog-FieldMask"] = mask
            r = requests.post(url, json=corpo, headers=cab, timeout=timeout, verify=_VERIFICAR)
    except requests.exceptions.SSLError as e:
        return None, ("Falha de verificacao de certificado TLS. Conjunto em uso: "
                      f"{_BUNDLE or 'padrao'}. Motivo: {_sem_chave(str(e))[:250]}")
    except Exception as e:
        return None, f"Falha na conexao com o Google: {type(e).__name__}"

    try:
        dados = r.json()
    except Exception:
        return None, f"Erro Google (HTTP {r.status_code}): resposta nao-JSON."
    if r.status_code != 200:
        det = ""
        if isinstance(dados, dict):
            det = (dados.get("error") or {}).get("message", "") or dados.get("error_message", "")
        return None, _erro_http(r.status_code, det)
    # A Geocoding devolve 200 com status proprio no corpo.
    if isinstance(dados, dict) and dados.get("status") not in (None, "OK", "ZERO_RESULTS"):
        return None, _erro_http(200, f"{dados.get('status')}: {dados.get('error_message', '')}")
    return dados, None


def _segundos(valor) -> float:
    """Converte '949s' em 949.0. A Routes devolve duracao como texto."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    return float(str(valor).rstrip("s") or 0)


@mcp.tool()
def geocodificar_google(endereco: str, limite: int = 3) -> str:
    """Converte endereco em coordenadas pela Geocoding API, com o nivel de precisao.

    O campo de precisao e o que decide se a coordenada serve: ROOFTOP e o ponto
    da edificacao; GEOMETRIC_CENTER e centroide de um poligono; APPROXIMATE e
    aproximacao de area e NAO serve como ponto de parada nem de acesso.

    Para equipamento de transporte (estacao, terminal), preferir
    buscar_lugares_google, que devolve o TIPO do lugar e permite separar a
    estacao de metro do terminal de onibus de mesmo nome.
    """
    dados, erro = _pedir(GEOCODE, params={"address": endereco, "region": "br",
                                          "language": "pt-BR"})
    if erro:
        return erro
    res = dados.get("results") or []
    if not res:
        return f"Nenhum resultado para '{endereco}'. Incluir cidade e estado na consulta."

    linhas = [f"=== GOOGLE GEOCODING: '{endereco}' ==="]
    for i, r in enumerate(res[:max(1, min(int(limite), 10))], 1):
        loc = r["geometry"]["location"]
        linhas.append(
            f"{i}. {r.get('formatted_address', 'sem endereco')}\n"
            f"   lat {loc['lat']}, lon {loc['lng']} | precisao: {r['geometry'].get('location_type')}"
            f" | tipos: {', '.join((r.get('types') or [])[:4])}"
        )
    return "\n".join(linhas)


@mcp.tool()
def buscar_lugares_google(consulta: str, limite: int = 5) -> str:
    """Busca lugares pela Places API (New), devolvendo o TIPO de cada um.

    E a ferramenta certa para fixar coordenada de equipamento de transporte,
    porque separa, dentro do mesmo nome, subway_station, train_station,
    bus_station, transit_station e shopping_mall. Em Salvador essa distincao
    vale centenas de metros: em Piraja a estacao de metro e o terminal de
    onibus distam 277 m, e no Aeroporto, 1.116 m.

    Tambem resolve nome desatualizado: o antigo Shopping Iguatemi responde hoje
    como Shopping da Bahia, e buscas por nome antigo em outras fontes caem a
    quilometros do lugar certo.
    """
    dados, erro = _pedir(PLACES,
                         corpo={"textQuery": consulta, "languageCode": "pt-BR",
                                "maxResultCount": max(1, min(int(limite), 20))},
                         mask=("places.displayName,places.formattedAddress,places.location,"
                               "places.primaryType,places.types,places.businessStatus"))
    if erro:
        return erro
    lugares = dados.get("places") or []
    if not lugares:
        return f"Nenhum lugar encontrado para '{consulta}'."

    linhas = [f"=== GOOGLE PLACES (New): '{consulta}' ==="]
    for i, p in enumerate(lugares, 1):
        loc = p.get("location") or {}
        tipos = [t for t in (p.get("types") or []) if t not in ("point_of_interest", "establishment")]
        linhas.append(
            f"{i}. {p.get('displayName', {}).get('text', 'sem nome')}"
            f"  [{p.get('primaryType') or 'tipo nao declarado'}]\n"
            f"   lat {loc.get('latitude')}, lon {loc.get('longitude')}\n"
            f"   {p.get('formattedAddress', '')}"
            + (f"\n   outros tipos: {', '.join(tipos[:5])}" if tipos else "")
        )
    return "\n".join(linhas)


@mcp.tool()
def calcular_tempo_e_distancia_google(lat_origem: float, lon_origem: float,
                                      lat_destino: float, lon_destino: float,
                                      considerar_transito: bool = True) -> str:
    """Distancia e tempo entre dois pontos pela Routes API.

    Par com as ferramentas equivalentes do TomTom e da HERE, para comparacao no
    mesmo par origem-destino.

    ATENCAO a definicao: o tempo "sem transito" do Google (staticDuration) nao
    e o fluxo livre do TomTom nem o da HERE. Medido as 22h15, o tempo COM
    transito veio menor que o estatico, o que so acontece se o estatico embutir
    condicao tipica. Para t0 de modelo, declarar a fonte e a definicao.
    """
    corpo = {
        "origin": {"location": {"latLng": {"latitude": lat_origem, "longitude": lon_origem}}},
        "destination": {"location": {"latLng": {"latitude": lat_destino, "longitude": lon_destino}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE" if considerar_transito else "TRAFFIC_UNAWARE",
        "languageCode": "pt-BR",
    }
    dados, erro = _pedir(ROTAS, corpo=corpo,
                         mask="routes.duration,routes.staticDuration,routes.distanceMeters")
    if erro:
        return erro
    rotas = dados.get("routes") or []
    if not rotas:
        return "O Google respondeu sem rota. Conferir se as coordenadas caem em via."

    r = rotas[0]
    dist_km = (r.get("distanceMeters") or 0) / 1000.0
    t_tr = _segundos(r.get("duration")) / 60.0
    t_est = _segundos(r.get("staticDuration")) / 60.0
    v_tr = dist_km / (t_tr / 60.0) if t_tr else 0.0
    v_est = dist_km / (t_est / 60.0) if t_est else 0.0
    dif = t_tr - t_est

    linhas = [
        "=== CONSULTA GOOGLE ROUTES ===",
        f"• Distância da ligação: {dist_km:.2f} km",
        f"• Tempo estimado sem trânsito ao vivo: {t_est:.1f} min ({v_est:.1f} km/h)",
        f"• Tempo com trânsito do momento: {t_tr:.1f} min ({v_tr:.1f} km/h)",
        f"• Diferença: {dif:+.1f} min",
    ]
    if dif < -0.1:
        linhas.append("  (tempo com trânsito MENOR que o estático: o estático do Google embute "
                      "condição típica, não condição ideal; não usar como t0 de fluxo livre)")
    linhas.append(f"• Trânsito considerado: {'momento da consulta' if considerar_transito else 'não'}")
    return "\n".join(linhas)


@mcp.tool()
def matriz_impedancia_google(origens: list[list[float]], destinos: list[list[float]],
                             considerar_transito: bool = False) -> str:
    """Matriz de tempos e distancias pela Routes API, em uma chamada.

    origens e destinos: listas de pares [latitude, longitude]. Par com
    matriz_impedancia_here, para comparar as duas fontes na mesma instancia.

    A resposta vem como lista de itens com indices de origem e destino, e a
    ordem nao e garantida: a montagem aqui usa os indices. Par com `condition`
    diferente de ROUTE_EXISTS aparece como n/d, nunca como zero.
    """
    def validar(pontos, nome):
        if not pontos:
            return f"Erro: lista de {nome} vazia."
        for p in pontos:
            if len(p) != 2:
                return f"Erro: cada ponto de {nome} deve ser [latitude, longitude]; recebi {p}."
            if not (-90 <= p[0] <= 90) or not (-180 <= p[1] <= 180):
                return f"Erro: ponto de {nome} fora de faixa: {p}."
        return ""

    for pontos, nome in ((origens, "origens"), (destinos, "destinos")):
        e = validar(pontos, nome)
        if e:
            return e

    def fora_do_brasil(p):
        return not (-34.0 <= p[0] <= 6.0 and -74.5 <= p[1] <= -32.0)

    suspeitos = [p for p in list(origens) + list(destinos) if fora_do_brasil(p)]
    aviso = ""
    if suspeitos:
        aviso = (f"AVISO: {len(suspeitos)} ponto(s) fora da envoltoria do Brasil, por exemplo "
                 f"{suspeitos[0]}. Conferir a ordem [latitude, longitude].\n")

    pares = len(origens) * len(destinos)
    if pares > 400:
        return (f"Erro: {len(origens)} x {len(destinos)} = {pares} pares, acima do limite de 400 "
                "imposto nesta ferramenta. Partir em blocos.")

    ponto = lambda c: {"waypoint": {"location": {"latLng": {"latitude": c[0], "longitude": c[1]}}}}
    corpo = {"origins": [ponto(c) for c in origens],
             "destinations": [ponto(c) for c in destinos],
             "travelMode": "DRIVE",
             "routingPreference": "TRAFFIC_AWARE" if considerar_transito else "TRAFFIC_UNAWARE"}
    dados, erro = _pedir(MATRIZ, corpo=corpo, timeout=120,
                         mask=("originIndex,destinationIndex,duration,staticDuration,"
                               "distanceMeters,condition"))
    if erro:
        return erro
    if not isinstance(dados, list):
        return "Resposta inesperada da Routes: esperava lista de pares."

    nd = len(destinos)
    tempos = {}
    for it in dados:
        i, j = it.get("originIndex"), it.get("destinationIndex")
        if i is None or j is None:
            continue
        ok = it.get("condition") == "ROUTE_EXISTS"
        tempos[(i, j)] = (
            _segundos(it.get("duration") if considerar_transito else it.get("staticDuration")),
            (it.get("distanceMeters") or 0), ok)

    linhas = []
    if aviso:
        linhas.append(aviso)
    linhas += [f"=== GOOGLE ROUTES MATRIX ({len(origens)} origens x {nd} destinos, "
               f"{'com trânsito do momento' if considerar_transito else 'sem trânsito ao vivo'}) ===",
               "Tempos em minutos; distâncias em km; n/d = par sem rota.", ""]
    linhas.append("origem\\destino " + " ".join(f"{j + 1:>12}" for j in range(nd)))
    sem_rota = 0
    validos = []
    for i in range(len(origens)):
        cel = []
        for j in range(nd):
            t, d, ok = tempos.get((i, j), (0.0, 0, False))
            if not ok:
                cel.append("n/d")
                sem_rota += 1
            else:
                cel.append(f"{t / 60.0:6.1f}/{d / 1000.0:5.1f}")
                if t > 0:
                    validos.append(t)
        linhas.append(f"{i + 1:>14} " + " ".join(f"{c:>12}" for c in cel))

    linhas.append("")
    if validos:
        linhas.append(f"Pares com tempo positivo: {len(validos)} de {pares} | "
                      f"tempo médio {sum(validos) / len(validos) / 60.0:.1f} min")
    if sem_rota:
        linhas.append(f"Pares sem rota: {sem_rota} de {pares}.")
    if not considerar_transito:
        linhas.append("Lembrete: o tempo sem trânsito ao vivo do Google embute condição típica; "
                      "não é o fluxo livre do TomTom nem o da HERE.")
    return "\n".join(linhas)


if __name__ == "__main__":
    mcp.run()
