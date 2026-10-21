#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
here_network_server.py - Servidor MCP da HERE para rede viaria e impedancia

Espelha as ferramentas do tomtom_network_server.py, para que as duas fontes
possam ser comparadas na mesma instancia, e acrescenta a matriz de impedancia,
que a HERE resolve em uma chamada.

Convencoes verificadas contra a API em 21/10/2026, nao supostas:
  - Routing v8 e Matrix v8: OMITIR departureTime devolve tempo COM transito;
    `departureTime=any` devolve tempo sem transito. O valor 'now' e recusado
    com 400 ("'now' is an invalid date/time"). Medido no par Piraja-Lapa:
    1.239 s com transito contra 1.099 s sem.
  - O `summary` do Routing v8 traz `duration` (com transito) e `baseDuration`
    (fluxo livre) na mesma resposta.
  - Traffic Flow v7: velocidades em METROS POR SEGUNDO (`speed`, `freeFlow`),
    convertidas aqui para km/h. `jamFactor` vai de 0 a 10.

A chave NUNCA fica no codigo: vem do bloco "env" do servidor here-network em
claude_desktop_config.json, na variavel HERE_API_KEY. Atencao: a plataforma
HERE entrega tambem refresh token (base64 com prefixo "reftkn"), que NAO
autentica estas chamadas; aqui e preciso a API Key (REST).
"""
import os
import sys
import warnings
import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

CHAVE = os.environ.get("HERE_API_KEY", "")

GEOCODE = "https://geocode.search.hereapi.com/v1/geocode"
ROUTING = "https://router.hereapi.com/v8/routes"
MATRIZ = "https://matrix.router.hereapi.com/v8/matrix"
FLOW = "https://data.traffic.hereapi.com/v7/flow"

# TLS: verificacao ATIVA por padrao. O tomtom_network_server.py desta mesma
# maquina usa verify=False para contornar a interceptacao de certificado do
# ambiente; aqui a solucao correta vem primeiro e o paliativo e explicito:
#   1. REQUESTS_CA_BUNDLE apontando para o certificado raiz corporativo
#   2. em ultimo caso, HERE_MCP_INSECURE_SSL=1
_INSEGURO = os.environ.get("HERE_MCP_INSECURE_SSL", "0") == "1"
_VERIFICAR = not _INSEGURO
if _INSEGURO:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn("HERE_MCP_INSECURE_SSL=1: verificacao de certificado TLS desativada. "
                  "Preferir REQUESTS_CA_BUNDLE com o certificado corporativo.", RuntimeWarning)

_ERRO_SEM_CHAVE = (
    "Erro: variavel de ambiente HERE_API_KEY nao definida. Configure-a no bloco 'env' do "
    "servidor here-network em claude_desktop_config.json e reinicie o Claude Desktop. "
    "Usar a API Key REST do projeto HERE, nao o refresh token da plataforma."
)
_AJUDA_TLS = (
    "Falha de verificacao de certificado TLS nesta maquina. Duas saidas, nessa ordem: "
    "exportar o certificado raiz corporativo e apontar REQUESTS_CA_BUNDLE para ele no bloco "
    "'env' do servidor, ou, como paliativo, definir HERE_MCP_INSECURE_SSL=1."
)
if not CHAVE:
    print("AVISO: HERE_API_KEY ausente; as ferramentas da HERE retornarao erro ate a chave "
          "ser definida.", file=sys.stderr)

mcp = FastMCP("HereNetworkMCP")


def _pedir(metodo: str, url: str, **kw):
    """Chamada unica a HERE. Devolve (dados, None) ou (None, mensagem_de_erro)."""
    if not CHAVE:
        return None, _ERRO_SEM_CHAVE
    try:
        r = requests.request(metodo, url, timeout=kw.pop("timeout", 30),
                             verify=_VERIFICAR, **kw)
    except requests.exceptions.SSLError:
        return None, _AJUDA_TLS
    except Exception as e:
        return None, f"Falha na conexao com a HERE: {type(e).__name__}"

    try:
        dados = r.json()
    except Exception:
        return None, f"Erro HERE (HTTP {r.status_code}): resposta nao-JSON."

    if r.status_code != 200:
        # A URL leva a apiKey na query: nunca devolver r.url nem r.text bruto.
        titulo = dados.get("title") or dados.get("error") or ""
        causa = dados.get("cause") or dados.get("error_description") or ""
        extra = ""
        if r.status_code == 401:
            extra = (" Problema de credencial: conferir se HERE_API_KEY e a API Key REST "
                     "do projeto, e nao o refresh token da plataforma.")
        elif r.status_code == 429:
            extra = " Limite de requisicoes da conta HERE: espacar as chamadas."
        return None, f"Erro HERE ({r.status_code}): {titulo} {causa}".strip() + extra
    return dados, None


@mcp.tool()
def calcular_tempo_e_distancia_here(lat_origem: float, lon_origem: float,
                                    lat_destino: float, lon_destino: float,
                                    considerar_transito: bool = True) -> str:
    """Distancia, tempo em fluxo livre e tempo com transito entre dois pontos, pela HERE.

    Par com calcular_tempo_e_distancia_tomtom: mesmas entradas e mesmas
    grandezas na saida, para que as duas fontes sejam comparaveis no mesmo par
    origem-destino. Divergencia entre elas e esperada (cada uma tem sua propria
    rede e seu proprio historico de velocidade) e deve ser medida, nao suposta.

    considerar_transito=True usa o transito do momento da consulta, portanto o
    resultado depende da hora. Para impedancia de rede em modelo, preferir
    considerar_transito=False (fluxo livre) ou declarar o periodo da coleta.
    """
    params = {"transportMode": "car", "return": "summary",
              "origin": f"{lat_origem},{lon_origem}",
              "destination": f"{lat_destino},{lon_destino}",
              "apiKey": CHAVE}
    if not considerar_transito:
        params["departureTime"] = "any"      # verificado: 'any' desliga o transito

    dados, erro = _pedir("GET", ROUTING, params=params)
    if erro:
        return erro
    try:
        s = dados["routes"][0]["sections"][0]["summary"]
    except (KeyError, IndexError):
        return "A HERE respondeu 200 sem rota utilizavel. Conferir se as coordenadas estao em via."

    dist_km = s["length"] / 1000.0
    t_transito_min = s["duration"] / 60.0
    t_livre_min = s.get("baseDuration", s["duration"]) / 60.0
    atraso_min = max(0.0, t_transito_min - t_livre_min)
    v_oper = dist_km / (t_transito_min / 60.0) if t_transito_min > 0 else 0.0
    v_livre = dist_km / (t_livre_min / 60.0) if t_livre_min > 0 else 0.0

    return (
        "=== CONSULTA HERE ROUTING v8 ===\n"
        f"• Distância da ligação: {dist_km:.2f} km\n"
        f"• Tempo em fluxo livre (t0): {t_livre_min:.1f} min ({v_livre:.1f} km/h)\n"
        f"• Tempo com trânsito (t_atual): {t_transito_min:.1f} min ({v_oper:.1f} km/h)\n"
        f"• Atraso por congestionamento: {atraso_min:.1f} min "
        f"({(atraso_min / t_livre_min * 100 if t_livre_min else 0):.0f}% sobre t0)\n"
        f"• Trânsito considerado: {'momento da consulta' if considerar_transito else 'não (departureTime=any)'}"
    )


@mcp.tool()
def consultar_velocidade_trecho_viario_here(latitude: float, longitude: float,
                                            raio_m: int = 300) -> str:
    """Velocidade praticada e de fluxo livre nos trechos em torno de um ponto, pela HERE.

    Par com consultar_velocidade_trecho_viario (TomTom). A HERE devolve TODOS os
    trechos no raio pedido, com nome de via e extensao, e nao um unico segmento:
    util para ver a degradacao ao longo de um corredor. As velocidades vem da
    API em m/s e sao convertidas para km/h aqui.

    jamFactor vai de 0 (livre) a 10 (parado). Acima de 8 a HERE considera o
    trecho em congestionamento severo.
    """
    params = {"in": f"circle:{latitude},{longitude};r={max(10, int(raio_m))}",
              "locationReferencing": "none", "apiKey": CHAVE}
    dados, erro = _pedir("GET", FLOW, params=params)
    if erro:
        return erro

    res = dados.get("results") or []
    if not res:
        return (f"Nenhum trecho com dado de fluxo no raio de {raio_m} m em "
                f"{latitude}, {longitude}. Ampliar o raio ou conferir o ponto.")

    linhas = [f"=== HERE TRAFFIC FLOW v7 (ponto {latitude}, {longitude}, raio {raio_m} m) ===",
              f"Atualizado em: {dados.get('sourceUpdated', 'nao informado')}",
              f"Trechos no raio: {len(res)}"]
    for item in res[:12]:
        f = item.get("currentFlow") or {}
        loc = item.get("location") or {}
        v = (f.get("speed") or 0) * 3.6
        v0 = (f.get("freeFlow") or 0) * 3.6
        deg = (1 - v / v0) * 100 if v0 > 0 else 0.0
        linhas.append(
            f"\n• {loc.get('description', 'via sem nome')} ({loc.get('length', 0):.0f} m)\n"
            f"  V praticada {v:.1f} km/h | V fluxo livre {v0:.1f} km/h | degradação {deg:.0f}%\n"
            f"  jamFactor {f.get('jamFactor', 0):.1f}/10 | confiabilidade "
            f"{(f.get('confidence') or 0) * 100:.0f}% | {f.get('traversability', 'desconhecido')}"
        )
    if len(res) > 12:
        linhas.append(f"\n(+{len(res) - 12} trechos omitidos; reduzir o raio para focar)")
    return "\n".join(linhas)


@mcp.tool()
def geocodificar_here(endereco: str, limite: int = 3) -> str:
    """Converte endereco em coordenadas pela HERE, com o escore de aderencia da busca.

    Usar para conferir coordenada de ponto de projeto antes de levar para a
    rede ou para a pesquisa de campo. O escore (0 a 1) diz o quanto a resposta
    casa com o texto pedido: abaixo de 0,8 conferir manualmente.

    Nunca adotar a primeira coordenada sem olhar o tipo do resultado: 'place' e
    ponto de interesse, 'street' e eixo de via, 'locality' e centroide de
    bairro ou cidade, que nao serve como ponto de parada.
    """
    params = {"q": endereco, "limit": max(1, min(int(limite), 10)),
              "lang": "pt-BR", "apiKey": CHAVE}
    dados, erro = _pedir("GET", GEOCODE, params=params)
    if erro:
        return erro

    itens = dados.get("items") or []
    if not itens:
        return f"Nenhum resultado para '{endereco}'. Reformular incluindo cidade e estado."

    linhas = [f"=== HERE GEOCODE: '{endereco}' ==="]
    for i, it in enumerate(itens, 1):
        p = it.get("position") or {}
        escore = (it.get("scoring") or {}).get("queryScore")
        linhas.append(
            f"{i}. {it.get('title', 'sem titulo')}\n"
            f"   lat {p.get('lat')}, lon {p.get('lng')} | tipo: {it.get('resultType', '?')}"
            + (f" | escore {escore:.2f}" if isinstance(escore, (int, float)) else "")
        )
        end = (it.get("address") or {}).get("label")
        if end:
            linhas.append(f"   {end}")
    return "\n".join(linhas)


@mcp.tool()
def matriz_impedancia_here(origens: list[list[float]], destinos: list[list[float]],
                           considerar_transito: bool = False) -> str:
    """Matriz de tempos e distancias entre conjuntos de pontos, em uma chamada.

    origens e destinos: listas de pares [latitude, longitude].
    Serve para impedancia de rede e para matriz de tempo entre zonas ou
    terminais, sem fazer uma chamada por par.

    considerar_transito=False (padrao) devolve fluxo livre, que e o que entra
    em modelo de rede como t0. Com True, o resultado depende da hora da
    consulta e so deve ser usado com o periodo declarado no entregavel.

    Limite imposto aqui: 400 pares por chamada, por prudencia, nao por
    documentacao da API. Acima disso, partir em blocos ou usar o modo
    assincrono da HERE, que nao esta implementado nesta ferramenta.
    """
    def validar(pontos, nome):
        if not pontos:
            return f"Erro: lista de {nome} vazia."
        for p in pontos:
            if len(p) != 2:
                return f"Erro: cada ponto de {nome} deve ser [latitude, longitude]; recebi {p}."
            if not (-90 <= p[0] <= 90) or not (-180 <= p[1] <= 180):
                return (f"Erro: ponto de {nome} fora de faixa: {p}. A ordem e "
                        "[latitude, longitude], nao [longitude, latitude].")
        return ""

    for pontos, nome in ((origens, "origens"), (destinos, "destinos")):
        e = validar(pontos, nome)
        if e:
            return e

    # Latitude e longitude trocadas e o erro classico, e nem sempre sai da faixa
    # valida: -38,5 e latitude legitima. Como o trabalho e no Brasil, ponto fora
    # da envoltoria do pais gera aviso, nao recusa.
    def fora_do_brasil(p):
        return not (-34.0 <= p[0] <= 6.0 and -74.5 <= p[1] <= -32.0)

    suspeitos = [p for p in list(origens) + list(destinos) if fora_do_brasil(p)]
    aviso_ordem = ""
    if suspeitos:
        aviso_ordem = ("AVISO: %d ponto(s) fora da envoltoria do Brasil, por exemplo %s. "
                       "Conferir se a ordem e [latitude, longitude] e nao o contrario.\n"
                       % (len(suspeitos), suspeitos[0]))

    pares = len(origens) * len(destinos)
    if pares > 400:
        return (f"Erro: {len(origens)} x {len(destinos)} = {pares} pares, acima do limite de 400 "
                "imposto nesta ferramenta. Partir em blocos.")

    corpo = {
        "origins": [{"lat": p[0], "lng": p[1]} for p in origens],
        "destinations": [{"lat": p[0], "lng": p[1]} for p in destinos],
        "regionDefinition": {"type": "world"},
        "matrixAttributes": ["travelTimes", "distances"],
    }
    if not considerar_transito:
        corpo["departureTime"] = "any"      # verificado: com transito e omitir o campo

    dados, erro = _pedir("POST", MATRIZ, params={"async": "false", "apiKey": CHAVE},
                         json=corpo, timeout=120)
    if erro:
        return erro

    m = dados.get("matrix") or {}
    tempos, dists = m.get("travelTimes") or [], m.get("distances") or []
    if len(tempos) != pares:
        return (f"A HERE devolveu {len(tempos)} tempos para {pares} pares. "
                f"Codigos de erro por par em 'errorCodes': {m.get('errorCodes')}")

    # errorCodes marca par sem rota. Sem isso, um par inatingivel chega como 0 e
    # se confunde com viagem instantanea, que e pior do que faltar o dado.
    codigos = m.get("errorCodes") or []

    def sem_rota(k):
        return bool(codigos[k]) if k < len(codigos) else False

    nd = len(destinos)
    linhas = []
    if aviso_ordem:
        linhas.append(aviso_ordem)
    linhas += [f"=== HERE MATRIX v8 ({len(origens)} origens x {nd} destinos, "
               f"{'com trânsito do momento' if considerar_transito else 'fluxo livre'}) ===",
               "Tempos em minutos; distâncias em km; n/d = par sem rota.", ""]
    linhas.append("origem\\destino " + " ".join(f"{j + 1:>12}" for j in range(nd)))
    for i in range(len(origens)):
        cel = []
        for j in range(nd):
            k = i * nd + j
            if sem_rota(k):
                cel.append("n/d")
            else:
                cel.append(f"{tempos[k] / 60.0:6.1f}/{dists[k] / 1000.0:5.1f}")
        linhas.append(f"{i + 1:>14} " + " ".join(f"{c:>12}" for c in cel))

    nao_roteados = sum(1 for k in range(pares) if sem_rota(k))
    validos = [tempos[k] for k in range(pares) if not sem_rota(k) and tempos[k] > 0]
    linhas.append("")
    if validos:
        linhas.append(f"Pares com tempo positivo: {len(validos)} de {pares} | "
                      f"tempo médio {sum(validos) / len(validos) / 60.0:.1f} min")
    if nao_roteados:
        vistos = sorted({codigos[k] for k in range(pares) if sem_rota(k)})
        linhas.append(f"Pares sem rota: {nao_roteados} de {pares} (códigos HERE: {vistos}). "
                      "Causa usual: ponto longe de via navegável ou fora da região roteável.")
    return "\n".join(linhas)


if __name__ == "__main__":
    mcp.run()
