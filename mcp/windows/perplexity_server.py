#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
perplexity_server.py - Servidor MCP da Perplexity (Agent API)

Substitui o pacote npm `perplexity-mcp`, que parou por dois motivos somados,
medidos em 21/10/2026:

  1. TLS: o servidor em Node falhava com "unable to verify the first
     certificate" antes de chegar a API. Os servidores Python desta mesma
     maquina fazem HTTPS sem problema (o transport_server consulta o Crossref),
     porque usam o conjunto de certificados do Python, nao o do Node.
  2. API: o caminho `POST /chat/completions` com o modelo `sonar` foi
     desativado e responde 403 com aviso de migracao. O caminho atual e
     `POST /v1/agent` (`/v1/responses` e apelido compativel com a OpenAI).

A chave NUNCA fica no codigo: vem do bloco "env" do servidor perplexity em
claude_desktop_config.json, na variavel PERPLEXITY_API_KEY.
"""
import os
import sys
import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

CHAVE = os.environ.get("PERPLEXITY_API_KEY")
ENDPOINT = "https://api.perplexity.ai/v1/agent"
PRESET_PADRAO = os.environ.get("PERPLEXITY_PRESET", "low")

# Sem chave o servidor SOBE mesmo assim: encerrar no import fazia o Claude
# Desktop marcar o servidor como falho sem explicar o motivo. Mesma convencao
# do kimi_server.py.
_ERRO_SEM_CHAVE = (
    "Erro: variavel de ambiente PERPLEXITY_API_KEY nao definida. Configure-a no bloco 'env' "
    "do servidor perplexity em claude_desktop_config.json e reinicie o Claude Desktop."
)
if not CHAVE:
    print("AVISO: PERPLEXITY_API_KEY ausente; as ferramentas da Perplexity retornarao erro "
          "ate a chave ser definida.", file=sys.stderr)

mcp = FastMCP("PerplexityAgent")


def _chamar_agente(pergunta: str, preset: str, modelo: str, max_fontes: int,
                   tempo_limite: int = 180) -> dict:
    """Uma chamada ao Agent API. Devolve dict com texto, fontes e citacoes, ou erro."""
    if not CHAVE:
        return {"erro": _ERRO_SEM_CHAVE}

    corpo = {"input": pergunta, "tools": [{"type": "web_search"}]}
    if modelo:
        # model e preset sao mutuamente exclusivos na API.
        corpo["model"] = modelo
        if modelo.startswith("anthropic/"):
            corpo["max_output_tokens"] = 4096      # exigido para modelos anthropic/*
    else:
        corpo["preset"] = preset or PRESET_PADRAO

    try:
        r = requests.post(ENDPOINT, json=corpo, timeout=tempo_limite,
                          headers={"Authorization": f"Bearer {CHAVE}",
                                   "Content-Type": "application/json"})
    except Exception as e:
        return {"erro": f"Falha na requisicao a Perplexity: {type(e).__name__}"}

    try:
        dados = r.json()
    except Exception:
        return {"erro": f"Erro Perplexity (HTTP {r.status_code}): resposta nao-JSON."}

    if r.status_code != 200:
        # Nao propagar o corpo bruto: pode ecoar cabecalhos.
        msg = (dados.get("error") or {}).get("message", "") if isinstance(dados, dict) else ""
        extra = ""
        if r.status_code == 401:
            extra = " Isso e problema de chave, nao de requisicao: conferir PERPLEXITY_API_KEY."
        elif r.status_code == 429:
            extra = " Limite de requisicoes: respeitar o Retry-After e repetir depois."
        return {"erro": f"Erro Perplexity ({r.status_code}): {msg or 'falha reportada pelo gateway'}.{extra}"}

    # Extracao conforme a referencia da API: percorrer output, pegar itens
    # type=message e, no content, as partes type=output_text.
    textos, citacoes, fontes = [], [], []
    for item in dados.get("output", []) or []:
        tipo = item.get("type")
        if tipo == "message":
            for parte in item.get("content", []) or []:
                if parte.get("type") == "output_text":
                    textos.append(parte.get("text", ""))
                    for a in parte.get("annotations", []) or []:
                        if a.get("type") == "url_citation" and a.get("url"):
                            citacoes.append((a.get("title") or a["url"], a["url"]))
        elif tipo == "search_results":
            for res in item.get("results", []) or []:
                fontes.append({"titulo": res.get("title") or "", "url": res.get("url") or "",
                               "fonte": res.get("source") or "", "data": res.get("date") or "",
                               "trecho": (res.get("snippet") or "")[:300]})

    uso = dados.get("usage") or {}
    return {
        "texto": "\n".join(t for t in textos if t).strip(),
        "citacoes": citacoes,
        "fontes": fontes[:max_fontes],
        "modelo": dados.get("model", ""),
        "preset": dados.get("preset", ""),
        "custo_usd": (uso.get("cost") or {}).get("total_cost"),
        "tokens": uso.get("total_tokens"),
        "id_resposta": dados.get("id", ""),
    }


def _rodape(d: dict) -> str:
    partes = []
    if d.get("modelo"):
        partes.append("modelo " + str(d["modelo"]))
    if d.get("preset"):
        partes.append("preset " + str(d["preset"]))
    if d.get("tokens"):
        partes.append("%s tokens" % d["tokens"])
    if d.get("custo_usd") is not None:
        partes.append("custo US$ %.4f" % float(d["custo_usd"]))
    return " | ".join(partes)


@mcp.tool()
def consultar_perplexity(pergunta: str, preset: str = "", modelo: str = "") -> str:
    """Resposta ancorada em busca web, com as fontes citadas, pela Perplexity.

    USAR quando a resposta depende de informacao externa e atual: norma vigente,
    status de licitacao, indice, preco, catalogo de fornecedor, noticia setorial.
    Conferir sempre a fonte antes de levar o numero a entregavel: a ferramenta
    devolve os links justamente para isso.

    NAO USAR para derivacao de formulacao, escolha metodologica, critica de
    premissa ou redacao tecnica, que se resolvem sem busca. Para bibliografia
    revisada por pares, preferir pesquisar_sciencedirect_transportes, que
    devolve DOI.

    ATENCAO: a pergunta e enviada a um servico externo. Nao incluir dado de
    cliente, pesquisa bruta nem material sob NDA.

    preset: 'low' (padrao) ou 'fast'. Alternativamente informar 'modelo' no
    formato provedor/modelo, por exemplo 'openai/gpt-5.6-terra'. Os dois campos
    sao mutuamente exclusivos na API; informando modelo, o preset e ignorado.
    """
    d = _chamar_agente(pergunta, preset, modelo, max_fontes=10)
    if d.get("erro"):
        return d["erro"]
    if not d["texto"]:
        return ("A Perplexity respondeu sem texto (HTTP 200). Pode ter esgotado o orcamento de "
                "saida em raciocinio. Repetir com preset 'fast' ou reformular a pergunta. "
                + _rodape(d))

    linhas = [d["texto"]]
    vistos, fontes = set(), []
    for titulo, url in d["citacoes"]:
        if url not in vistos:
            vistos.add(url)
            fontes.append((titulo, url))
    for f in d["fontes"]:
        if f["url"] and f["url"] not in vistos:
            vistos.add(f["url"])
            fontes.append((f["titulo"] or f["url"], f["url"]))
    if fontes:
        linhas.append("\nFontes:")
        linhas += ["- [%s](%s)" % (t, u) for t, u in fontes]
    linhas.append("\n(" + _rodape(d) + ")")
    return "\n".join(linhas)


@mcp.tool()
def buscar_fontes_perplexity(consulta: str, max_fontes: int = 10, preset: str = "") -> str:
    """Lista fontes web sobre um tema, com titulo, dominio, data e trecho.

    Serve para levantar material antes de ler: documento oficial, pagina de
    orgao, relatorio, manual. Reproduzir apenas o que vier aqui; nunca
    completar de memoria titulo, autor, orgao ou data de uma fonte que a
    ferramenta nao devolveu.

    Para artigo cientifico com DOI, usar pesquisar_sciencedirect_transportes.
    ATENCAO: a consulta vai para um servico externo; nao incluir dado sigiloso.
    """
    pedido = ("Liste as fontes mais relevantes e atuais sobre: " + consulta +
              ". Responda em uma frase e deixe as fontes para a lista de resultados.")
    d = _chamar_agente(pedido, preset, "", max_fontes=max(1, min(int(max_fontes), 25)))
    if d.get("erro"):
        return d["erro"]
    if not d["fontes"] and not d["citacoes"]:
        return ("Nenhuma fonte retornada para '%s'. Reformular a consulta com termos mais "
                "especificos. %s" % (consulta, _rodape(d)))

    linhas = ["=== FONTES: '%s' ===" % consulta]
    if d["texto"]:
        linhas.append(d["texto"] + "\n")
    for i, f in enumerate(d["fontes"], 1):
        linhas.append("%d. %s" % (i, f["titulo"] or f["url"]))
        meta = " | ".join(x for x in (f["fonte"], f["data"]) if x)
        if meta:
            linhas.append("   " + meta)
        linhas.append("   " + f["url"])
        if f["trecho"]:
            linhas.append("   " + f["trecho"])
    if not d["fontes"]:
        linhas += ["- [%s](%s)" % (t, u) for t, u in d["citacoes"]]
    linhas.append("\n(" + _rodape(d) + ")")
    return "\n".join(linhas)


if __name__ == "__main__":
    mcp.run()
