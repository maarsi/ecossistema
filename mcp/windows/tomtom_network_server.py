#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tomtom_network_server.py — Servidor MCP para integração TomTom API no Claude Desktop (Windows)
Foco: Modelagem de Rede Viária e Matrizes de Impedância da RMS.
"""
import os
import json
import requests
import urllib3
from fastmcp import FastMCP

# Suprime avisos de requisições HTTPS sem verificação de certificado no log do MCP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    Calcula distancia (km), tempo em fluxo livre (min) e tempo com transito atual/historico (min)
    entre duas coordenadas da RMS (ex: Estação Lapa para Estação Aeroporto).
    """
    if not TOMTOM_KEY:
        return "Erro: Variável de ambiente TOMTOM_API_KEY não configurada."

    url = f"https://api.tomtom.com/routing/1/calculateRoute/{lat_origem},{lon_origem}:{lat_destino},{lon_destino}/json"
    
    params = {
        "key": TOMTOM_KEY,
        "traffic": "true" if considerar_transito else "false",
        "travelMode": "car",
        "routeType": "fastest"
    }

    try:
        # verify=False adicionado para contornar a falha de SSL no Windows
        r = requests.get(url, params=params, timeout=15, verify=False)
        if r.status_code != 200:
            return f"Erro na API TomTom (HTTP {r.status_code}): {r.text}"

        dados = r.json()
        sumario = dados["routes"][0]["summary"]
        
        distancia_km = sumario["lengthInMeters"] / 1000.0
        tempo_transito_min = sumario["travelTimeInSeconds"] / 60.0
        tempo_fluxo_livre_min = sumario.get("noTrafficTravelTimeInSeconds", sumario["travelTimeInSeconds"]) / 60.0
        atraso_transito_min = sumario.get("trafficDelayInSeconds", 0) / 60.0

        return (
            f"=== CONSULTA TOMTOM ROUTING ===\n"
            f"• Distância da Ligação: {distancia_km:.2f} km\n"
            f"• Tempo em Fluxo Livre (t0): {tempo_fluxo_livre_min:.1f} min\n"
            f"• Tempo com Trânsito (t_atual): {tempo_transito_min:.1f} min\n"
            f"• Atraso por Congestionamento: {atraso_transito_min:.1f} min\n"
            f"• Velocidade Média Operacional: {(distancia_km / (tempo_transito_min / 60.0)):.1f} km/h"
        )
    except Exception as e:
        return f"Erro na conexão com a TomTom: {str(e)}"

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
        # verify=False adicionado para contornar a falha de SSL no Windows
        r = requests.get(url, params=params, timeout=15, verify=False)
        if r.status_code != 200:
            return f"Erro na API TomTom Flow (HTTP {r.status_code}): {r.text}"

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
    except Exception as e:
        return f"Erro na consulta de tráfego: {str(e)}"

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