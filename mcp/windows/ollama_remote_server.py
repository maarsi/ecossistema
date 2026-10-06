import os
import re
import base64
import math
import json
import time
import uuid
import shlex
import asyncio
import concurrent.futures
import requests
import paramiko

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

# Configurações de rede e credenciais (Tailscale / Workstation Ubuntu)
UBUNTU_IP = os.environ.get("UBUNTU_IP", "100.66.93.31")
UBUNTU_USER = os.environ.get("UBUNTU_USER", "mateus")
SSH_KEY_PATH = os.environ.get("SSH_KEY_PATH", r"C:\Users\mateu\.ssh\id_ed25519")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", f"http://{UBUNTU_IP}:11434").rstrip("/")
# A chave NGC nunca fica no codigo. Vem do bloco "env" do claude_desktop_config.json
# ou de variavel de ambiente do sistema.
NGC_KEY = os.environ.get("NGC_API_KEY") or os.environ.get("NVIDIA_API_KEY") or ""
NGC_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
# Repositorio do ecossistema na Ubuntu: fonte unica de papeis, regras e inventario.
ECOSSISTEMA = os.environ.get("UBUNTU_ECOSSISTEMA", f"/home/{UBUNTU_USER}/ecossistema")

mcp = FastMCP("UbuntuWorkstationOrchestrator")

def _ngc_indisponivel() -> str:
    """Retorna mensagem de erro se a chave NGC não estiver configurada no ambiente."""
    if not NGC_KEY:
        return ("Erro: NGC_API_KEY não configurada no ambiente. Defina-a no bloco 'env' do "
                "servidor ollama-remote em claude_desktop_config.json. "
                "Alternativa local sem chave: 'consultar_modelo_local' ou 'analisar_mapa_local_visao'.")
    return ""

# ----------------------------------------------------------------------
# 1. CATÁLOGO, DIRETRIZES OPERACIONAIS E GOVERNANÇA
# ----------------------------------------------------------------------
@mcp.tool()
async def obter_catalogo_e_diretrizes_modelos() -> str:
    """Retorna o ESTADO VIVO do ecossistema (inventario, papeis vigentes) e a regra de decisao.
    Chamar no inicio de tarefa relevante: a fonte e ~/ecossistema na Ubuntu, nao este texto.

    REGRA DE DECISÃO (CONDICIONAL AO TIPO DE TAREFA, NÃO CATEGÓRICA):

    A Workstation serve a quatro finalidades: processamento pesado, confidencialidade de dados,
    tarefas repetitivas e execução empírica de código. Não serve para terceirizar raciocínio
    técnico: um modelo de 12B a 14B produz insumo, não decisão metodológica.

    1. DELEGAR quando a tarefa atender pelo menos um critério:
       a) VOLUME: edital, TR, memorial ou relatorio extenso -> consultar_papel com papel 'doc' (qwen3:14b; acima de ~32K tokens, 'doc-longo' com gemma4:12b)
       b) CONFIDENCIALIDADE: dado de cliente, pesquisa bruta, material sob NDA -> SEMPRE local,
          independentemente do tamanho; devolver apenas agregados e conclusões
       c) PROCESSAMENTO: SIG, ETL, cruzamento de bases, cálculo em lote -> 'qwen2.5-coder:14b-fast'
          + 'executar_python_ubuntu'; roteirização e VRP -> 'otimizar_rotas_ortools'
       d) REPETIÇÃO: mesma operação sobre N arquivos, zonas, linhas ou cenários
       e) EXECUÇÃO E TESTE: sempre -> 'executar_python_ubuntu' no ambiente 'transporte'
          (trabalhos acima de ~2 min: background=True e consultar_job_ubuntu)

    2. NÃO DELEGAR, resolver diretamente, quando o produto da tarefa é o próprio raciocínio:
       - derivação de formulação: Logit, Probit, elasticidades, valor do tempo, teoria do fluxo,
         HCM, curvas BPR, funções de custo
       - escolha metodológica, crítica de premissas, desenho amostral, zoneamento
       - interpretação de resultado, diagnóstico de inconsistência, análise de sensibilidade
       - redação técnica de relatório, nota metodológica, proposta ou parecer
       - código curto (ordem de 50 linhas ou menos)
       Nesses casos o papel 'conferencia' (qwen3:30b-a3b) e 'raciocinar_ngc_kimi_k3' entram como SEGUNDA OPINIÃO,
       para conferir uma derivação já feita, nunca como fonte primária dela.

    3. DESEMPATE: se a tarefa é pensar, resolver aqui; se é processar, delegar.
       Na dúvida, escrever a formulação ou o código aqui e usar o Ubuntu para executar e testar.

    4. VALIDAÇÃO EMPÍRICA, PROPORCIONAL AO RISCO:
       - código que vai para entregável, cliente ou modelo: execução obrigatória no Ubuntu,
         com asserções, conferência de unidades, CRS e totais de controle
       - trecho ilustrativo de poucas linhas em uma explicação: não precisa rodar, mas deve
         vir rotulado como ilustrativo

    5. FRONTEIRA DE DADOS (atenção, ponto crítico):
       As ferramentas NGC e Kimi ('raciocinar_ngc_kimi_k3', 'analisar_mapa_kimi_k3',
       'analisar_mapa_sig_ngc', 'extrair_tabela_grafico_deplot', 'consultar_ngc_llama33_70b')
       ENVIAM O CONTEÚDO PARA FORA da Workstation, para APIs externas. Elas não atendem ao
       critério (b) de confidencialidade. Para dado sensível, usar apenas modelos locais
       do Ollama, OR-Tools e 'analisar_mapa_local_visao'.
    """
    cmd = (f"{ECOSSISTEMA}/bin/inventario.py --resumo; echo; {ECOSSISTEMA}/bin/llm.py --listar; echo; "
           f"echo 'Via preferencial para modelos: consultar_papel. Regras completas: {ECOSSISTEMA}/CLAUDE.md'")
    return await _executar_async(cmd, timeout=60)


