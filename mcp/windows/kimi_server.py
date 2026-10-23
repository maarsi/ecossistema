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

# Medido em 21/10/2026 contra /v1/models com a chave nova: a conta enxerga
# kimi-k2.6, kimi-k2.7-code, kimi-k2.7-code-highspeed e kimi-k3. A familia
# moonshot-v1-* NAO existe mais e devolve 404 "Not found the model ... or
# Permission denied", o que mantinha este servidor parado independentemente
# da chave.
MODELO_PADRAO = os.environ.get("MOONSHOT_MODELO", "kimi-k3")

# O kimi-k3 recusa temperatura diferente de 1 ("invalid temperature: only 1 is
# allowed for this model"), por ser modelo de raciocinio. Para ele o campo e
# omitido e vale o padrao da API; os demais seguem com 0.3.
MODELOS_SEM_TEMPERATURA = ("kimi-k3",)

# Sem chave o servidor SOBE mesmo assim: encerrar no import (sys.exit) fazia o Claude Desktop
# marcar o servidor inteiro como falho, sem explicar o motivo. Agora cada ferramenta devolve
# a mensagem de erro e o restante do ambiente segue operacional.
_ERRO_SEM_CHAVE = (
    "Erro: variavel de ambiente MOONSHOT_API_KEY nao definida. Configure-a no bloco 'env' do "
    "servidor kimi-assistant em claude_desktop_config.json e reinicie o Claude Desktop."
)
if not KIMI_API_KEY:
    print("AVISO: MOONSHOT_API_KEY ausente; as ferramentas do Kimi retornarao erro ate a chave ser definida.", file=sys.stderr)

# Contexto declarado pela propria API em 23/10/2026 (GET /v1/models, campo context_length).
# Nao e suposicao nem leitura de documentacao: veio da conta que esta chave alcanca. A familia k3
# tem o MESMO contexto do gemini-4-argon, um milhao de tokens, e quatro vezes o doc-longo local.
CTX_MAX_POR_MODELO = {
    "kimi-k3": 1048576,
    "kimi-k3.1-pro": 1048576,
    "kimi-k3.1-pro-highspeed": 1048576,
    "kimi-k2.6": 262144,
    "kimi-k2.7-code": 262144,
    "kimi-k2.7-code-highspeed": 262144,
}
CHARS_POR_TOKEN = 2.5  # estimativa pessimista, a mesma de bin/llm.py

# Esforco de raciocinio. MEDIDO em 23/10/2026, quatro repeticoes de cada: low leva 4,2 s e gera
# 112 caracteres de raciocinio; max leva 10,9 s e gera 1.748. Intervalos sem sobreposicao, logo o
# parametro e honrado. MAS a API NAO valida o valor: valor invalido, e mesmo nome de parametro
# inventado, voltam HTTP 200 em silencio e cobram o padrao, que e max. Por isso a validacao e
# feita aqui: o remoto nao reclama, e um erro de digitacao custaria 2,6 vezes o tempo sem aviso.
ESFORCOS_VALIDOS = ("low", "high", "max")

mcp = FastMCP("KimiAssistant")


def _conferir_saida(nao_sigiloso: bool, conteudo: str, esforco: str, modelo: str) -> str:
    """As DUAS travas que o gateway bin/llm.py aplica e que faltavam neste caminho.

    Ate 23/10/2026 o Kimi era alcancavel apenas por aqui, fora do gateway. A advertencia sobre
    dado de cliente existia em DOCSTRING, e docstring e aviso, nao trava. E nao havia conferencia
    de orcamento de contexto, justamente num servidor cujo nicho declarado e documento extenso,
    que e o pior lugar possivel para essa trava faltar.

    Devolve string vazia quando pode seguir, ou o texto da recusa."""
    if nao_sigiloso is not True:
        return (
            "RECUSADO: esta ferramenta envia o conteudo para a Moonshot, FORA da workstation. "
            "Exige nao_sigiloso=True explicito.\n"
            "Nao usar com dado de cliente, pesquisa bruta ou material sob NDA: nesses casos "
            "processar na Ubuntu e devolver apenas agregado, estatistica ou conclusao. Para "
            "analisar METODO sobre material sigiloso, substituir o dado por sintetico ou "
            "agregado e enviar so a formulacao."
        )
    if esforco and esforco not in ESFORCOS_VALIDOS:
        return (f"RECUSADO: esforco '{esforco}' invalido. Validos: "
                f"{', '.join(ESFORCOS_VALIDOS)}. A API aceitaria esse valor SEM reclamar e "
                f"cobraria o esforco padrao (max), medido em 2,6 vezes o tempo do 'low', por "
                f"isso a recusa e local.")
    mod = modelo or MODELO_PADRAO
    teto = CTX_MAX_POR_MODELO.get(mod)
    if teto:
        est = int(len(conteudo) / CHARS_POR_TOKEN) + 1
        if est > teto:
            return (f"RECUSADO: insumo de ~{est} tokens (estimativa pessimista de "
                    f"{CHARS_POR_TOKEN} caracteres por token) excede o contexto de {teto} do "
                    f"modelo {mod}. Recusado em vez de truncado: corte silencioso devolve "
                    f"resposta plausivel e INCOMPLETA, que e o pior defeito possivel numa "
                    f"analise de documento. Dividir o material e analisar por partes.")
    return ""


