import os
import sys
import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

# A chave NUNCA fica no codigo. Vem exclusivamente do ambiente definido
# no claude_desktop_config.json (bloco "env" do servidor kimi-assistant)
# ou de uma variavel de ambiente do sistema.
KIMI_API_KEY = os.environ.get("MOONSHOT_API_KEY")
KIMI_API_URL = "https://api.moonshot.ai/v1/chat/completions"

# Sem chave o servidor SOBE mesmo assim: encerrar no import (sys.exit) fazia o Claude Desktop
# marcar o servidor inteiro como falho, sem explicar o motivo. Agora cada ferramenta devolve
# a mensagem de erro e o restante do ambiente segue operacional.
_ERRO_SEM_CHAVE = (
    "Erro: variavel de ambiente MOONSHOT_API_KEY nao definida. Configure-a no bloco 'env' do "
    "servidor kimi-assistant em claude_desktop_config.json e reinicie o Claude Desktop."
)
if not KIMI_API_KEY:
    print("AVISO: MOONSHOT_API_KEY ausente; as ferramentas do Kimi retornarao erro ate a chave ser definida.", file=sys.stderr)

mcp = FastMCP("KimiAssistant")


def _chamar_api_kimi(mensagens: list, modelo: str = "moonshot-v1-128k") -> str:
    """Envia requisicoes para a API oficial da Moonshot AI com suporte a janelas longas de contexto."""
    if not KIMI_API_KEY:
        return _ERRO_SEM_CHAVE
    headers = {
        "Authorization": f"Bearer {KIMI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": modelo,
        "messages": mensagens,
        "temperature": 0.3,
    }
    try:
        r = requests.post(KIMI_API_URL, headers=headers, json=payload, timeout=180)
        try:
            dados = r.json()
        except Exception:
            return f"Erro Kimi (Status HTTP {r.status_code}): resposta nao-JSON retornada pelo gateway."

        if r.status_code == 200:
            return dados["choices"][0]["message"]["content"]

        msg_erro = dados.get("error", {}).get("message", "")
        # Nao propagar r.text bruto: pode conter eco de cabecalhos ou credenciais
        return f"Erro Kimi ({r.status_code}): {msg_erro or 'falha reportada pelo gateway'}"
    except Exception as e:
        return f"Falha na requisicao ao Kimi: {type(e).__name__}"


@mcp.tool()
def consultar_kimi(pergunta: str, modelo: str = "moonshot-v1-128k") -> str:
    """Envia uma pergunta tecnica direta para a IA Kimi (Moonshot AI).

    Uso recomendado: documentos ou bases muito extensas que excedam a janela util
    dos modelos locais do Ubuntu. Para raciocinio metodologico, derivacao de
    formulacao ou decisao tecnica, nao delegar.
    Modelos: 'moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k', 'moonshot-v1-auto'.
    """
    mensagens = [
        {
            "role": "system",
            "content": "Voce e um assistente tecnico especialista em engenharia de transportes e analise de dados.",
        },
        {"role": "user", "content": pergunta},
    ]
    return _chamar_api_kimi(mensagens, modelo=modelo)


@mcp.tool()
def analisar_documento_com_kimi(
    texto_documento: str, instrucao_de_analise: str, modelo: str = "moonshot-v1-128k"
) -> str:
    """Envia documentos extensos, editais ou dados para analise critica pelo Kimi (janela de ate 128k tokens).

    ATENCAO: esta ferramenta envia o conteudo para um servico externo.
    Nao usar com dados de cliente, pesquisa bruta ou material sob NDA;
    nesses casos processar localmente no Ubuntu.
    """
    mensagens = [
        {
            "role": "system",
            "content": "Voce e um auditor senior de engenharia de transportes encarregado de analise critica de documentos tecnicos e termos de referencia.",
        },
        {
            "role": "user",
            "content": f"INSTRUCAO:\n{instrucao_de_analise}\n\nCONTEUDO:\n{texto_documento}",
        },
    ]
    return _chamar_api_kimi(mensagens, modelo=modelo)


if __name__ == "__main__":
    mcp.run()