def _caminho_ubuntu(caminho: str) -> str:
    """Converte caminho do Windows em D: para o ponto de montagem na Ubuntu."""
    c = caminho.replace("\\", "/")
    return "/media/mateus/DADOS_01/" + c[3:] if c.lower().startswith("d:/") else caminho


def _comando_llm(args: list, texto: str = "") -> str:
    """Monta o script bash que chama o gateway; texto inline vai por heredoc com marcador unico."""
    linhas = []
    if texto:
        tmp = f"/tmp/llm_in_{uuid.uuid4().hex[:10]}.txt"
        marca = f"__FIM_{uuid.uuid4().hex}__"
        linhas.append(f"cat > {tmp} <<'{marca}'\n{texto}\n{marca}")
        args = list(args) + ["--arquivo", tmp]
    linhas.append(f"{ECOSSISTEMA}/bin/llm.py " + " ".join(shlex.quote(str(a)) for a in args))
    if texto:
        linhas.append(f"rc=$?; rm -f {tmp}; exit $rc")
    return "\n".join(linhas)


@mcp.tool()
async def consultar_papel(papel: str, instrucao: str, caminho_arquivo: str = "", texto: str = "",
                          partes: bool = False, nuvem: bool = False, caminho_saida: str = "",
                          consolidar: str = "concatenar", max_tokens: int = 0, background: bool = False,
                          ocr: bool = False) -> str:
    """VIA PREFERENCIAL para acionar modelos: chama ~/ecossistema/bin/llm.py na Ubuntu pelo PAPEL.
    Papeis vigentes: ver obter_catalogo_e_diretrizes_modelos (ex.: doc, doc-longo, codigo, raciocinio-local, conferencia, visao, embeddings, raciocinio-nuvem, redacao-nuvem). O gateway usa contexto fixo por papel, RECUSA em vez de truncar,
    divide documento longo com partes=True e exige nuvem=True para papel de nuvem
    (o conteudo sai da workstation: nunca com dado sigiloso).
    - caminho_arquivo: PDF, DOCX, PPTX, XLSX, HTML (convertidos via Docling, com cache e marcadores de pagina)
      ou texto (.txt/.md/.csv/.json); caminho D:\\ e convertido. Alternativa: texto inline.
    - ocr=True: PDF digitalizado (OCRmyPDF por 300 DPI antes do Docling). Sem ele, PDF sem texto e recusado.
    - caminho_saida: grava a resposta em arquivo e devolve so estatisticas (economia de contexto).
    - consolidar: concatenar (extracao, padrao) ou llm (sintese) no modo partes.
    - background=True para documento longo com partes; acompanhar com consultar_job_ubuntu.
    """
    args = ["--papel", papel, "--instrucao", instrucao, "--consolidar", consolidar]
    if caminho_arquivo:
        args += ["--arquivo", _caminho_ubuntu(caminho_arquivo)]
    if partes:
        args.append("--partes")
    if nuvem:
        args.append("--nuvem")
    if ocr:
        args.append("--ocr")
    if caminho_saida:
        args += ["--saida", _caminho_ubuntu(caminho_saida)]
    if max_tokens:
        args += ["--max-tokens", int(max_tokens)]
    cmd = _comando_llm(args, "" if caminho_arquivo else texto)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_POOL, _executar_job, cmd, "transporte", "bash",
                                      f"llm_{papel}", "", background, SSH_TIMEOUT_S)

@mcp.tool()
async def consultar_modelo_local(modelo: str, prompt: str, num_ctx: int = 16384) -> str:
    """[LEGADO] Consulta direta a um modelo local pelo nome. Preferir consultar_papel.
    Agora passa pelo gateway llm.py com num_ctx fixo e RECUSA se o prompt nao couber.
    Motivo: sem num_ctx, o Ollama descartava ~metade do contexto e guardava so o final do texto, sem aviso.
    """
    cmd = _comando_llm(["--modelo", modelo, "--ctx", int(num_ctx)], prompt)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_POOL, _executar_job, cmd, "transporte", "bash",
                                      f"llm_{modelo}", "", False, SSH_TIMEOUT_S)

@mcp.tool()
def buscar_similaridade_local(pergunta: str, trechos: list[str]) -> str:
    """Ranqueia trechos documentais por similaridade semântica em relação a uma consulta técnica
    utilizando o modelo qwen3-embedding:4b no Ollama local (100% offline; 10/10 no bench de parafrase em portugues).
    """
    if not trechos:
        return "Erro: Nenhum trecho fornecido para ranqueamento."

    def _obter_vetor_local(texto: str) -> list:
        payload = {"model": "qwen3-embedding:4b", "prompt": texto}
        r = requests.post(f"{OLLAMA_HOST}/api/embeddings", json=payload, timeout=20)
        r.raise_for_status()
        return r.json()["embedding"]

    def _cosseno(v1, v2):
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        return dot / (norm1 * norm2) if (norm1 and norm2) else 0.0

    try:
        vetor_q = _obter_vetor_local(pergunta)
        ranqueados = []
        for i, t in enumerate(trechos):
            vt = _obter_vetor_local(t)
            score = _cosseno(vetor_q, vt)
            ranqueados.append((score, i + 1, t))

        ranqueados.sort(key=lambda x: x[0], reverse=True)

        linhas = [f"=== RANQUEAMENTO SEMÂNTICO LOCAL RAG (CONSULTA: '{pergunta}') ==="]
        for score, idx, t in ranqueados:
            linhas.append(f"• [Score: {score:.4f}] (Trecho #{idx}):\n  {t}\n")
        return "\n".join(linhas)
    except Exception as e:
        return f"Falha no RAG semântico local: {str(e)}"