def _chamar_api_kimi(mensagens: list, modelo: str = "", esforco: str = "") -> str:
    """Envia requisicoes para a API oficial da Moonshot AI com suporte a janelas longas de contexto."""
    if not KIMI_API_KEY:
        return _ERRO_SEM_CHAVE
    modelo = modelo or MODELO_PADRAO
    headers = {
        "Authorization": f"Bearer {KIMI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": modelo,
        "messages": mensagens,
    }
    if not modelo.startswith(MODELOS_SEM_TEMPERATURA):
        payload["temperature"] = 0.3
    if esforco in ESFORCOS_VALIDOS:
        payload["reasoning_effort"] = esforco
    try:
        r = requests.post(KIMI_API_URL, headers=headers, json=payload, timeout=180)
        try:
            dados = r.json()
        except Exception:
            return f"Erro Kimi (Status HTTP {r.status_code}): resposta nao-JSON retornada pelo gateway."

        if r.status_code == 200:
            escolha = dados["choices"][0]
            texto = (escolha.get("message", {}).get("content") or "").strip()
            if texto:
                return texto
            # Acontece com modelo de raciocinio quando o limite de saida e
            # consumido antes de sair texto. Devolver aviso, nao string vazia.
            return (f"O Kimi respondeu sem texto (HTTP 200, modelo {modelo}, "
                    f"finish_reason={escolha.get('finish_reason', 'desconhecido')}). "
                    "Em modelo de raciocinio como o kimi-k3 isso indica orcamento de saida "
                    "consumido no raciocinio: repetir com pergunta mais direta ou usar "
                    "modelo='kimi-k2.6'.")

        msg_erro = dados.get("error", {}).get("message", "")
        extra = ""
        if r.status_code == 404:
            extra = (" Conferir o nome do modelo: a familia moonshot-v1-* foi desativada. "
                     "Conferido em 23/10/2026, a conta enxerga kimi-k2.6, kimi-k2.7-code, "
                     "kimi-k2.7-code-highspeed, kimi-k3, kimi-k3.1-pro e "
                     "kimi-k3.1-pro-highspeed. O catalogo mudou em dois dias: os dois ultimos "
                     "nao existiam em 21/10, entao listar pela API antes de fixar nome.")
        elif r.status_code == 401:
            extra = " Problema de chave, nao de requisicao: conferir MOONSHOT_API_KEY."
        # Nao propagar r.text bruto: pode conter eco de cabecalhos ou credenciais
        return f"Erro Kimi ({r.status_code}): {msg_erro or 'falha reportada pelo gateway'}.{extra}"
    except Exception as e:
        return f"Falha na requisicao ao Kimi: {type(e).__name__}"


@mcp.tool()
def consultar_kimi(pergunta: str, nao_sigiloso: bool = False,
                   modelo: str = "", esforco: str = "") -> str:
    """Envia uma pergunta tecnica direta para a IA Kimi (Moonshot AI).

    Uso recomendado: documentos ou bases muito extensas que excedam a janela util
    dos modelos locais do Ubuntu. Para raciocinio metodologico, derivacao de
    formulacao ou decisao tecnica, nao delegar.

    Modelos disponiveis na conta (conferido em 21/10/2026): 'kimi-k3' (padrao,
    raciocinio, mais lento, temperatura travada em 1), 'kimi-k2.6' (uso geral,
    mais rapido), 'kimi-k2.7-code' e 'kimi-k2.7-code-highspeed' (codigo).
    A familia 'moonshot-v1-*' foi desativada.
    """
    recusa = _conferir_saida(nao_sigiloso, pergunta, esforco, modelo)
    if recusa:
        return recusa
    mensagens = [
        {
            "role": "system",
            "content": "Voce e um assistente tecnico especialista em engenharia de transportes e analise de dados.",
        },
        {"role": "user", "content": pergunta},
    ]
    return _chamar_api_kimi(mensagens, modelo=modelo, esforco=esforco)


@mcp.tool()
def analisar_documento_com_kimi(
    texto_documento: str, instrucao_de_analise: str, nao_sigiloso: bool = False,
    modelo: str = "", esforco: str = ""
) -> str:
    """Envia documentos extensos, editais ou dados para analise critica pelo Kimi.

    Padrao 'kimi-k3' (raciocinio). Para documento muito longo em que a latencia
    pese, usar modelo='kimi-k2.6'.

    ATENCAO: esta ferramenta envia o conteudo para um servico externo.
    Nao usar com dados de cliente, pesquisa bruta ou material sob NDA;
    nesses casos processar localmente no Ubuntu.
    """
    recusa = _conferir_saida(nao_sigiloso, texto_documento, esforco, modelo)
    if recusa:
        return recusa
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
    return _chamar_api_kimi(mensagens, modelo=modelo, esforco=esforco)


if __name__ == "__main__":
    mcp.run()
