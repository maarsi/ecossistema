#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transport_server.py - Servidor MCP de Engenharia de Transportes
Modulos: Dimensionamento Operacional e Pesquisa Cientifica Filtrada (Elsevier / ScienceDirect / Crossref)
"""
import os
import sys
import ssl
import math
import warnings
import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

# ----------------------------------------------------------------------
# TLS: verificacao ATIVA por padrao.
# O bypass global anterior desativava a verificacao de certificado para todo o
# processo, nao apenas para a chamada ao Crossref. Agora e opcional e explicito.
#
# Ordem de preferencia para rede corporativa com proxy:
#   1. apontar REQUESTS_CA_BUNDLE para o certificado raiz da empresa (solucao correta)
#   2. em ultimo caso, definir TRANSPORT_MCP_INSECURE_SSL=1 (solucao paliativa)
# ----------------------------------------------------------------------
_INSEGURO = os.environ.get("TRANSPORT_MCP_INSECURE_SSL", "0") == "1"
_VERIFICAR_TLS = not _INSEGURO

if _INSEGURO:
    import urllib3
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.warn(
        "TRANSPORT_MCP_INSECURE_SSL=1: verificacao de certificado TLS desativada. "
        "Preferir REQUESTS_CA_BUNDLE com o certificado corporativo.",
        RuntimeWarning,
    )

mcp = FastMCP("TransportModelingMCP")


# ----------------------------------------------------------------------
# 1. PESQUISA CIENTIFICA EM TRANSPORTES (SCIENCEDIRECT / ELSEVIER)
# ----------------------------------------------------------------------
@mcp.tool()
def pesquisar_sciencedirect_transportes(termo: str, limite: int = 5, apenas_elsevier: bool = True) -> str:
    """
    Pesquisa artigos cientificos revisados por pares em Engenharia de Transportes.
    Por padrao filtra periodicos da Elsevier/ScienceDirect (Transportation Research,
    Transport Policy, Journal of Rail Transport, etc.) publicados a partir de 2020, via Crossref.

    Usar esta ferramenta SEMPRE que uma referencia bibliografica for citada em entregavel.
    Reproduzir apenas titulo, autores, periodico, ano e DOI retornados aqui.
    Nunca completar de memoria uma referencia que a ferramenta nao retornou.
    """
    url = "https://api.crossref.org/works"

    filtros = ["from-pub-date:2020-01-01"]
    if apenas_elsevier:
        filtros.append("prefix:10.1016")

    params = {
        "query.bibliographic": f"{termo} transport",
        "filter": ",".join(filtros),
        "rows": limite,
        "sort": "relevance",
        "order": "desc",
    }

    # Crossref "polite pool": identificar a aplicacao e um e-mail de contato REAL via CROSSREF_MAILTO.
    _mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
    headers = {
        "User-Agent": f"CitatisTransportMCP/1.1 (mailto:{_mailto})" if _mailto else "CitatisTransportMCP/1.1"
    }

    try:
        r = requests.get(url, params=params, headers=headers, verify=_VERIFICAR_TLS, timeout=15)
        if r.status_code != 200:
            return f"Erro na API Crossref (Status HTTP {r.status_code})."

        itens = r.json().get("message", {}).get("items", [])
        if not itens:
            return (f"Nenhum artigo encontrado para o termo '{termo}'. "
                    f"Nao inferir referencias: reformular o termo ou usar apenas_elsevier=False.")

        resultados = []
        for item in itens:
            titulo = item.get("title", ["Sem titulo"])[0] if item.get("title") else "Sem titulo"
            revista = item.get("container-title", ["Elsevier / ScienceDirect"])[0] if item.get("container-title") else "Elsevier / ScienceDirect"

            ano = "s/d"
            try:
                ano = item["published"]["date-parts"][0][0]
            except (KeyError, IndexError, TypeError):
                try:
                    ano = item["created"]["date-parts"][0][0]
                except (KeyError, IndexError, TypeError):
                    ano = "s/d"

            doi = item.get("DOI", "")
            link = f"https://doi.org/{doi}" if doi else item.get("URL", "")

            autores = []
            for a in item.get("author", [])[:3]:
                nome = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if nome:
                    autores.append(nome)
            nomes_autores = ", ".join(autores) if autores else "Autores diversos"

            resultados.append(
                f"- Titulo: {titulo} ({ano})\n"
                f"  Periodico: {revista}\n"
                f"  Autores: {nomes_autores}\n"
                f"  DOI: {doi}\n"
                f"  Link: {link}"
            )

        rotulo_base = "ELSEVIER / SCIENCEDIRECT (2020 em diante)" if apenas_elsevier else "PERIODICOS CIENTIFICOS DE TRANSPORTES"
        return f"=== {rotulo_base}: '{termo}' ===\n\n" + "\n\n".join(resultados)
    except Exception as e:
        return f"Erro na consulta bibliografica: {type(e).__name__}: {e}"


# ----------------------------------------------------------------------
# 2. DIMENSIONAMENTO OPERACIONAL DE SISTEMAS DE TRANSPORTE
# ----------------------------------------------------------------------
@mcp.tool()
def dimensionar_frota_operacional(
    tempo_viagem_ida_volta_min: float,
    headway_min: float,
    capacidade_veiculo: int,
    demanda_pico_passageiros_hora: int,
    reserva_tecnica_percentual: float = 10.0,
    tempo_terminal_min: float = 0.0,
    fator_carregamento_max: float = 0.85,
    fator_pico_horario: float = 1.0,
) -> str:
    """
    Calcula frota comercial e total de uma linha de transporte publico (BRT, Metro, VLT, onibus).
    Formulacao classica: N = ceil(T_ciclo / h), com T_ciclo = tempo de percurso ida e volta
    somado ao tempo de terminal (recuperacao e regulagem).

    Parametros de premissa, todos explicitados na saida:
      tempo_terminal_min ...... tempo de terminal nos dois extremos. Omiti-lo subdimensiona a frota.
      fator_carregamento_max .. ocupacao maxima admissivel do veiculo no trecho critico
                                (0,85 e valor usual de conforto; 1,0 supoe lotacao plena).
      fator_pico_horario ...... razao entre o pico de 15 min expandido e a media horaria.
                                Usar > 1,0 quando a demanda informada for media da hora.

    A capacidade ofertada e calculada sobre a capacidade efetiva do veiculo
    (nominal multiplicada pelo fator de carregamento), nao sobre a nominal.
    A saida inclui bloco de premissas a verificar antes do uso em entregavel.
    """
    try:
        if capacidade_veiculo <= 0 or headway_min <= 0:
            return "Erro: capacidade do veiculo e headway devem ser estritamente positivos."
        if tempo_viagem_ida_volta_min <= 0:
            return "Erro: tempo de viagem ida e volta deve ser estritamente positivo."
        if not (0 < fator_carregamento_max <= 1.0):
            return "Erro: fator de carregamento deve estar no intervalo (0, 1]."
        if fator_pico_horario <= 0:
            return "Erro: fator de pico horario deve ser estritamente positivo."
        if tempo_terminal_min < 0 or reserva_tecnica_percentual < 0:
            return "Erro: tempo de terminal e reserva tecnica nao podem ser negativos."

        capacidade_efetiva = capacidade_veiculo * fator_carregamento_max
        demanda_dimensionante = demanda_pico_passageiros_hora * fator_pico_horario

        freq_demanda = demanda_dimensionante / capacidade_efetiva
        headway_demanda = 60.0 / freq_demanda if freq_demanda > 0 else headway_min

        # Adota-se o headway mais restritivo entre a politica de servico e a demanda
        headway_operacional = min(headway_min, headway_demanda)
        restricao = "demanda" if headway_demanda < headway_min else "politica de servico"

        tempo_ciclo = tempo_viagem_ida_volta_min + tempo_terminal_min

        frota_operacao = math.ceil(tempo_ciclo / headway_operacional)
        frota_reserva = math.ceil(frota_operacao * (reserva_tecnica_percentual / 100.0))
        frota_total = frota_operacao + frota_reserva

        freq_operacional = 60.0 / headway_operacional
        capacidade_ofertada_efetiva = freq_operacional * capacidade_efetiva
        capacidade_ofertada_nominal = freq_operacional * capacidade_veiculo
        folga = ((capacidade_ofertada_efetiva / demanda_dimensionante - 1.0) * 100.0
                 if demanda_dimensionante > 0 else float("nan"))
        if folga == folga and abs(folga) < 0.05:  # elimina "-0.0%" por erro de ponto flutuante
            folga = 0.0

        linhas = [
            "=== DIMENSIONAMENTO OPERACIONAL ===",
            f"- Headway adotado: {headway_operacional:.2f} min ({int(round(headway_operacional * 60))} s) | restricao ativa: {restricao}",
            f"- Frequencia: {freq_operacional:.2f} veic/h/sentido",
            f"- Tempo de ciclo: {tempo_ciclo:.1f} min (percurso {tempo_viagem_ida_volta_min:.1f} + terminal {tempo_terminal_min:.1f})",
            f"- Capacidade efetiva por veiculo: {capacidade_efetiva:.0f} pass (nominal {capacidade_veiculo} x FC {fator_carregamento_max:.2f})",
            f"- Capacidade ofertada: {capacidade_ofertada_efetiva:.0f} pass/h/sentido (nominal {capacidade_ofertada_nominal:.0f})",
            f"- Demanda dimensionante: {demanda_dimensionante:.0f} pass/h (informada {demanda_pico_passageiros_hora} x FPH {fator_pico_horario:.2f})",
            f"- Folga sobre a demanda: {folga:.1f}%",
            f"- Frota em operacao comercial: {frota_operacao} veiculos",
            f"- Reserva tecnica ({reserva_tecnica_percentual:.0f}%): {frota_reserva} veiculos",
            f"- FROTA TOTAL: {frota_total} veiculos",
            "",
            "=== PREMISSAS A VERIFICAR ANTES DE LEVAR AO ENTREGAVEL ===",
        ]

        alertas = []
        if headway_operacional < 1.0:
            alertas.append(
                f"CRITICO: headway resultante de {headway_operacional * 60:.0f} s. A formulacao classica nao "
                "impoe headway tecnico minimo, mas operacao de superficie dificilmente sustenta valores abaixo de "
                "60 a 90 s por estacao sem ultrapassagem e sem bunching severo. Reavaliar: veiculo de maior "
                "capacidade, servicos expressos sobrepostos, estacao com baia de ultrapassagem ou revisao da demanda."
            )
        if tempo_terminal_min == 0.0:
            alertas.append("Tempo de terminal igual a zero: o ciclo esta sem recuperacao e regulagem. "
                           "Valores usuais ficam entre 10% e 20% do tempo de percurso. Frota provavelmente subdimensionada.")
        if fator_carregamento_max >= 0.99:
            alertas.append("Fator de carregamento em lotacao plena: supoe distribuicao perfeita de passageiros "
                           "entre veiculos e ausencia de bunching. Irrealista em operacao.")
        if fator_pico_horario == 1.0:
            alertas.append("Fator de pico horario igual a 1,0: verificar se a demanda informada e do pico de 15 min "
                           "expandido ou media da hora. Se for media, a frota esta subdimensionada.")
        alertas.append("A demanda informada e do trecho critico (secao de maior carregamento)? "
                       "Dimensionar pelo total da linha subestima a frota.")
        alertas.append("Taxa de renovacao de passageiros nao considerada: havendo renovacao relevante ao longo "
                       "do percurso, a capacidade necessaria no trecho critico pode diferir da calculada.")
        alertas.append("O tempo de percurso adotado corresponde a qual periodo? Ciclo de pico e de entrepico "
                       "diferem, e a frota deve ser dimensionada pelo pico.")

        for i, a in enumerate(alertas, 1):
            linhas.append(f"{i}. {a}")

        return "\n".join(linhas)
    except Exception as e:
        return f"Erro no calculo operacional: {type(e).__name__}: {e}"


def _main() -> None:
    """Uso:
         python transport_server.py              -> stdio (Claude Desktop, Windows)
         python transport_server.py sse 8000     -> servidor SSE na porta 8000 (daemon Linux)
         python transport_server.py http 8000    -> servidor HTTP (streamable) na porta 8000
    A versao anterior ignorava os argumentos e subia sempre em stdio; sob o systemd (sem stdin)
    encerrava imediatamente e o servico entrava em loop de reinicio.
    """
    modo = (sys.argv[1] if len(sys.argv) > 1 else "stdio").lower()
    porta = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    host = os.environ.get("MCP_BIND_HOST", "0.0.0.0")
    if modo == "stdio":
        mcp.run()
        return
    transporte = "sse" if modo == "sse" else "streamable-http"
    try:
        # fastmcp (jlowin) >= 2: aceita host/port diretamente
        mcp.run(transport=transporte, host=host, port=porta)
    except TypeError:
        # mcp.server.fastmcp (SDK oficial): host/port ficam em settings
        mcp.settings.host = host
        mcp.settings.port = porta
        mcp.run(transport=transporte)


if __name__ == "__main__":
    _main()