@mcp.tool()
async def reranquear_trechos(pergunta: str, trechos: list[str], modelo: str = "Qwen/Qwen3-Reranker-0.6B") -> str:
    """Reordena trechos recuperados por relevancia real para a pergunta (cross-encoder na RTX 5060 Ti
    da Workstation Ubuntu, venv 'transporte'; 100% offline apos o primeiro download do modelo).
    Complemento de buscar_similaridade_local: use quando houver quase-duplicatas (mesmo tema,
    numeros parecidos) ou quando os scores de cosseno estiverem colados no topo.
    Modelo padrao: Qwen3-Reranker-0.6B (0,6B, multilingue, campeao do teste de quase-duplicatas);
    alternativa mais pesada: BAAI/bge-reranker-v2-m3.
    Execucao remota via mecanismo de jobs (~/.claude_jobs), como as demais ferramentas do servidor."""
    if not trechos:
        return "Erro: nenhum trecho fornecido."
    payload = json.dumps({"q": pergunta, "t": trechos, "m": modelo}, ensure_ascii=False)
    codigo = (
        "import json, sys\n"
        "try:\n"
        "    from sentence_transformers import CrossEncoder\n"
        "except ImportError:\n"
        "    print(\"Erro: sentence-transformers nao instalado no venv 'transporte'. \"\n"
        "          \"Instale com: pip install sentence-transformers\"); sys.exit(0)\n"
        f"dados = json.loads({payload!r})\n"
        "try:\n"
        "    ce = CrossEncoder(dados['m'], device='cuda')\n"
        "    scores = ce.predict([(dados['q'], t) for t in dados['t']])\n"
        "    ordenado = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)\n"
        "    linhas = [f\"=== RERANQUEAMENTO ({dados['m']}; consulta: '{dados['q'][:80]}') ===\"]\n"
        "    for rank, (i, s) in enumerate(ordenado, 1):\n"
        "        linhas.append(f\"{rank}o [score {float(s):.4f}] trecho #{i+1}:\\n  {dados['t'][i]}\")\n"
        "    print('\\n\\n'.join(linhas))\n"
        "except Exception as e:\n"
        "    print(f'Falha no reranking: {type(e).__name__}: {e}')\n"
    )
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_POOL, _executar_job, codigo, "transporte", "python",
                                      "reranquear_trechos", "", False, SSH_TIMEOUT_S)

@mcp.tool()
def otimizar_rotas_ortools(matriz_distancia: list[list[float]], demandas: list[float], capacidades_veiculos: list[float], num_veiculos: int, deposito: int = 0) -> str:
    """Resolve problemas de roteamento de veículos capacitados (CVRP) localmente via Google OR-Tools
    dentro do ambiente ~/env_transporte no Ubuntu.
    Aceita matrizes de tempo/distância reais com números decimais.
    """
    script_py = f"""
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import json

# Converte entradas numéricas para inteiros escalados para compatibilidade com os solucionadores do OR-Tools
matriz_bruta = {repr(matriz_distancia)}
demandas_brutas = {repr(demandas)}
capacidades_brutas = {repr(capacidades_veiculos)}

matriz_int = [[int(round(val * 100)) for val in linha] for linha in matriz_bruta]
demandas_int = [int(round(d)) for d in demandas_brutas]
capacidades_int = [int(round(c)) for c in capacidades_brutas]

dados = {{
    'matriz_distancia': matriz_int,
    'demandas': demandas_int,
    'capacidades_veiculos': capacidades_int,
    'num_veiculos': {num_veiculos},
    'deposito': {deposito}
}}

manager = pywrapcp.RoutingIndexManager(len(dados['matriz_distancia']), dados['num_veiculos'], dados['deposito'])
routing = pywrapcp.RoutingModel(manager)

def distancia_callback(from_index, to_index):
    return dados['matriz_distancia'][manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

transit_callback_index = routing.RegisterTransitCallback(distancia_callback)
routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

def demanda_callback(from_index):
    return dados['demandas'][manager.IndexToNode(from_index)]

demand_callback_index = routing.RegisterUnaryTransitCallback(demanda_callback)
routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, dados['capacidades_veiculos'], True, 'Capacidade')

search_parameters = pywrapcp.DefaultRoutingSearchParameters()
search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

solucao = routing.SolveWithParameters(search_parameters)

if solucao:
    rotas = []
    custo_total = 0.0
    for veiculo_id in range(dados['num_veiculos']):
        index = routing.Start(veiculo_id)
        sequencia = []
        custo_rota = 0
        carga_rota = 0
        while not routing.IsEnd(index):
            no = manager.IndexToNode(index)
            carga_rota += dados['demandas'][no]
            sequencia.append(no)
            previous_index = index
            index = solucao.Value(routing.NextVar(index))
            custo_rota += routing.GetArcCostForVehicle(previous_index, index, veiculo_id)
        sequencia.append(manager.IndexToNode(index))
        custo_real = custo_rota / 100.0
        custo_total += custo_real
        rotas.append({{
            'veiculo': veiculo_id + 1,
            'sequencia_nos': sequencia,
            'custo_tempo_min': round(custo_real, 2),
            'demanda_atendida': carga_rota
        }})
    print(json.dumps({{'custo_total_min': round(custo_total, 2), 'rotas': rotas}}, indent=2))
else:
    print(json.dumps({{'erro': 'Nenhuma solucao viavel encontrada para as restricoes informadas.'}}))
"""
    b64 = base64.b64encode(script_py.encode("utf-8")).decode("ascii")
    cmd = f"/home/mateus/env_transporte/bin/python -c \"import base64; exec(compile(base64.b64decode('{b64}').decode('utf-8'), '<string>', 'exec'))\""
    return _executar_ssh_paramiko(cmd, timeout=120)

