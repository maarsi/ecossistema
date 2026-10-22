#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
argon_mcp.py - Servidor MCP do Argon (Gemini) como auditor metodologico

Expoe tres ferramentas para uso ANTES de fechar entregavel tecnico, rodar job critico ou
concluir calculo relevante:

  argon_auditar_metodologia  segunda opiniao sobre premissa e metodo
  argon_fiscalizar_codigo    segunda opiniao sobre rotina, com caso concreto por defeito
  argon_prova_independente   rotina de recalculo escrita pelo Argon, para rodar na Ubuntu

FONTE UNICA DA LOGICA. Este arquivo nao reimplementa nada: toda a regra de auditoria (prompts,
censura de credencial, recusa em vez de truncar, exigencia de material nao sigiloso) vive em
~/ecossistema/bin/argon_core.py na Ubuntu, espelhado nesta maquina por Syncthing. O caminho
completo desse arquivo vem da variavel de ambiente ARGON_CORE, declarada no bloco "env" do
servidor argon-auditor em claude_desktop_config.json. Sem ela, as ferramentas RECUSAM e dizem o
que falta: nao existe copia local dos prompts, porque prompt de auditoria duplicado em duas
maquinas vira dois criterios diferentes sem ninguem perceber. O servidor sobe de qualquer forma,
para que a propria ferramenta de diagnostico possa informar o problema; servidor que nao sobe
desaparece da lista e nao explica nada.

POR QUE A PROVA REAL NAO EXECUTA AQUI. Codigo escrito por modelo de linguagem nao roda na estacao
de trabalho. argon_prova_independente devolve a rotina e a instrucao de execucao; quem executa,
em ambiente isolado, e a Ubuntu, por bin/llm.py --papel auditor-argon --prova ou por
executar_python_ubuntu. Enquanto nao executada, a rotina e insumo de conferencia, nao prova, e o
retorno diz isso de forma explicita.

FRONTEIRA DE DADOS. O Argon e modelo de NUVEM: o conteudo sai da workstation e sai desta maquina.
Toda ferramenta exige nao_sigiloso=True explicito. Para auditar metodo sobre material sigiloso,
substituir o dado por sintetico ou agregado e enviar apenas a formulacao e a rotina.

