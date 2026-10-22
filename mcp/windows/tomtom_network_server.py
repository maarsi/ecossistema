#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tomtom_network_server.py — Servidor MCP para integração TomTom API no Claude Desktop (Windows)
Foco: Modelagem de Rede Viária e Matrizes de Impedância da RMS.
"""
import os
import json
import re
import warnings
import requests
from fastmcp import FastMCP

# TLS: verificacao ATIVA por padrao. A versao anterior passava verify=False em
# todas as chamadas, desativando a verificacao de certificado em definitivo,
# com o comentario "contornar a falha de SSL no Windows". A falha e real (o
# servidor em Node da Perplexity quebrou com "unable to verify the first
# certificate" na mesma maquina), mas o remedio certo vem primeiro e o
# paliativo fica explicito:
#   1. REQUESTS_CA_BUNDLE apontando para o certificado raiz corporativo
#   2. em ultimo caso, TOMTOM_MCP_INSECURE_SSL=1
#
# Medido em 21/10/2026, apos o reinicio: o MESMO interpretador
# (D:\TransportMCP\.venv) verifica o certificado do api.tomtom.com sem erro
# quando o script roda pelo Explorador, e FALHA quando o Claude Desktop lanca
# este servidor. Mesma maquina, mesmo certifi (2026.07.22), mesmo host. A
# diferenca esta no ambiente herdado do aplicativo, que pode trazer
# SSL_CERT_FILE ou REQUESTS_CA_BUNDLE apontando para um conjunto reduzido.
# Por isso o conjunto de certificados e informado EXPLICITAMENTE na chamada:
# verify com caminho tem precedencia sobre essas variaveis, e a verificacao
# continua ativa.
_INSEGURO = os.environ.get("TOMTOM_MCP_INSECURE_SSL", "0") == "1"
_BUNDLE = os.environ.get("TOMTOM_CA_BUNDLE", "").strip()
if not _BUNDLE:
    try:
        import certifi
        _BUNDLE = certifi.where()
    except Exception:
        _BUNDLE = ""

# MEDIDO em 21/10/2026, apos tres rodadas de diagnostico: a falha e
# INTERMITENTE e o motivo e 'unable to get local issuer certificate'. Nao e
# interceptacao (daria 'self signed certificate in chain') nem variavel de
# ambiente (SSL_CERT_FILE e REQUESTS_CA_BUNDLE vieram vazias). Resta cadeia
# incompleta servida por parte dos nos da CDN da TomTom: o certifi e um arquivo
# estatico e nao tem como completar cadeia que o servidor nao manda.
# O repositorio de certificados do Windows busca o intermediario que falta pela
# extensao AIA, e o truststore faz o Python usar esse repositorio. Assim a
# verificacao continua ATIVA e o caso ruim deixa de quebrar.
_TRUSTSTORE = False
if os.environ.get("TOMTOM_USAR_TRUSTSTORE", "1") == "1" and not _INSEGURO:
    try:
        import truststore
        truststore.inject_into_ssl()
        _TRUSTSTORE = True
    except Exception:
        pass        # sem o pacote, segue com o certifi

# Com o truststore ativo, verify precisa ser True: passar caminho de arquivo
# substituiria o repositorio do sistema pelo conjunto estatico, anulando o ganho.
_VERIFICAR = False if _INSEGURO else (True if _TRUSTSTORE else (_BUNDLE or True))
if _INSEGURO:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn("TOMTOM_MCP_INSECURE_SSL=1: verificacao de certificado TLS desativada. "
                  "Preferir REQUESTS_CA_BUNDLE com o certificado corporativo.", RuntimeWarning)

def _sem_chave(texto: str) -> str:
    """Remove a chave de API do texto antes de devolve-la a conversa.

    CORRECAO de 21/10/2026: a primeira versao desta mensagem incluia str(erro)
    cru, e a excecao do requests carrega a URL inteira. Como a TomTom recebe a
    chave na query string, a chave vazou para a conversa. Qualquer texto de erro
    desta API passa por aqui antes de sair.
    """
    return re.sub(r"(?i)(key=)[^&\s'\"]+", r"\1<chave_censurada>", texto or "")


def _ajuda_tls(erro: Exception) -> str:
    """Mensagem de falha de TLS COM o motivo real, que e o que permite decidir.

    'unable to get local issuer certificate' indica cadeia incompleta ou conjunto
    de certificados sem a raiz. 'self signed certificate in certificate chain'
    indica interceptacao por produto corporativo ou antivirus.
    """
    return (
        "Falha de verificacao de certificado TLS ao falar com a TomTom.\n"
        f"  repositorio do Windows via truststore: {'ativo' if _TRUSTSTORE else 'NAO ativo'}\n"
        f"  conjunto de certificados usado: {_BUNDLE or 'padrao do requests'}\n"
        f"  SSL_CERT_FILE herdado: {os.environ.get('SSL_CERT_FILE', '(nao definido)')}\n"
        f"  REQUESTS_CA_BUNDLE herdado: {os.environ.get('REQUESTS_CA_BUNDLE', '(nao definido)')}\n"
        f"  motivo relatado pelo OpenSSL: {_sem_chave(str(erro))[:400]}\n"
        "  Saidas, nessa ordem: apontar TOMTOM_CA_BUNDLE para um conjunto que contenha a raiz "
        "da cadeia, ou, como paliativo, definir TOMTOM_MCP_INSECURE_SSL=1 no bloco 'env'."
    )

mcp = FastMCP("TomTomTransportMCP")

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY", "")

# ----------------------------------------------------------------------
# CATALOGO DE POLOS DA RMS, corrigido em 21/10/2026.
#
# As coordenadas anteriores vinham de registro manual e tres delas estavam a
# mais de 1 km do equipamento: Piraja 1.672 m, Mussurunga 2.874 m e Acesso
# Norte 1.138 m. O erro foi achado comparando tres geocodificadores
# independentes: Google Places (New) e HERE concordaram entre si dentro de
# 29 m, 79 m e 152 m nesses tres polos, e ambos discordaram do catalogo. Com
# duas fontes independentes de acordo entre si e em desacordo com o registro,
# o suspeito e o registro.
#
# Nos outros polos a leitura se inverteu: em Lapa e Iguatemi o catalogo estava
# certo (211 m e 190 m) e foram HERE e TomTom que erraram, por nome
# desatualizado (o antigo Shopping Iguatemi responde hoje como Shopping da
# Bahia, e as duas foram parar a 5,6 km e 14,1 km).
#
# Cada polo guarda ATE DOIS pontos, porque sao coisas diferentes e a escolha
# muda o tempo de acesso: o acesso ao trilho e o embarque no alimentador. Em
# Piraja distam 277 m, na Lapa 70 m e no Aeroporto 1.116 m.
# ----------------------------------------------------------------------
POLOS_SALVADOR = {
    "LAPA": {
        "descricao": "Terminal Urbano / Metrô Linha 1",
        "trilho": {"lat": -12.98279, "lon": -38.51213, "tipo": "subway_station", "nome": "Lapa"},
        "onibus": {"lat": -12.98287, "lon": -38.51149, "tipo": "bus_station", "nome": "Lapa"},
        "separacao_m": 70.0, "catalogo_antigo_m": 211.0,
    },
    "PIRAJA": {
        "descricao": "Terminal de Integração / Metrô Linha 1",
        "trilho": {"lat": -12.92423, "lon": -38.46753, "tipo": "subway_station", "nome": "Estação Pirajá"},
        "onibus": {"lat": -12.92593, "lon": -38.46566, "tipo": "bus_station", "nome": "Estação Pirajá"},
        "separacao_m": 277.0, "catalogo_antigo_m": 1672.0,
    },
    "ACESSO NORTE": {
        "descricao": "Terminal / Integração Linhas 1 e 2",
        "trilho": {"lat": -12.96886, "lon": -38.47720, "tipo": "subway_station", "nome": "Acesso Norte"},
        "onibus": None, "catalogo_antigo_m": 1138.0,
    },
    "MUSSURUNGA": {
        "descricao": "Terminal Urbano / Metrô Linha 2",
        "trilho": {"lat": -12.92148, "lon": -38.35906, "tipo": "subway_station", "nome": "Estação Mussurunga"},
        "onibus": None, "catalogo_antigo_m": 2874.0,
    },
    "AEROPORTO": {
        "descricao": "Metrô Linha 2 / Lauro de Freitas",
        # O Google tipou este ponto como transit_stop nesta coleta e como
        # subway_station em consulta anterior: conferir in loco antes de usar
        # como acesso de passageiro.
        "trilho": {"lat": -12.90421, "lon": -38.34119, "tipo": "transit_stop", "nome": "Estação Aeroporto"},
        "onibus": {"lat": -12.91329, "lon": -38.33680, "tipo": "bus_station",
                   "nome": "Terminal do Aeroporto Internacional de Salvador"},
        "separacao_m": 1116.0, "catalogo_antigo_m": 774.0,
    },
    "IGUATEMI": {
        "descricao": "Eixo Central / Metrô Linha 2 / BRT",
        "trilho": None, "onibus": None,
        "outro": {"lat": -12.97946, "lon": -38.46349, "tipo": "bus_stop",
                  "nome": "Estação de Transbordo do Iguatemi"},
        "catalogo_antigo_m": 190.0,
    },
    "BARRA": {
        "descricao": "Polo Gerador / Bacia Orla",
        "trilho": None, "onibus": None,
        "outro": {"lat": -13.00821, "lon": -38.52669, "tipo": None, "nome": "Barra"},
        "catalogo_antigo_m": 506.0,
    },
    "CALCADA": {
        "descricao": "Bacia Ferroviária / Cidade Baixa",
        "trilho": None, "onibus": None,
        "outro": {"lat": -12.94598, "lon": -38.50026, "tipo": "transportation_service",
                  "nome": "Estação Calçada"},
        "catalogo_antigo_m": 286.0,
    },
}

# ----------------------------------------------------------------------
# 1. MATRIZ DE IMPEDÂNCIA / TEMPOS DE VIAGEM (ROUTING API)
# ----------------------------------------------------------------------
@mcp.tool()
def calcular_tempo_e_distancia_tomtom(
    lat_origem: float,
    lon_origem: float,
    lat_destino: float,
    lon_destino: float,
    considerar_transito: bool = True
) -> str:
    """
    Calcula distancia (km), tempo em fluxo livre (min) e tempo com transito atual (min)
    entre duas coordenadas da RMS (ex: Estação Lapa para Estação Aeroporto).

    CORRECAO de 21/10/2026: a versao anterior nao pedia computeTravelTimeFor=all,
    e sem esse parametro a resposta do TomTom NAO traz
    noTrafficTravelTimeInSeconds. O codigo caia no valor de reserva e reportava o
    tempo COM transito como se fosse o t0, com atraso sempre zero. Medido no par
    Piraja-Lapa: 1.305 s com transito contra 1.133 s em fluxo livre, 15,2% que
    estavam sendo perdidos. Qualquer t0 obtido antes dessa correcao esta
    contaminado com transito e nao serve para calibrar BPR.

    O atraso agora e a diferenca entre os dois tempos. O campo
    trafficDelayInSeconds nao serve para isso: ele mede atraso por incidente
    declarado e voltou 0 nos 28 pares medidos, inclusive nos que tinham 20% de
    degradacao.
    """
    if not TOMTOM_KEY:
        return "Erro: Variável de ambiente TOMTOM_API_KEY não configurada."

    url = f"https://api.tomtom.com/routing/1/calculateRoute/{lat_origem},{lon_origem}:{lat_destino},{lon_destino}/json"

    params = {
        "key": TOMTOM_KEY,
        "traffic": "true" if considerar_transito else "false",
        "travelMode": "car",
        "routeType": "fastest",
        "computeTravelTimeFor": "all",      # sem isto nao vem o tempo em fluxo livre
    }

    try:
        r = requests.get(url, params=params, timeout=15, verify=_VERIFICAR)
        if r.status_code != 200:
            # Nao devolver r.text: a URL e o corpo podem ecoar a chave.
            try:
                detalhe = (r.json().get("error") or {}).get("description", "")
            except Exception:
                detalhe = ""
            return f"Erro na API TomTom (HTTP {r.status_code}): {detalhe or 'falha reportada pelo gateway'}"

        dados = r.json()
        sumario = dados["routes"][0]["summary"]

        distancia_km = sumario["lengthInMeters"] / 1000.0
        tempo_transito_min = sumario["travelTimeInSeconds"] / 60.0
        t0_s = sumario.get("noTrafficTravelTimeInSeconds")
        if t0_s is None:
            # Sem o campo, nao inventar t0: dizer que falta.
            return (f"=== CONSULTA TOMTOM ROUTING ===\n"
                    f"• Distância da ligação: {distancia_km:.2f} km\n"
                    f"• Tempo com trânsito: {tempo_transito_min:.1f} min\n"
                    f"• Tempo em fluxo livre: NAO RETORNADO pela API nesta chamada. "
                    f"Nao usar o tempo acima como t0.")

        tempo_fluxo_livre_min = t0_s / 60.0
        atraso_min = max(0.0, tempo_transito_min - tempo_fluxo_livre_min)
        v_oper = distancia_km / (tempo_transito_min / 60.0) if tempo_transito_min else 0.0
        v_livre = distancia_km / (tempo_fluxo_livre_min / 60.0) if tempo_fluxo_livre_min else 0.0

        return (
            f"=== CONSULTA TOMTOM ROUTING ===\n"
            f"• Distância da ligação: {distancia_km:.2f} km\n"
            f"• Tempo em fluxo livre (t0): {tempo_fluxo_livre_min:.1f} min ({v_livre:.1f} km/h)\n"
            f"• Tempo com trânsito (t_atual): {tempo_transito_min:.1f} min ({v_oper:.1f} km/h)\n"
            f"• Atraso por congestionamento: {atraso_min:.1f} min "
            f"({(atraso_min / tempo_fluxo_livre_min * 100 if tempo_fluxo_livre_min else 0):.0f}% sobre t0)\n"
            f"• Trânsito considerado: {'momento da consulta' if considerar_transito else 'não'}"
        )
    except requests.exceptions.SSLError as e:
        return _ajuda_tls(e)
    except Exception as e:
        return f"Erro na conexão com a TomTom: {type(e).__name__}"

# ----------------------------------------------------------------------
# 2. FLUXO E VELOCIDADE EM SEGMENTO DE VIA (TRAFFIC FLOW API)
# ----------------------------------------------------------------------
@mcp.tool()
def consultar_velocidade_trecho_viario(latitude: float, longitude: float) -> str:
    """
    Obtém a velocidade livre da via e a velocidade praticada no momento para um ponto viário
    específico (ex: Av. Paralela, Bonocô, BR-324).
    """
    if not TOMTOM_KEY:
        return "Erro: Variável de ambiente TOMTOM_API_KEY não configurada."

    url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
    params = {
        "key": TOMTOM_KEY,
        "point": f"{latitude},{longitude}",
        "unit": "kmph"
    }

    try:
        r = requests.get(url, params=params, timeout=15, verify=_VERIFICAR)
        if r.status_code != 200:
            # Nao devolver r.text: a URL carrega a chave na query.
            return (f"Erro na API TomTom Flow (HTTP {r.status_code}). "
                    "Conferir se o ponto cai sobre via mapeada.")

        dados = r.json().get("flowSegmentData", {})
        v_livre = dados.get("freeFlowSpeed", 0)
        v_atual = dados.get("currentSpeed", 0)
        confianca = dados.get("confidence", 0)
        bloqueado = dados.get("roadClosure", False)

        fator_congestao = (1 - (v_atual / v_livre)) * 100 if v_livre > 0 else 0

        return (
            f"=== TOMTOM TRAFFIC FLOW (Ponto {latitude}, {longitude}) ===\n"
            f"• Velocidade em Fluxo Livre (V0): {v_livre} km/h\n"
            f"• Velocidade Atual Praticada: {v_atual} km/h\n"
            f"• Nível de Degradação/Congestão: {fator_congestao:.1f}%\n"
            f"• Confiabilidade da Amostra: {confianca * 100:.0f}%\n"
            f"• Via Bloqueada: {'SIM' if bloqueado else 'NÃO'}"
        )
    except requests.exceptions.SSLError as e:
        return _ajuda_tls(e)
    except Exception as e:
        return f"Erro na consulta de tráfego: {type(e).__name__}"

# ----------------------------------------------------------------------
# 3. POLOS E ESTAÇÕES MULTIMODAIS DA RMS PRÉ-CATALOGADOS
# ----------------------------------------------------------------------
@mcp.tool()
def obter_coordenadas_polos_salvador(polo: str) -> str:
    """
    Retorna as coordenadas exatas dos principais terminais de ônibus e estações do metrô de Salvador/RMS.
    """
    polo_up = polo.upper().replace("Á", "A").replace("Ç", "C").strip()
    if polo_up in ("IGUATEMI_RODOVIARIA", "IGUATEMI RODOVIARIA"):
        polo_up = "IGUATEMI"
    if polo_up not in POLOS_SALVADOR:
        return (f"Polo '{polo}' não cadastrado. Opções: {', '.join(POLOS_SALVADOR)}. "
                "Para ponto fora desta lista, usar buscar_lugares_google, que devolve o tipo "
                "do lugar, ou geocodificar_here.")

    info = POLOS_SALVADOR[polo_up]
    linhas = [f"=== {polo_up} ({info['descricao']}) ==="]
    for chave, rotulo in (("trilho", "Estação de trilho"), ("onibus", "Ponto de ônibus"),
                          ("outro", "Ponto do equipamento")):
        p = info.get(chave)
        if p:
            linhas.append(f"• {rotulo}: Lat {p['lat']}, Lon {p['lon']}  "
                          f"[{p.get('tipo') or 'tipo não declarado'}] {p.get('nome', '')}")
    if info.get("trilho") and info.get("onibus"):
        linhas.append(f"• Separação entre os dois pontos: {info['separacao_m']:.0f} m. "
                      "Escolher pelo uso: acesso de passageiro ao trilho, ou embarque no "
                      "alimentador. A escolha muda o tempo de acesso.")
    if info.get("catalogo_antigo_m"):
        linhas.append(f"• A coordenada usada até 21/10/2026 estava a "
                      f"{info['catalogo_antigo_m']:.0f} m daqui.")
    linhas.append("• Fonte: Google Places (New), tipado, conferido em 21/10/2026 contra HERE.")
    return "\n".join(linhas)

if __name__ == "__main__":
    mcp.run()