# ----------------------------------------------------------------------
# 3. APIS DE ALTO DESEMPENHO (NVIDIA NGC)
# ----------------------------------------------------------------------
@mcp.tool()
def raciocinar_ngc_kimi_k3(prompt: str, reasoning_effort: str = "high") -> str:
    """Aciona o modelo Moonshot Kimi-k3 via NVIDIA NGC para raciocínio analítico avançado,
    dedução matemática de sistemas de transporte e planejamento operacional formal.

    ATENÇÃO: envia o conteúdo para API externa. Não usar com dado de cliente, pesquisa bruta
    ou material sob NDA. Uso recomendado: segunda opinião sobre derivação já feita,
    verificação numérica independente ou caso limite. Não é fonte primária de decisão metodológica.
    """
    erro = _ngc_indisponivel()
    if erro:
        return erro
    payload = {
        "model": "moonshotai/kimi-k3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.3,
        "reasoning_effort": reasoning_effort,
        "stream": False
    }
    headers = {
        "Authorization": f"Bearer {NGC_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    try:
        resp = requests.post(NGC_ENDPOINT, headers=headers, json=payload, timeout=240)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Falha na API Moonshot Kimi-k3 (NGC): {str(e)}"

@mcp.tool()
def extrair_tabela_grafico_deplot(caminho_imagem: str, prompt_instrucao: str = "") -> str:
    """Converte gráficos de carregamento, curvas de tráfego, histogramas e diagramas em tabelas estruturadas
    usando o modelo Google DePlot via NVIDIA NGC API.
    Aceita caminhos do Windows (ex: 'D:\\...') ou do Ubuntu (ex: '/media/mateus/DADOS_01/...').

    ATENÇÃO: a imagem é enviada para API externa. Para figura de relatório sob NDA,
    usar 'analisar_mapa_local_visao' ou digitalizar manualmente.
    """
    erro = _ngc_indisponivel()
    if erro:
        return erro
    caminho_limpo = caminho_imagem.replace("\\", "/")
    if caminho_limpo.lower().startswith("d:/"):
        caminho_ubuntu = "/media/mateus/DADOS_01/" + caminho_limpo[3:]
    else:
        caminho_ubuntu = caminho_imagem

    if not prompt_instrucao or not prompt_instrucao.strip():
        prompt_instrucao = "Generate underlying data table of the figure below:"

    script_py = f"""
import base64, io, os, sys, requests
from PIL import Image

caminho = {repr(caminho_ubuntu)}
prompt = {repr(prompt_instrucao)}
ngc_key = {repr(NGC_KEY)}

if not os.path.exists(caminho):
    print(f"Erro: Arquivo '{{caminho}}' não encontrado.")
    sys.exit(1)

with Image.open(caminho) as img:
    img = img.convert("RGB")
    w, h = img.size
    max_dim = 2048
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

payload = {{
    "model": "google/deplot",
    "messages": [
        {{
            "role": "user",
            "content": [
                {{"type": "text", "text": prompt}},
                {{"type": "image_url", "image_url": {{"url": f"data:image/jpeg;base64,{{img_b64}}"}} }}
            ]
        }}
    ],
    "max_tokens": 4096,
    "temperature": 0.1,
    "stream": False
}}

headers = {{
    "Authorization": f"Bearer {{ngc_key}}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}}

try:
    resp = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload, timeout=240)
    resp.raise_for_status()
    print(resp.json()["choices"][0]["message"]["content"])
except Exception as e:
    print(f"Falha na extração DePlot: {{str(e)}}")
    if 'resp' in locals() and resp.text:
        print(f"Detalhes: {{resp.text}}")
"""
    b64 = base64.b64encode(script_py.encode("utf-8")).decode("ascii")
    cmd = f"/usr/bin/python3 -c \"import base64; exec(compile(base64.b64decode('{b64}').decode('utf-8'), '<string>', 'exec'))\""
    return _executar_ssh_paramiko(cmd, timeout=200)

@mcp.tool()
def consultar_ngc_llama33_70b(prompt: str, system_prompt: str = "") -> str:
    """Executa o Llama 3.3 70B Instruct via NVIDIA NGC para redação técnica, relatórios formais
    e síntese de memoriais descritivos extensos.

    ATENÇÃO: envia o conteúdo para API externa. Não usar com dado de cliente ou material sob NDA.
    Uso recomendado: sumarização de texto longo já público. A redação técnica final de
    relatório, proposta ou parecer não deve ser delegada.
    """
    erro = _ngc_indisponivel()
    if erro:
        return erro
    messages = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "meta/llama-3.3-70b-instruct",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 8192
    }
    headers = {
        "Authorization": f"Bearer {NGC_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    try:
        r = requests.post(NGC_ENDPOINT, headers=headers, json=payload, timeout=220)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Falha na API Llama 3.3 70B (NGC): {str(e)}"

@mcp.tool()
def analisar_mapa_kimi_k3(caminho_imagem: str, prompt_analise: str = "", reasoning_effort: str = "high") -> str:
    """Analisa imagens de mapas, plantas e traçados usando o Moonshot Kimi-k3 na API NVIDIA NGC.
    Combina visão em alta resolução com esforço analítico profundo (Chain of Thought).

    ATENÇÃO: a imagem é enviada para API externa. Para mapa de projeto sob NDA,
    usar 'analisar_mapa_local_visao' (100% offline).
    """
    erro = _ngc_indisponivel()
    if erro:
        return erro
    caminho_limpo = caminho_imagem.replace("\\", "/")
    if caminho_limpo.lower().startswith("d:/"):
        caminho_ubuntu = "/media/mateus/DADOS_01/" + caminho_limpo[3:]
    else:
        caminho_ubuntu = caminho_imagem

    if not prompt_analise or not prompt_analise.strip():
        prompt_analise = (
            "Você é um engenheiro especialista em planejamento de transportes e SIG. "
            "Analise detalhadamente esta imagem técnica. Deduza a hierarquia viária, identifique nós críticos "
            "de circulação, examine sobreposições de bacias de captação e apresente deduções técnicas fundamentadas."
        )

    script_py = f"""
import base64, io, os, sys, requests
from PIL import Image

caminho = {repr(caminho_ubuntu)}
prompt = {repr(prompt_analise)}
effort = {repr(reasoning_effort)}
ngc_key = {repr(NGC_KEY)}

if not os.path.exists(caminho):
    print(f"Erro: Arquivo '{{caminho}}' não encontrado.")
    sys.exit(1)

with Image.open(caminho) as img:
    img = img.convert("RGB")
    w, h = img.size
    max_dim = 2048
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

payload = {{
    "model": "moonshotai/kimi-k3",
    "messages": [
        {{
            "role": "user",
            "content": [
                {{"type": "text", "text": prompt}},
                {{"type": "image_url", "image_url": {{"url": f"data:image/jpeg;base64,{{img_b64}}"}} }}
            ]
        }}
    ],
    "max_tokens": 8192,
    "temperature": 0.3,
    "reasoning_effort": effort,
    "stream": False
}}

headers = {{
    "Authorization": f"Bearer {{ngc_key}}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}}

try:
    resp = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload, timeout=220)
    resp.raise_for_status()
    print(resp.json()["choices"][0]["message"]["content"])
except Exception as e:
    print(f"Falha na API Kimi-k3: {{str(e)}}")
    if 'resp' in locals() and resp.text:
        print(f"Detalhes: {{resp.text}}")
"""
    b64 = base64.b64encode(script_py.encode("utf-8")).decode("ascii")
    cmd = f"/usr/bin/python3 -c \"import base64; exec(compile(base64.b64decode('{b64}').decode('utf-8'), '<string>', 'exec'))\""
    return _executar_ssh_paramiko(cmd, timeout=200)

@mcp.tool()
def analisar_mapa_local_visao(caminho_imagem: str, prompt_analise: str = "") -> str:
    """Realiza análise visual de mapas e traçados usando o modelo local qwen2.5vl:7b (100% offline; campeao do bench de visao 5/5)."""
    caminho_limpo = caminho_imagem.replace("\\", "/")
    if caminho_limpo.lower().startswith("d:/"):
        caminho_ubuntu = "/media/mateus/DADOS_01/" + caminho_limpo[3:]
    else:
        caminho_ubuntu = caminho_imagem

    if not prompt_analise or not prompt_analise.strip():
        prompt_analise = (
            "Analise este mapa sob a ótica de engenharia de transportes e SIG. "
            "Identifique a hierarquia da rede viária, bacias de captação pedonal, eixos principais e eventuais gargalos."
        )

    script_py = f"""
import base64, requests, json, sys, os
caminho = {repr(caminho_ubuntu)}
if not os.path.exists(caminho):
    print(f"Erro: Arquivo {{caminho}} não encontrado.")
    sys.exit(1)

with open(caminho, 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode('utf-8')

payload = {{
    'model': 'qwen2.5vl:7b',
    'prompt': {repr(prompt_analise)},
    'images': [img_b64],
    'stream': False
}}
r = requests.post('http://localhost:11434/api/generate', json=payload, timeout=180)
if r.status_code == 200:
    print(r.json().get('response', 'Sem resposta.'))
else:
    print(f"Erro HTTP {{r.status_code}}: {{r.text}}")
"""
    b64 = base64.b64encode(script_py.encode("utf-8")).decode("ascii")
    cmd = f"/usr/bin/python3 -c \"import base64; exec(compile(base64.b64decode('{b64}').decode('utf-8'), '<string>', 'exec'))\""
    return _executar_ssh_paramiko(cmd, timeout=200)

@mcp.tool()
def analisar_mapa_sig_ngc(caminho_imagem: str, prompt_analise: str = "") -> str:
    """Análise multimodal direta de mapas via Llama 3.2 Vision 11B na API NVIDIA NGC."""
    caminho_limpo = caminho_imagem.replace("\\", "/")
    if caminho_limpo.lower().startswith("d:/"):
        caminho_ubuntu = "/media/mateus/DADOS_01/" + caminho_limpo[3:]
    else:
        caminho_ubuntu = caminho_imagem

    if not prompt_analise or not prompt_analise.strip():
        prompt_analise = (
            "Você é um engenheiro especialista em planejamento de transportes e SIG. "
            "Analise tecnicamente este mapa. Identifique a hierarquia viária, bacias de captação pedonal, "
            "eixos de transporte coletivo, pontos de integração e eventuais restrições físicas."
        )

    codigo_py = f"""
import sys
sys.path.insert(0, '/home/mateus')
from test_vision_ngc import analisar_mapa_ngc

caminho = {repr(caminho_ubuntu)}
prompt = {repr(prompt_analise)}
analisar_mapa_ngc(caminho, prompt)
"""
    b64 = base64.b64encode(codigo_py.encode("utf-8")).decode("ascii")
    cmd = f"/usr/bin/python3 -c \"import base64; exec(compile(base64.b64decode('{b64}').decode('utf-8'), '<string>', 'exec'))\""
    return _executar_ssh_paramiko(cmd, timeout=200)

# ======================================================================
# NUCLEO DE EXECUCAO REMOTA (revisao 2026-09-18)
#
# Problemas corrigidos em relacao a versao anterior:
#  1. O Claude Desktop abandona a chamada apos ~240 s. O timeout interno era 400 s, entao
#     qualquer comando lento aparecia como "falhou" mesmo quando terminava na Ubuntu.
#     Agora: limite duro de SSH_TIMEOUT_S (padrao 170 s) para execucao em primeiro plano
#     e modo background (nohup + setsid) com consulta posterior do log.
#  2. stdout e stderr eram lidos em sequencia; se o processo remoto escrevesse muito em
#     stderr, o canal paramiko travava (deadlock). Agora os dois fluxos sao drenados juntos.
#  3. Codigo era injetado na linha de comando (base64 + exec). Funciona, mas nao deixa
#     rastro e nao serve para jobs longos. Agora o codigo e gravado via SFTP em
#     ~/.claude_jobs/<job>.py|.sh e executado a partir do arquivo, com log e codigo de saida.
#  4. Ferramentas sincronas bloqueavam o loop de eventos: um comando travado segurava
#     TODAS as chamadas seguintes. Agora a execucao SSH roda em thread e as ferramentas
#     de execucao sao assincronas.
#  5. Saida ilimitada consumia contexto. Agora retorna-se o final da saida (MAX_SAIDA_CHARS).
# ======================================================================
JOBS_DIR = os.environ.get("UBUNTU_JOBS_DIR", f"/home/{UBUNTU_USER}/.claude_jobs")
SSH_TIMEOUT_S = int(os.environ.get("SSH_TIMEOUT_S", "170"))      # < 240 s do Claude Desktop
SSH_TIMEOUT_MAX = 200                                              # teto absoluto em primeiro plano
MAX_SAIDA_CHARS = int(os.environ.get("MAX_SAIDA_CHARS", "12000"))
VENVS = {"transporte": f"/home/{UBUNTU_USER}/env_transporte", "trtllm": f"/home/{UBUNTU_USER}/env_trtllm"}
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _venv(ambiente: str) -> str:
    return VENVS.get(ambiente, VENVS["transporte"])


def _cortar(texto: str, limite: int = MAX_SAIDA_CHARS) -> str:
    if len(texto) <= limite:
        return texto
    return f"[... saida truncada: {len(texto)} caracteres no total; exibindo os ultimos {limite} ...]\n" + texto[-limite:]


def _conectar() -> "paramiko.SSHClient":
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    chave = paramiko.Ed25519Key.from_private_key_file(SSH_KEY_PATH)
    client.connect(UBUNTU_IP, username=UBUNTU_USER, pkey=chave, timeout=15, banner_timeout=20, auth_timeout=20)
    return client


def _ssh_exec_drenando(client, comando: str, timeout: int) -> tuple[str, str, int]:
    """Executa e drena stdout/stderr simultaneamente. Retorna (out, err, rc). rc=-1 se estourou o tempo."""
    chan = client.get_transport().open_session()
    chan.settimeout(5.0)
    chan.exec_command(comando)
    out, err = bytearray(), bytearray()
    inicio = time.monotonic()
    rc = None
    while True:
        atividade = False
        while chan.recv_ready():
            out += chan.recv(65536); atividade = True
        while chan.recv_stderr_ready():
            err += chan.recv_stderr(65536); atividade = True
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            rc = chan.recv_exit_status()
            break
        if time.monotonic() - inicio > timeout:
            rc = -1
            break
        if not atividade:
            time.sleep(0.05)
    try:
        chan.close()
    except Exception:
        pass
    return out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace"), rc


def _executar_bloqueante(comando: str, timeout: int) -> str:
    timeout = max(5, min(int(timeout), SSH_TIMEOUT_MAX))
    client = None
    try:
        client = _conectar()
        out, err, rc = _ssh_exec_drenando(client, comando, timeout)
        partes = []
        if out.strip():
            partes.append(out.strip())
        if err.strip():
            partes.append(f"[stderr]: {err.strip()}")
        if rc == -1:
            partes.append(f"[TIMEOUT] {timeout} s excedidos em primeiro plano. Para trabalhos longos use background=True "
                          f"e acompanhe com consultar_job_ubuntu(job_id).")
        elif rc not in (0, None):
            partes.append(f"[codigo de saida: {rc}]")
        return _cortar("\n".join(partes)) if partes else "Executado com sucesso (sem saida textual)."
    except Exception as e:
        return f"Erro na conexao SSH: {type(e).__name__}: {e}"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _executar_ssh_paramiko(comando: str, timeout: int = SSH_TIMEOUT_S) -> str:
    """Compatibilidade com as ferramentas antigas: execucao sincrona com limite duro de tempo."""
    fut = _POOL.submit(_executar_bloqueante, comando, timeout)
    try:
        return fut.result(timeout=min(int(timeout), SSH_TIMEOUT_MAX) + 15)
    except concurrent.futures.TimeoutError:
        return (f"[TIMEOUT] a execucao nao retornou em {timeout} s. O processo remoto pode continuar rodando. "
                f"Use background=True para trabalhos longos.")


async def _executar_async(comando: str, timeout: int = SSH_TIMEOUT_S) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_POOL, _executar_ssh_paramiko, comando, timeout)