A CHAVE NUNCA FICA NO CODIGO: vem do bloco "env" deste servidor, na variavel GEMINI_API_KEY.
Nenhuma mensagem de erro daqui sai sem passar pela censura de argon_core.censurar().
"""
import importlib.util
import os
import sys
import traceback

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

# TLS: verificacao ATIVA. O repositorio de certificados do Windows busca o intermediario que
# falta pela extensao AIA do proprio certificado, o que o conjunto estatico do certifi nao faz.
# Foi o que resolveu, em 21/10/2026, a falha intermitente de 'unable to get local issuer
# certificate' nos nos de CDN que nao enviam a cadeia completa.
_TRUSTSTORE = False
try:
    import truststore
    truststore.inject_into_ssl()
    _TRUSTSTORE = True
except Exception:
    pass

mcp = FastMCP("ArgonAuditorMCP")

AVISO_SIGILO = (
    "RECUSADO: o Argon e modelo de NUVEM e o conteudo sai desta maquina. Exige nao_sigiloso=True "
    "explicito.\nNao usar com dado de cliente, pesquisa bruta ou material sob NDA. Para auditar o "
    "METODO sobre material sigiloso, substituir o dado por sintetico ou agregado e enviar apenas "
    "a formulacao e a rotina."
)

RODAPE_SEGUNDA_OPINIAO = (
    "\n\n---\nNATUREZA DESTE PARECER: segunda opiniao de outro modelo, NAO verificacao "
    "independente. O parecer nao confere nenhum numero: ele le o que foi enviado. Defeito "
    "apontado aqui so vale depois de reproduzido com o caso concreto indicado. Para conferir "
    "numero, usar argon_prova_independente e executar a rotina na Ubuntu."
)


def _carregar_nucleo():
    """Importa bin/argon_core.py pelo caminho declarado em ARGON_CORE. Devolve (modulo, erro)."""
    caminho = os.environ.get("ARGON_CORE", "").strip().strip('"')
    if not caminho:
        return None, (
            "variavel de ambiente ARGON_CORE nao definida. Ela deve conter o caminho COMPLETO de "
            "argon_core.py nesta maquina (a copia que o Syncthing mantem da pasta ecossistema da "
            "Ubuntu), declarada no bloco \"env\" do servidor argon-auditor em "
            "claude_desktop_config.json. Nao existe copia local dos prompts de auditoria de "
            "proposito: a fonte e unica, na Ubuntu.")
    if not os.path.isfile(caminho):
        return None, f"ARGON_CORE aponta para {caminho}, que nao existe nesta maquina."
    try:
        spec = importlib.util.spec_from_file_location("argon_core", caminho)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, ""
    except Exception as e:
        return None, f"falha ao importar {caminho}: {type(e).__name__}: {e}"


def _censurar_cru(texto):
    """Censura de emergencia, para o caso em que o proprio nucleo nao carregou e portanto a
    funcao boa nao esta disponivel."""
    import re
    s = str(texto)
    s = re.sub(r"(?i)(\bkey=)[^&\s'\"]+", r"\1<chave_censurada>", s)
    s = re.sub(r"\bAIza[0-9A-Za-z_\-]{10,}", "<chave_censurada>", s)
    chave = os.environ.get("GEMINI_API_KEY", "")
    if chave and len(chave) >= 8:
        s = s.replace(chave, "<chave_censurada>")
    return s


def _executar(funcao, *args, **kwargs):
    """Chama o nucleo e devolve texto. Toda excecao sai censurada, inclusive o traceback."""
    nucleo, erro = _carregar_nucleo()
    if nucleo is None:
        return f"ERRO DE INSTALACAO: {erro}"
    try:
        return funcao(nucleo, *args, **kwargs)
    except Exception as e:
        bruto = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
        try:
            return "ERRO: " + nucleo.censurar(bruto)
        except Exception:
            return "ERRO: " + _censurar_cru(bruto)


def _rodape_uso(r):
    return (f"\n\n[argon] modelo={r.get('modelo')} tokens_in={r.get('tokens_in')} "
            f"tokens_out={r.get('tokens_out')} t={r.get('segundos')}s "
            f"contagem_entrada={r.get('tokens_entrada_conferidos')} ({r.get('origem_contagem')})")


@mcp.tool()
def argon_auditar_metodologia(material: str, nao_sigiloso: bool = False, foco: str = "") -> str:
    """Submete METODO ao Argon para leitura critica: premissa fragil, o que a invalidaria,
    alternativa defensavel e impacto no resultado. De 3 a 5 pontos, do mais grave ao menos grave.

    Usar antes de fechar capitulo de metodologia, projecao de demanda, calibracao, dimensionamento
    operacional, avaliacao economico-financeira, desenho de pesquisa ou definicao de cenarios.

    SEM RESSALVA e resposta valida e aparece na primeira linha quando o material se sustenta: o
    prompt diz isso ao Argon de proposito, porque auditor que nunca aprova nada nao informa nada.

    Enviar o material SEM a sua conclusao, para a leitura dele nao se ancorar nela.

    material: formulacao, premissas, metodo e dados de entrada, em texto.
    nao_sigiloso: obrigatoriamente True, declarando que o material pode sair desta maquina.
    foco: opcional, aspecto a priorizar (por exemplo "elasticidade e valor do tempo").
    """
    if nao_sigiloso is not True:
        return AVISO_SIGILO
    if not material.strip():
        return "ERRO: material vazio. Nao ha o que auditar, e material vazio nao e aprovacao."

    def alvo(nucleo):
        r = nucleo.auditar_metodologia(material, foco=foco, nao_sigiloso=True)
        cabeca = ("VEREDITO: SEM RESSALVA\n\n" if r.get("aprovado_sem_ressalva") else
                  "VEREDITO: COM RESSALVAS\n\n")
        return cabeca + r["texto"] + RODAPE_SEGUNDA_OPINIAO + _rodape_uso(r)

    return _executar(alvo)


@mcp.tool()
def argon_fiscalizar_codigo(codigo: str, nao_sigiloso: bool = False, contexto: str = "") -> str:
    """Submete CODIGO ao Argon para fiscalizacao. Para cada defeito ele deve dar o trecho, o
    defeito em uma frase, UM caso concreto de entrada que o faz errar e a correcao.

    Prioridade do prompt: resultado numerico errado; unidade, fator de conversao e sistema de
    coordenadas; valor ausente tratado como zero; condicao de contorno e divisao por zero;
    agregacao que soma o que nao se soma; fuso e virada de meia-noite em GTFS e em pesquisa de
    campo; e so ao final estilo e desempenho.

    Defeito sem caso concreto e classificado como suspeita, nao como defeito. Reproduzir o caso
    continua sendo obrigacao de quem recebe o parecer: este retorno nao executa nada.

    codigo: a rotina, em texto.
    nao_sigiloso: obrigatoriamente True. Atencao: codigo costuma trazer caminho de projeto,
      nome de cliente e credencial em literal. Limpar antes de enviar.
    contexto: opcional, o que a rotina deve fazer, unidades e sistema de coordenadas esperados.
    """
    if nao_sigiloso is not True:
        return AVISO_SIGILO
    if not codigo.strip():
        return "ERRO: codigo vazio."

    def alvo(nucleo):
        r = nucleo.fiscalizar_codigo(codigo, contexto=contexto, nao_sigiloso=True)
        cabeca = ("VEREDITO: SEM RESSALVA\n\n" if r.get("aprovado_sem_ressalva") else
                  "VEREDITO: COM RESSALVAS\n\n")
        return cabeca + r["texto"] + RODAPE_SEGUNDA_OPINIAO + _rodape_uso(r)

    return _executar(alvo)


@mcp.tool()
def argon_prova_independente(enunciado: str, nao_sigiloso: bool = False) -> str:
    """Pede ao Argon uma rotina Python AUTOCONTIDA que recalcule, do zero e as cegas, a grandeza
    do enunciado. Devolve a rotina para ser EXECUTADA NA UBUNTU, onde a comparacao dos numeros
    produz o veredito.

    Esta ferramenta NAO executa e NAO compara: codigo escrito por modelo de linguagem nao roda na
    estacao de trabalho. Enquanto nao executada, a rotina e insumo de conferencia, nao prova.

    Para obter o veredito em uma unica chamada, usar na Ubuntu:
        bin/llm.py --papel auditor-argon --nuvem --prova --referencia <seu numero> --texto "<enunciado>"
    que gera a rotina, executa em ambiente isolado (interpretador isolado, diretorio temporario e
    namespace de rede proprio) e devolve CONFERE, DIVERGE ou o motivo de nao ter dado veredito.

    NAO informar o seu resultado no enunciado: o calculo do Argon precisa ser as cegas, senao a
    prova mede concordancia, nao correcao.

    enunciado: os dados de entrada, as unidades e a grandeza pedida, sem a sua resposta.
    nao_sigiloso: obrigatoriamente True.
    """
    if nao_sigiloso is not True:
        return AVISO_SIGILO
    if not enunciado.strip():
        return "ERRO: enunciado vazio."

    def alvo(nucleo):
        r = nucleo.prova_independente(enunciado, meu_resultado=None, nao_sigiloso=True,
                                      executar=False)
        v = r.get("veredito")
        if v == "NAO_CALCULAVEL":
            return ("VEREDITO: NAO_CALCULAVEL (o enunciado nao tem dado suficiente)\n\n"
                    + r.get("motivo", "") + _rodape_uso(r))
        if v == "SEM_CODIGO":
            return ("VEREDITO: SEM_CODIGO (o Argon nao devolveu rotina nem declarou falta de "
                    "dado)\n\nResposta recebida:\n" + r.get("resposta", "") + _rodape_uso(r))
        if v != "NAO_EXECUTADO":
            return f"VEREDITO INESPERADO: {v}\n\n{r}" + _rodape_uso(r)
        return (
            "ROTINA DE RECALCULO RECEBIDA. AINDA NAO E PROVA: falta executar.\n\n"
            "```python\n" + r["codigo"] + "\n```\n\n"
            "Executar na Ubuntu e comparar com o seu numero, por exemplo com "
            "executar_python_ubuntu, ou refazer a chamada por "
            "bin/llm.py --papel auditor-argon --nuvem --prova --referencia <numero>, "
            "que ja executa em ambiente isolado e devolve o veredito.\n"
            "A ultima linha impressa pela rotina e 'RESULTADO: <valor>'; as linhas iniciadas por "
            "'# ' trazem as etapas e as unidades, para a conta poder ser conferida a mao."
            + _rodape_uso(r))

    return _executar(alvo)


@mcp.tool()
def argon_diagnostico() -> str:
    """Estado da instalacao do Argon nesta maquina, SEM exibir credencial: presenca da chave e sua
    impressao digital sha256, modelo configurado, versao do pacote google-genai, carregamento do
    nucleo e repositorio de certificados em uso. Primeiro passo quando uma ferramenta falha.

    Tambem lista os modelos que a chave alcanca, que e de onde sai o identificador gravado em
    config/papeis.json: nao existe modelo padrao chumbado no codigo, porque os nomes giram e um
    palpite viraria 404 silencioso semanas depois.
    """
    linhas = [
        f"interpretador: {sys.executable}",
        f"servidor: {os.path.abspath(__file__)}",
        f"ARGON_CORE: {os.environ.get('ARGON_CORE', '(nao definida)')}",
        f"GEMINI_API_KEY presente: {'sim' if os.environ.get('GEMINI_API_KEY') else 'NAO'}",
        f"ARGON_MODELO: {os.environ.get('ARGON_MODELO', '(nao definida)')}",
        f"truststore ativo: {'sim' if _TRUSTSTORE else 'nao (verificacao segue ativa pelo certifi)'}",
    ]
    nucleo, erro = _carregar_nucleo()
    if nucleo is None:
        linhas.append(f"nucleo: NAO CARREGADO. {erro}")
        return "\n".join(linhas)
    linhas.append("nucleo: carregado")
    try:
        d = nucleo.diagnostico()
        linhas.append(f"google-genai: {d.get('google_genai')}")
        linhas.append(f"impressao digital da chave: {d.get('chave_impressao_digital')}")
    except Exception as e:
        linhas.append(f"diagnostico do nucleo falhou: {nucleo.censurar(e)}")
    try:
        ms = nucleo.listar_modelos()
        linhas.append(f"\nmodelos com generateContent nesta chave: {len(ms)}")
        for m in ms[:40]:
            linhas.append(f"  {m['nome']:<46} ctx_in={m['ctx_entrada']} ctx_out={m['ctx_saida']}")
        if len(ms) > 40:
            linhas.append(f"  (mais {len(ms) - 40} nao listados)")
    except Exception as e:
        linhas.append(f"\nlistagem de modelos falhou: {nucleo.censurar(e)}")
    return "\n".join(linhas)


if __name__ == "__main__":
    mcp.run()
