#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tomtom_network_server.py — Servidor MCP para integração TomTom API no Claude Desktop (Windows)
Foco: Modelagem de Rede Viária e Matrizes de Impedância da RMS.
"""
import os
import json
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
_INSEGURO = os.environ.get("TOMTOM_MCP_INSECURE_SSL", "0") == "1"
_VERIFICAR = not _INSEGURO
if _INSEGURO:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn("TOMTOM_MCP_INSECURE_SSL=1: verificacao de certificado TLS desativada. "
                  "Preferir REQUESTS_CA_BUNDLE com o certificado corporativo.", RuntimeWarning)

_AJUDA_TLS = ("Falha de verificacao de certificado TLS nesta maquina. Duas saidas, nessa ordem: "
              "exportar o certificado raiz corporativo e apontar REQUESTS_CA_BUNDLE para ele no "
              "bloco 'env' do servidor, ou, como paliativo, definir TOMTOM_MCP_INSECURE_SSL=1.")

mcp = FastMCP("TomTomTransportMCP")

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY", "")

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
    except requests.exceptions.SSLError:
        return _AJUDA_TLS
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
    except requests.exceptions.SSLError:
        return _AJUDA_TLS
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
    polos = {
        "LAPA": {"lat": -12.9814, "lon": -38.5108, "tipo": "Terminal Urbano / Metrô Linha 1"},
        "PIRAJÁ": {"lat": -12.9152, "lon": -38.4552, "tipo": "Terminal de Integração / Metrô Linha 1"},
        "ACESSO NORTE": {"lat": -12.9687, "lon": -38.4877, "tipo": "Terminal / Integração Linhas 1 e 2"},
        "MUSSURUNGA": {"lat": -12.9288, "lon": -38.3845, "tipo": "Terminal Urbano / Metrô Linha 2"},
        "AEROPORTO": {"lat": -12.9069, "lon": -38.3346, "tipo": "Estação Metrô Linha 2 / Lauro de Freitas"},
        "IGUATEMI_RODOVIARIA": {"lat": -12.9782, "lon": -38.4623, "tipo": "Eixo Central / Metrô Linha 2 / BRT"},
        "BARRA": {"lat": -13.0094, "lon": -38.5312, "tipo": "Polo Gerador / Bacia Orla"},
        "CALÇADA": {"lat": -12.9467, "lon": -38.5028, "tipo": "Bacia Ferroviária / Cidade Baixa"}
    }
    polo_up = polo.upper()
    if polo_up in polos:
        info = polos[polo_up]
        return f"{polo_up}: Lat {info['lat']}, Lon {info['lon']} ({info['tipo']})"

    opcoes = ", ".join(polos.keys())
    return f"Polo '{polo}' não cadastrado. Opções rápidas: {opcoes}"

if __name__ == "__main__":
    mcp.run()