def _gravar_arquivo_remoto(client, caminho: str, conteudo: str) -> None:
    sftp = client.open_sftp()
    try:
        try:
            sftp.stat(JOBS_DIR)
        except IOError:
            sftp.mkdir(JOBS_DIR, mode=0o700)
        with sftp.file(caminho, "w") as f:
            f.write(conteudo.encode("utf-8"))
        sftp.chmod(caminho, 0o700)
    finally:
        sftp.close()


def _novo_job_id(nome_job: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", nome_job.strip())[:40] if nome_job else "job"
    return f"{time.strftime('%Y%m%d_%H%M%S')}_{base}_{uuid.uuid4().hex[:6]}"


def _preparar_job(conteudo: str, ambiente: str, tipo: str, nome_job: str, diretorio_trabalho: str) -> tuple[str, str]:
    """Grava o script na Ubuntu e devolve (job_id, comando_de_execucao_em_primeiro_plano)."""
    job_id = _novo_job_id(nome_job)
    venv = _venv(ambiente)
    cd = f"cd {shlex.quote(diretorio_trabalho)} && " if diretorio_trabalho else ""
    if tipo == "python":
        arq = f"{JOBS_DIR}/{job_id}.py"
        exec_cmd = f"{cd}export PYTHONUNBUFFERED=1 PYTHONUTF8=1 && {venv}/bin/python {arq}"
        corpo = conteudo
    else:
        arq = f"{JOBS_DIR}/{job_id}.sh"
        exec_cmd = f"{cd}bash {arq}"
        corpo = f"#!/usr/bin/env bash\nset -o pipefail\nsource {venv}/bin/activate\nexport PYTHONUNBUFFERED=1 PYTHONUTF8=1\n{conteudo}\n"
    client = _conectar()
    try:
        _gravar_arquivo_remoto(client, arq, corpo)
    finally:
        client.close()
    return job_id, exec_cmd


def _lancar_background(job_id: str, exec_cmd: str) -> str:
    log = f"{JOBS_DIR}/{job_id}.log"
    rc = f"{JOBS_DIR}/{job_id}.rc"
    pid = f"{JOBS_DIR}/{job_id}.pid"
    inner = f"{exec_cmd} > {log} 2>&1; echo $? > {rc}"
    cmd = f"nohup setsid bash -c {shlex.quote(inner)} > /dev/null 2>&1 & echo $! > {pid}; cat {pid}"
    return _executar_ssh_paramiko(cmd, timeout=30)


def _executar_job(conteudo: str, ambiente: str, tipo: str, nome_job: str, diretorio_trabalho: str,
                  background: bool, timeout_s: int) -> str:
    try:
        job_id, exec_cmd = _preparar_job(conteudo, ambiente, tipo, nome_job, diretorio_trabalho)
    except Exception as e:
        return f"Erro ao gravar o script na Ubuntu via SFTP: {type(e).__name__}: {e}"
    if background:
        pid = _lancar_background(job_id, exec_cmd)
        return (f"[JOB EM BACKGROUND] job_id={job_id} pid={pid.strip()}\n"
                f"log: {JOBS_DIR}/{job_id}.log\n"
                f"Acompanhe com consultar_job_ubuntu('{job_id}'). O script fica em {JOBS_DIR}/{job_id}.{ 'py' if tipo=='python' else 'sh'}")
    t = max(5, min(int(timeout_s or SSH_TIMEOUT_S), SSH_TIMEOUT_MAX))
    cmd = f"timeout -k 5 {t}s bash -c {shlex.quote(exec_cmd)}"
    saida = _executar_ssh_paramiko(cmd, timeout=t)
    return f"[job_id={job_id}]\n{saida}"


# ----------------------------------------------------------------------
# 4. EXECUCAO COMPUTACIONAL E TESTES NO UBUNTU
# ----------------------------------------------------------------------
@mcp.tool()
async def executar_python_ubuntu(codigo_python: str, ambiente: str = "transporte", background: bool = False,
                                 nome_job: str = "", diretorio_trabalho: str = "", timeout_s: int = SSH_TIMEOUT_S) -> str:
    """Executa codigo Python na Workstation Ubuntu (o codigo e gravado em ~/.claude_jobs/<job>.py e executado pelo venv).
    Ambientes: 'transporte' (~/env_transporte: GeoPandas, OSMnx, Shapely, PyProj, NetworkX, Biogeme, SciPy, Pandas,
    OR-Tools, pyreadstat) e 'trtllm' (~/env_trtllm: TensorRT-LLM, CUDA).
    - background=False: execucao em primeiro plano, limite de timeout_s (max 200 s). Retorna a saida (final truncado).
    - background=True: lanca com nohup e retorna job_id imediatamente; acompanhe com consultar_job_ubuntu.
      Use SEMPRE background para leitura de bases grandes, geoprocessamento extenso, downloads e modelos.
    - diretorio_trabalho: 'cd' antes de executar (ex.: raiz do projeto), para caminhos relativos.
    Regras: nunca imprimir credenciais; carregar chaves apenas via .env; nao exportar registros individuais de microdados.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_POOL, _executar_job, codigo_python, ambiente, "python", nome_job,
                                      diretorio_trabalho, background, timeout_s)


@mcp.tool()
async def executar_comando_ubuntu(comando_bash: str, ambiente: str = "transporte", background: bool = False,
                                  nome_job: str = "", diretorio_trabalho: str = "", timeout_s: int = SSH_TIMEOUT_S) -> str:
    """Executa comandos bash na Ubuntu dentro do venv indicado (o script e gravado em ~/.claude_jobs/<job>.sh).
    Mesmas opcoes de executar_python_ubuntu: background para trabalhos longos, diretorio_trabalho para 'cd' previo,
    timeout_s (max 200 s) em primeiro plano. Evite 'find' amplo em /media/mateus (disco lento): use o inventario.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_POOL, _executar_job, comando_bash, ambiente, "bash", nome_job,
                                      diretorio_trabalho, background, timeout_s)


@mcp.tool()
async def consultar_job_ubuntu(job_id: str, linhas: int = 80) -> str:
    """Consulta um job lancado em background: situacao (rodando/concluido com codigo de saida) e as ultimas linhas do log."""
    job_id = re.sub(r"[^A-Za-z0-9_-]", "", job_id)
    cmd = (f"J={JOBS_DIR}/{job_id}; "
           f"if [ -f $J.rc ]; then echo \"[CONCLUIDO] codigo de saida: $(cat $J.rc)\"; "
           f"elif [ -f $J.pid ] && kill -0 $(cat $J.pid) 2>/dev/null; then echo \"[RODANDO] pid $(cat $J.pid) desde $(stat -c %y $J.pid | cut -c1-19)\"; "
           f"else echo \"[DESCONHECIDO] sem .rc e sem processo ativo (verifique o log)\"; fi; "
           f"echo \"--- log ($J.log, tamanho $(stat -c %s $J.log 2>/dev/null || echo 0) bytes) ---\"; "
           f"tail -n {int(linhas)} $J.log 2>/dev/null || echo '(log ainda nao criado)'")
    return await _executar_async(cmd, timeout=30)


@mcp.tool()
async def listar_jobs_ubuntu(ultimos: int = 15) -> str:
    """Lista os jobs mais recentes em ~/.claude_jobs com situacao e codigo de saida."""
    cmd = (f"cd {JOBS_DIR} 2>/dev/null || {{ echo 'nenhum job'; exit 0; }}; "
           f"for f in $(ls -t *.log 2>/dev/null | head -n {int(ultimos)}); do j=${{f%.log}}; "
           f"if [ -f $j.rc ]; then s=\"concluido rc=$(cat $j.rc)\"; elif [ -f $j.pid ] && kill -0 $(cat $j.pid) 2>/dev/null; then s=rodando; else s=desconhecido; fi; "
           f"echo \"$j | $s | $(stat -c %s $f) bytes\"; done")
    return await _executar_async(cmd, timeout=30)


@mcp.tool()
async def cancelar_job_ubuntu(job_id: str) -> str:
    """Interrompe um job em background (SIGTERM ao grupo de processos; SIGKILL apos 5 s se persistir)."""
    job_id = re.sub(r"[^A-Za-z0-9_-]", "", job_id)
    cmd = (f"P=$(cat {JOBS_DIR}/{job_id}.pid 2>/dev/null); if [ -z \"$P\" ]; then echo 'pid nao encontrado'; exit 0; fi; "
           f"kill -TERM -- -$P 2>/dev/null || kill -TERM $P 2>/dev/null; sleep 5; "
           f"kill -0 $P 2>/dev/null && {{ kill -KILL -- -$P 2>/dev/null || kill -KILL $P; echo 'encerrado com SIGKILL'; }} || echo 'encerrado'")
    return await _executar_async(cmd, timeout=30)

# ----------------------------------------------------------------------
# 5. TELEMETRIA E GERENCIAMENTO DE RECURSOS
# ----------------------------------------------------------------------
@mcp.tool()
def verificar_gpu_ubuntu() -> str:
    """Consulta em tempo real o estado da GPU NVIDIA RTX 5060 Ti (VRAM alocada, temperatura e processos)."""
    cmd = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader"
    gpu_info = _executar_ssh_paramiko(cmd)
    procs = _executar_ssh_paramiko("nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv")
    return f"=== TELEMETRIA DA GPU (RTX 5060 Ti) ===\n{gpu_info}\n\n=== PROCESSOS ALOCADOS ===\n{procs}"

@mcp.tool()
def listar_modelos_ubuntu() -> str:
    """Lista todos os modelos de IA disponíveis no daemon local do Ollama no Ubuntu."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code == 200:
            modelos = [m["name"] for m in r.json().get("models", [])]
            return "Modelos ativos no Ollama (Ubuntu):\n- " + "\n- ".join(modelos)
        return f"Ollama respondeu com status {r.status_code}."
    except Exception as e:
        return f"Não foi possível contactar o serviço Ollama: {str(e)}"

if __name__ == "__main__":
    mcp.run()