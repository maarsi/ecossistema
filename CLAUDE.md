# Ecossistema de processamento de Mateus: regras de orquestracao

Fonte unica da verdade para qualquer agente (Claude Desktop, Claude Code no Ubuntu).
Antes de tarefa relevante: `~/ecossistema/bin/inventario.py --resumo`.

## Papeis
- Orquestrador (Claude): metodologia, critica de premissas, redacao, decisao de rota, revisao.
- Processamento deterministico: Python, DuckDB, GeoPandas, OR-Tools, Biogeme, Docling.
- Insumo barato em volume: modelos locais via `bin/llm.py --papel <nome>`.
- Segunda opiniao externa: papeis de nuvem via `bin/llm.py --nuvem`.

## Regra de delegacao
Delegar tarefas de ENTRADA pesada (documento longo, base grande, lote repetitivo).
Nao delegar tarefas cujo produto e o raciocinio: formulacao, premissa, interpretacao, redacao final.
Codigo gerado por modelo local so tem valor se for executado e testado em seguida.
Verificacao por execucao vale mais que verificacao por outro modelo.

## Fronteira de dados
Claude (Desktop e Code) e os papeis de nuvem estao FORA da workstation.
O que protege dado sigiloso e o script devolver agregado, nunca registro individual.
Microdados de bilhetagem, OD bruta, dados pessoais e tabelas contratuais: processar por script
e devolver apenas estatisticas. Nuvem so com material publico ou sintetico.

## Economia de contexto
- Nunca exibir tabela bruta: agregar com DuckDB direto no arquivo e devolver no maximo 15 linhas.
- Resposta longa de modelo: `--saida arquivo.md` e ler so o trecho necessario.
- Trabalho acima de ~2 min: execucao em background e consulta do job.

## Armazenamento
- Escrita pesada, SQLite e GeoPackage: `/mnt/nvme_lexar/datasets_sig/` (ext4).
- `/media/mateus/DADOS_01/` (D:, NTFS via FUSE): apenas entrega e sincronizacao final.

## CRS
Definido POR PROJETO e registrado no referencial dele, nunca por estado.
Exemplos: Salvador UTM 24S (EPSG:31984); Sao Paulo capital, Rio e Brasilia UTM 23S (EPSG:31983);
Lencois Paulista UTM 22S (EPSG:31982). Projeto que cruza fusos (corredores bioceanicos):
projecao continental ou SIRGAS 2000 geografico, conforme a analise.

## Manutencao
Instalou ou removeu algo: rodar `bin/inventario.py` e fazer commit. Mudou papel: editar
`config/papeis.json` registrando o resultado do teste que justificou a mudanca.

## Licoes registradas (22/09/2026)
- NAO usar a ferramenta MCP `consultar_modelo_local` para documentos: ela nao define num_ctx e o Ollama
  descarta cerca de metade do contexto guardando o FINAL do texto, sem aviso. Usar `bin/llm.py`.
- `mistral-nemo:12b` reprovado em extracao (perdeu marcador mesmo com o texto inteiro visivel).
- Extracao em documento longo: `--partes` com consolidacao `concatenar` (padrao). A fusao por modelo
  apaga ocorrencias raras por "maioria" das partes vazias.
- Pergunta de avaliacao de modelo precisa ter resposta unica (evitar ambiguidade como ciclo com ou sem terminal).
- Configuracao de sistema (systemd, /etc, arquivos de servico): LER o arquivo inteiro antes de qualquer
  alteracao e nunca sobrescrever. Ajustes proprios vao em drop-in separado (ex.: ollama.service.d/10-desempenho.conf).
  Em 22/09 um `tee` sobrescreveu o override do Ollama e apagou OLLAMA_MODELS e OLLAMA_HOST.
- Servidor MCP do Windows e cliente fino: `consultar_papel` chama bin/llm.py; o catalogo le o inventario vivo.
  Fonte do servidor: mcp/windows/ (copiar para C:\TransportMCP e reiniciar o Claude Desktop apos mudanca).
- Documentos: `bin/llm.py --arquivo` aceita PDF, DOCX, PPTX, XLSX e HTML (Docling, cache por hash em cache/docling).
  PDF digitalizado e recusado sem `--ocr` (evita responder sobre pagina vazia). Marcadores de pagina com inicio E fim:
  com marcador unico o modelo citava a pagina seguinte (erro de uma pagina, 22/09).
- Bateria de avaliacao: `bench/bench.py --autoteste` antes de qualquer rodada (valida testes e gabaritos);
  resultado zerado ou vazio e suspeita de medicao ate prova em contrario (llama3.2-vision: erro 500, nao carrega
  no Ollama 0.34). Diferenca de 1 tarefa entre modelos e empate tecnico.
- Modelo novo so entra por bateria: candidato baixado, testado e removido se nao vencer (rodada 2, 22/09: ornith-1.5,
  granite4.2 e bge-m3 removidos; qwen3-embedding:4b adotado). Etiqueta `:cloud` no Ollama nao e modelo local.
- Acervo: `bin/indice.py` (LanceDB + papel embeddings; indices em /mnt/nvme_lexar/datasets_sig/indices).
  Indexa documentos (PDF, DOCX, DOC, MD, TXT), nunca dados. Excluir manuais de software (--excluir) e indexa-los
  em colecao propria. Colecao pgt_paiva (22/09): 72 arquivos, 3.095 trechos; validacao 11/20 em 1o, 18/20 no top 5.
  Ao buscar, ler os 5 primeiros: versoes gemeas (.docx e .md) e arquivos de processo (prompts) disputam o topo.
- Jobs em segundo plano: nunca usar `grep` sem `--line-buffered` no pipe (segura a saida ate o fim), e ao
  interromper um job, matar o script-mae, nao so o processo filho (o proximo comando da fila segue rodando).
- A pasta ~/ecossistema e pasta compartilhada do Syncthing (decisao de Mateus em 04/10: manter assim).
  Risco aceito: exclusao em outro dispositivo apaga arquivos daqui. O .gitignore em lista de permissao
  impede que o conteudo sincronizado entre no git; nunca relaxar essa lista.
- Offload medido (04/10, doc de 29k tokens, ctx 32768): qwen3:30b-a3b com 29% na CPU faz prefill 28% mais
  LENTO que um 14B denso, porem GERA 19% mais rapido (3B ativos). Offload penaliza leitura, nao escrita.

## Rodada de 06/10/2026 (madrugada): papel doc-longo e limpeza de modelos
- Novo papel `doc-longo` com gemma4:12b (4/4 na suite doc em 10,6 s; qwen3:14b tambem 4/4 em 5,7 s).
  Razao do papel: janela declarada de 262k tokens. Para documento que cabe em 32k, usar `doc` (qwen3:14b), mais rapido.
- Removidos por medicao na bateria, nenhum com papel:
  - qwen3-vl:8b ....... visao 3/5 (errou barras e contagem); qwen2.5vl:7b faz 5/5 e continua no papel `visao`
  - deepseek-r1:14b ... raciocinio 6/8 e codigo 4/6, 15 a 22 s por tarefa
  - qwen2.5-coder:14b . codigo 5/6 em 4,5 s, identico a variante `-fast` ja em uso: redundante
  - llama3.1:8b ....... raciocinio 1/8, codigo 2/6
  - nemotron-mini ..... raciocinio 0/8, codigo 0/6

## Registro de 07/10/2026: ativos e politica de atualizacao
- `qwen2.5-coder:14b-fast`: a tag sumiu do registro Ollama (re-pull falha; copia local intacta e funcional).
  ATIVO NAO-RECUPERAVEL: nunca executar `ollama rm` sobre este modelo — nao ha re-download ate surgir tag
  equivalente. Qualquer limpeza de modelos passa por conferencia previa desta lista.
  BACKUP (07/10): manifest + 6 blobs (8,19 GiB, gzip integro, 7 entradas conferidas) em
  `/media/mateus/DADOS_01/99 - BACKUPS/modelos/qwen2.5-coder-14b-fast_20261007.tar.gz`
  (entra no restic noturno das 03h). Restauracao: extrair na raiz de OLLAMA_MODELS
  (`/mnt/nvme_lexar/ia_models/ollama`), preservando os caminhos relativos manifests/ e blobs/.
- Stack Docker vigente: changedetection (:latest), osrm (PINADO — imagem osrm/osrm-backend,
  digest sha256:af5d4a83fb90086a43b1ae2ca22872e6768766ad5fcbb07a29ff90ec644ee409; recriar o container
  sempre por osrm/osrm-backend@sha256:..., nunca pela tag :latest), portainer, open-webui (:main),
  perplexica "vane" (:latest). Politica: atualizacao MANUAL, um container por vez, com backup da
  configuracao antes; nunca atualizar em lote nem habilitar auto-update.
- Chave NVIDIA tem ESCOPO por organizacao: a chave emitida fora do contexto CITATIS passou a devolver 403
  "Authorization failed" na inferencia, enquanto /v1/models continuava 200 (18/10). Diagnostico: 403 na inferencia
  e o sinal confiavel; listagem respondendo nao prova chave valida. Solucao: emitir chave com a organizacao selecionada.
- Modelo de nuvem pode sair do ar sem aviso (HTTP 410): mistral-nemotron descontinuado em 18/10, papel redacao-nuvem
  migrado para google/gemma-4-31b-it. Ao ver 410, trocar o modelo do papel, nao investigar a chave.

## Backup (18/10/2026)
- Remoto: git@github.com:maarsi/ecossistema.git (privado, chave SSH dedicada ~/.ssh/id_ed25519_github).
  Depois de qualquer commit relevante: `git push`. Nunca versionar .env (a lista de permissao do .gitignore ja barra).
- Copia secundaria: `git bundle create <destino>.bundle --all` em D:\TransportMCP\backup (reconstroi tudo offline).
- Modelos (3,2 GB do embed-vl, Ollama) e indices do NVMe NAO entram no backup: sao reconstruiveis.

## Rodada de 20/10/2026 (noite): anexos do Manus e bateria CVRP cuOpt x OR-Tools
- Skills NVIDIA instaladas em `.claude/skills/` (escopo do projeto): cuopt-routing-api-python,
  cuopt-numerical-optimization-api, cuopt-multi-objective-exploration, accelerated-computing-cudf.
- Anexos do Manus: as 419 falhas da rodada de 20/10 22:07 sao TODAS o mesmo motivo, e o rotulo
  "link expirado" em `bin/manus_export.py` esta ERRADO. O CloudFront devolve
  `<Code>InvalidKey</Code><Message>Unknown Key</Message>`, que e Key-Pair-Id fora da lista de
  signatarios confiaveis da distribuicao — nao expiracao. Provas: a Policy assinada vale ate
  31/12/2026; uma URL intacta devolve o MESMO erro que um Key-Pair-Id inventado; sem parametro
  nenhum o erro muda para MissingKey (ou seja, a camada de assinatura esta sendo avaliada, nao e
  bloqueio de IP). Amostra estratificada de 114 URLs novas nos 19 projetos: 114/114 em 403, inclusive
  arquivos que ja tinham baixado horas antes. E panne do lado do Manus, afeta 100% do acervo.
  NAO adianta nova tentativa enquanto o teste de uma URL nao voltar 200; o download e incremental
  (anexo em disco nao e refeito), entao repetir depois custa so os 1.008 ausentes de 4.580.
- Diagnostico de URL assinada: 403 sozinho nao diz nada. Ler o <Code> do corpo e decodificar a
  Policy base64 (substituicoes -_~ por +=/) antes de culpar expiracao ou chave de API.
- cuOpt 26.10 nao expoe trace de incumbente no Python: `dump_best_results` cria o arquivo e grava
  ZERO bytes, e `set_verbose_mode(True)` nao imprime nada. Perfil anytime so por varredura de
  orcamentos (resolver de novo com limites menores). OR-Tools tem o instante real via
  `AddAtSolutionCallback`. O solver do cuOpt e estocastico: repeticoes com o mesmo orcamento variam
  alguns decimos de %.
- Bateria CVRP (`bench/cvrp_cuopt_ortools.py`): a PRIMEIRA rodada (20/10) comparou os dois com frota
  folgada e funcoes objetivo diferentes. Os numeros dela (7.425 / 20.950 x 23.126 / 62.387 x 69.127)
  estao SUPERADOS e NAO podem ser citados: inflavam a vantagem do cuOpt. Ver a conclusao consolidada
  de 21/10 no fim deste arquivo. O que sobrevive daquela rodada e so o metodo (matriz inteira unica,
  validacao independente) e a constatacao de que o cuOpt roda em Blackwell sm_120.
- Dois ambientes cuOpt convivem por decisao de Mateus em 20/10: `~/env_cuopt` (26.8, com
  cuopt-server) e `/mnt/nvme_lexar/envs/cuopt` (26.10 + ortools, usado pela bateria CVRP).

## Rodada de 21/10/2026: comparacao justa no CVRP e sonda no exportador do Manus
- Objetivo do cuOpt: `set_objective_function(objectives, weights)` NAO permite desligar a
  minimizacao de veiculos — o proprio docstring diz "Solver optimizes for vehicle count first and
  then the total objective". Para igualar ao OR-Tools, travar a frota: `set_min_vehicles(K)` com
  `n_fleet=K` deixa so K viavel, o termo de contagem vira constante e sobra COST. Pesos declarados
  explicitamente (COST=1, VEHICLE_FIXED_COST=0) para nao depender de default. A skill
  cuopt-routing-api-python NAO documenta nem `set_objective_function` nem `set_min_vehicles`:
  sao os docstrings do pacote que valem.
- CORRECAO de registro: na rodada de 20/10 com 200 pontos o OR-Tools usou **12** veiculos, nao 14
  (frota de 14 DISPONIVEL no modelo, 2 rotas vazias). A tabela estava certa; errado estava um
  relato intermediario que dizia "gastava dois veiculos a mais". Os dois solvers sempre usaram 12;
  o que mudou na rodada justa foi a frota OFERECIDA ao modelo (14 -> 12), que encolhe o espaco de
  busca. Nunca confundir frota disponivel com frota usada.

### CONCLUSAO CONSOLIDADA CVRP (so estes numeros podem ser citados fora)
Regra: **so valor com frota igualada nas duas pontas e cuOpt em `--cuopt-so-distancia` e citavel**.
Qualquer numero de frota folgada ou objetivo diferente fica no historico e nao sai daqui.
Desenho: `--frota-fixa kmin --cuopt-so-distancia`, 30 s por solver, matriz inteira unica,
capacidade 100, demanda 1-10, RTX 5060 Ti. As 8 solucoes passaram na validacao independente.

| pontos | semente | frota | OR-Tools | cuOpt | vantagem |
|---|---|---|---|---|---|
| 50 | 42 | 3 | 7.480 | 7.425 | 0,7% |
| 200 | 42 | 12 | 22.546 | 20.940 | 7,1% |
| 1000 | 42 | 55 | 69.178 | 61.916 | 10,5% |
| 1000 | 43 | 56 | 89.160 | 84.010 | 5,8% |
| 1000 | 44 | 56 | 97.411 | 92.825 | 4,7% |

- Em 1000 pontos a vantagem do cuOpt e de 4,7% a 10,5% (media ~7%), sempre a favor dele, com os
  dois usando a MESMA frota (o minimo teorico) em todos os casos. Ruido do cuOpt medido em 3
  execucoes: 0,41% — a dispersao entre sementes e real, nao e ruido de solver.
- A dispersao vem do DESENHO da instancia, nao dos solvers: o deposito e sorteado junto com os
  clientes, entao sua posicao muda o piso radial que os dois pagam igualmente. Semente 42 cai
  perto do centro (distancia media ao deposito 414), 43 e 44 caem perto de bordas (607 e 684),
  e isso sozinho explica a distancia total saltar de 69k para 97k. Piso radial maior comprime a
  vantagem percentual. Em benchmark futuro, fixar o deposito no centro para medir so a parte
  otimizavel, ou reportar a vantagem sobre o excedente acima do piso radial.
- Travar a frota NAO e neutro para o OR-Tools: em 50 pontos ele PIOROU (7.425 com frota 5 para
  7.480 com frota 3), porque rotas vazias servem de estado intermediario para a busca local.
  Em 200 ele melhorou (23.126 -> 22.546). Ou seja, igualar a frota e o certo metodologicamente,
  mas nao favorece sistematicamente ninguem.
- Leitura pratica: ate ~50 pontos os dois empatam na pratica (0,7%) e o OR-Tools basta; de 200
  para cima o cuOpt entrega de 5% a 10% com a mesma frota, e a GPU se paga.
- Licao de metodo: comparar solvers com objetivos diferentes INFLA a diferenca (9,4% viraram 7,1%
  em 200 pontos). Antes de publicar qualquer numero: igualar frota e funcao objetivo, repetir o
  solver estocastico ao menos 3 vezes, e variar a semente — uma semente so nao mede nada.
- `bin/manus_export.py`: o rotulo "link expirado" saiu. `motivo_cdn()` le o `<Code>` do corpo do
  CloudFront e grava o motivo real (InvalidKey, MissingKey, AccessDenied...). Importante: ler o
  corpo ANTES de fechar a resposta — com `stream=True` + `r.close()` o `<Code>` se perde e o
  motivo vira "sem codigo no corpo".
- `sondar_anexos()`: baixa UMA url de anexo antes de comecar e aborta com mensagem clara se nao
  vier 200/206, em vez de marcar milhares de falhas. `--sem-anexos` pula a sonda. Testado em 21/10
  contra a panne em curso: aborta com "HTTP 403 (InvalidKey)" sem escrever nada em disco.

## Rodada de 21/10/2026 (tarde): roteirizacao no MCP, chave NVIDIA e licoes de processo

- ARQUIVO DO CHAT NAO E FONTE. Os cinco servidores MCP enviados pelo chat para analise estavam
  defasados: o `ollama_remote_server.py` recebido era de setembro (28.265 bytes) contra o canonico
  de 06/10 (41.801 bytes), sem o mecanismo de jobs, `consultar_papel`, `reranquear_trechos` nem
  `analisar_mapa_local_visao`. Aplicar a versao analisada teria apagado um mes de trabalho.
  Regra: antes de alterar qualquer arquivo do ecossistema, conferir sha256 contra o canonico do
  repo E contra o que roda em `C:\TransportMCP`. Os tres itens que eu havia "corrigido" (embeddings
  em lote, mapa de ambientes, num_ctx) ja estavam no canonico desde 06/10.
- `otimizar_rotas_ortools` rodava SEM metaheuristica e SEM limite de tempo, parando na primeira
  solucao viavel: contradizia a propria bateria. Agora PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH +
  `time_limit`, com parametro `orcamento_s` (padrao 10 s) e execucao pelo mecanismo de jobs
  (antes era base64 no comando, com `/home/mateus` fixo no caminho do venv).
- Nova ferramenta `otimizar_rotas_cuopt`: reaproveita `rodar_cuopt` e `validar` de
  `bench/cvrp_cuopt_ortools.py` em vez de reimplementar a chamada. Objetivo igualado ao OR-Tools
  (`so_distancia`, frota travada). RECUSA com mensagem, em vez de aproximar em silencio, frota
  heterogenea (a funcao testada modela capacidade unica) e deposito em indice diferente de 0.
- As duas ferramentas devolvem VERIFICACAO INDEPENDENTE na saida: custo recalculado pela matriz,
  cobertura de todos os nos, duplicados e capacidade por veiculo, sem usar nada interno do solver.
- `VENVS` ganhou `cuopt` -> `/mnt/nvme_lexar/envs/cuopt` (override por `UBUNTU_CUOPT_ENV`).
- Medicao de 21/10 no desenho citavel (frota travada no kmin nas duas pontas, cuOpt em
  so_distancia), 200 pontos, frota 12, 10 s por solver, todas aprovadas na verificacao:
  OR-Tools sem metaheuristica 23.192 (1,2 s de parede); com GUIDED_LOCAL_SEARCH 22.809 (10,2 s);
  cuOpt 21.023 (11,9 s). Ganho da metaheuristica: 1,65%. Vantagem do cuOpt: 7,83%.
  Os valores 22.546 e 20.940, que eu havia escrito nos comentarios do codigo, vinham da rodada
  superada de 20/10 e foram substituidos por estes.
- CHAVE NVIDIA rotacionada. A anterior foi exposta em texto puro em config enviado pelo chat.
  A nova esta em `~/ecossistema/.env` (perm 600, fora do versionamento) e no config do Windows.
  Testada em INFERENCIA, nao em listagem: `raciocinio-nuvem` (nvidia/nemotron-3-ultra-550b-a55b) e
  `redacao-nuvem` (google/gemma-4-31b-it) responderam HTTP 200 com conteudo.
- PROCEDIMENTO PADRAO PARA CREDENCIAL, a repetir: par RSA efemero gerado na Ubuntu; chave publica
  enviada a maquina de origem; cifragem OAEP-SHA256 lah; so a cifra trafega pelo chat; decifragem na
  Ubuntu; impressao digital sha256 conferida nas duas pontas; par efemero removido. A credencial em
  texto puro nunca passa pela conversa.
- SYNCTHING: a pasta `ecossistema` e **sendonly** na Ubuntu. A Ubuntu e a FONTE. Gravar o arquivo
  pelo lado do Windows nao propaga e deixa o par fora de sincronia ate um override manual.
  Alterar sempre na Ubuntu e deixar o Syncthing levar.
- PONTE: a resposta do MCP corta em ~60 s INDEPENDENTEMENTE de `timeout_s`. Comando com `sleep`
  longo, ou job em primeiro plano acima disso, perde a saida mesmo terminando bem. Para qualquer
  coisa acima de ~45 s: `background=True` e consulta curta ao log.
- Config entregue em `D:\95 - TEMP\claude_desktop_config.novo.json` com a chave NVIDIA aplicada
  na propria maquina. As chaves TomTom, Perplexity e Moonshot ficaram como `COLE_AQUI_...` porque
  nao estavam no arquivo enviado: copiar do config atual antes de substituir.

## Rodada de 21/10/2026 (fim da tarde): rotacao de chaves, Perplexity e Kimi

- Chaves rotacionadas por Mateus (TomTom, Perplexity, Moonshot) e aplicadas no config PELA PROPRIA
  MAQUINA dele, lendo os arquivos de `D:\95 - TEMP`: nenhuma passou pela conversa. A chave NVIDIA
  era a mesma do inicio da tarde (impressao digital identica), e o `.env` seguiu valido.
- IDENTIFICAR A CREDENCIAL ANTES DE USAR. O "token HERE" entregue nao e apiKey: em base64 ele
  decodifica para `reftkn:01:18...`, ou seja, refresh token da plataforma HERE. Resultado: 401 como
  `apiKey` ("apiKey not found") e 401 como Bearer ("Token Validation Failure"). Para montar a
  ferramenta HERE e a comparacao com o TomTom falta uma API Key gerada no portal. O prefixo em
  base64 identifica o tipo da credencial antes de qualquer tentativa.
- TomTom validada: geocode de Salvador devolveu HTTP 200 e -12,9642 / -38,5058.
- PERPLEXITY: o pacote npm `perplexity-mcp` estava parado por DOIS motivos somados, e nenhum era a
  chave. (1) TLS: o servidor em Node falha com "unable to verify the first certificate", provavel
  interceptacao do VPN Cisco; os servidores Python da mesma maquina fazem HTTPS sem problema, porque
  usam o conjunto de certificados do Python. (2) API: `POST /chat/completions` com `sonar` foi
  desativado e responde 403 com aviso de migracao. Substituido por `mcp/windows/perplexity_server.py`
  proprio, chamando `POST /v1/agent` com preset, no interpretador de `C:\TransportMCP\.venv`.
  Esquema conferido na referencia oficial: resposta em `output` -> item `type=message` -> parte
  `type=output_text`; fontes em itens `type=search_results`; citacoes nas `annotations`
  (`type=url_citation`). `model` e `preset` sao mutuamente exclusivos; modelo `anthropic/*` exige
  `max_output_tokens`. Testado de ponta a ponta: resposta com fontes sobre a Lei 15.432/2026.
- KIMI: `moonshot-v1-128k` foi desativado e devolve 404 "Not found the model ... or Permission
  denied", o que mantinha o servidor parado independentemente da chave. A conta enxerga hoje
  kimi-k2.6, kimi-k2.7-code, kimi-k2.7-code-highspeed e kimi-k3 (conferido em `/v1/models`).
  Padrao agora `kimi-k3`, que RECUSA temperatura diferente de 1 ("only 1 is allowed for this
  model"): o campo passou a ser omitido para ele e mantido em 0.3 para os demais. Modelo de
  raciocinio com orcamento de saida curto devolve HTTP 200 com conteudo vazio, e o servidor agora
  avisa em vez de retornar string vazia. Testado de ponta a ponta.
- Os dois servidores foram exercitados com as chaves reais DENTRO da maquina do Mateus, carregando
  o arquivo real com um stub do modulo `mcp`, nao uma copia do codigo.

## Rodada de 21/10/2026 (noite): HERE entra por medicao, e um defeito no t0 do TomTom

- HERE API Key valida (43 caracteres, diferente do refresh token de prefixo "reftkn" entregue antes).
  Responderam 200: Geocode v1, Routing v8, Matrix v8 e Traffic Flow v7.
- CONVENCOES DA HERE, verificadas contra a API, nao supostas: omitir `departureTime` devolve tempo
  COM transito; `departureTime=any` devolve fluxo livre; `now` e RECUSADO com 400 ("'now' is an
  invalid date/time"). O `summary` do Routing v8 traz `duration` e `baseDuration` juntos. O Flow v7
  devolve velocidade em METROS POR SEGUNDO, com `jamFactor` de 0 a 10.
- DEFEITO NO TOMTOM, corrigido hoje. `calcular_tempo_e_distancia_tomtom` nao pedia
  `computeTravelTimeFor=all`, e sem esse parametro a API OMITE `noTrafficTravelTimeInSeconds`. O
  codigo caia no valor de reserva e reportava o tempo COM transito como se fosse o t0, com atraso
  sempre zero. Medido: par Piraja-Lapa, 1.305 s com transito contra 1.133 s em fluxo livre, 15,2%
  perdidos. O campo `trafficDelayInSeconds`, usado antes como atraso, voltou 0 nos 28 pares, inclusive
  nos que tinham 20% de degradacao: ele mede atraso por incidente declarado, nao congestionamento.
  QUALQUER t0 tirado dessa ferramenta antes de 21/10/2026 esta contaminado com transito e nao serve
  para calibrar BPR.
- TLS: TESTADO, nao suposto, e corrigindo uma afirmacao minha de duas horas antes. O Crossref
  respondeu pelo Python do Windows com a verificacao de certificado ATIVA (transport_server, sem
  TRANSPORT_MCP_INSECURE_SSL). Logo o `verify=False` do tomtom_network_server.py era contorno antigo,
  nao necessidade atual. Substituido por verificacao ativa, com paliativo explicito
  (`TOMTOM_MCP_INSECURE_SSL=1`) e mensagem que ensina o caminho certo (REQUESTS_CA_BUNDLE com o
  certificado raiz corporativo). O problema de TLS e especifico do Node, que nao usa o repositorio de
  certificados do Windows; nao e da maquina.
- Novo servidor `mcp/windows/here_network_server.py`, espelhando o do TomTom para permitir comparacao
  no mesmo par, mais `matriz_impedancia_here`, que resolve a matriz em UMA chamada. Recusa frota de
  pares acima de 400 e marca par sem rota como `n/d` em vez de 0, porque 0 se confunde com viagem
  instantanea. Avisa quando ha ponto fora da envoltoria do Brasil, caso tipico de latitude e
  longitude trocadas que nao sai da faixa valida.

### CONCLUSAO CONSOLIDADA TOMTOM x HERE (so estes numeros podem ser citados fora)
Desenho: `bench/tomtom_vs_here.py`, 21/10/2026 por volta das 15h, 8 polos de Salvador, 28 pares, um
sentido por par, automovel, as duas fontes na MESMA janela de minutos.

| grandeza | mediana | p90 | maximo |
|---|---|---|---|
| distancia | 1,4% | 10,0% | 55,5% |
| tempo em fluxo livre (t0) | 3,9% | 9,8% | 21,0% |
| tempo com transito | 5,7% | 12,9% | 25,2% |

- Atraso declarado sobre o fluxo livre: TomTom 19,9% e HERE 21,6% de mediana. As duas CONCORDAM; a
  leitura de 0,0% no TomTom, vista na primeira rodada, era o defeito do `computeTravelTimeFor`.
- Para t0 as duas sao equivalentes dentro de 4% na mediana. Nenhuma substitui a outra: a HERE vale
  pela matriz em uma chamada e pelo fluxo por trecho com nome de via; o TomTom segue util par a par.
  Usar a divergencia entre as duas como FAIXA DE INCERTEZA do t0, nao como erro de uma delas.
- Pior caso de distancia: Piraja-Calcada, 8,0 km no TomTom contra 12,4 km na HERE (55,5%): rotas
  materialmente diferentes, conferir a mao antes de usar esse par.
- RESSALVA obrigatoria: 8 polos de uma unica cidade, uma unica janela de coleta, somente automovel.
  Nao extrapolar para outras cidades, outros periodos nem para caminhao.

### ACHADO QUE AFETA PROJETO: catalogo de coordenadas de Salvador
Os dois geocodificadores CONCORDAM ENTRE SI dentro de 250 m em Piraja (242 m), Barra (234 m) e
Calcada (630 m), e ainda assim ficam a 1,6 km (Piraja) e 2,9 km (Mussurunga) do catalogo embutido no
`tomtom_network_server.py`. Quando duas fontes independentes concordam entre si e discordam do
catalogo, o suspeito e o catalogo: as coordenadas de PIRAJA e MUSSURUNGA precisam de conferencia
manual antes de entrar em qualquer matriz. Em Lapa, Acesso Norte, Aeroporto e Iguatemi os dois
discordam ENTRE SI de 4,6 a 15,8 km, o nome e ambiguo e a coordenada tem de ser fixada a mao; nesses
quatro o TomTom foi o destoante (ate 14,1 km do catalogo). Resumo em
`bench/resultados/20261021_tomtom_vs_here_resumo.json`; o resultado por par ficou em
`D:\95 - TEMP\tomtom_vs_here_resultado.json`, fora do repositorio.

### CORRECAO sobre TLS, com medida pela via real (21/10/2026, apos o reinicio)

Afirmei duas vezes coisas diferentes sobre TLS nesta maquina, as duas sem medir pela via que importa.
Medido agora, chamando cada servidor MCP de fato, todos com verificacao de certificado ATIVA:

| host | servidor | resultado |
|---|---|---|
| api.crossref.org | transport_server | 200, verificacao OK |
| geocode/router/matrix.hereapi.com | here_network_server | 200 nos quatro endpoints, verificacao OK |
| api.tomtom.com | tomtom_network_server | SSLError, verificacao FALHA |

Conclusao: o problema NAO e da maquina nem do Python dela, e especifico do `api.tomtom.com`. O
`verify=False` original daquele servidor era necessario, e remove-lo quebrou a ferramenta (com
mensagem clara, que foi como o defeito apareceu). Fica pendente distinguir entre duas causas, ainda
nao testadas: `certifi` desatualizado no venv `C:\TransportMCP\.venv`, que nao teria a raiz usada
hoje pela TomTom, ou cadeia incompleta servida por aquele host. O primeiro se resolve com
`pip install -U certifi` no venv; o segundo exige apontar REQUESTS_CA_BUNDLE para um conjunto com o
intermediario. O paliativo `TOMTOM_MCP_INSECURE_SSL=1` restabelece o funcionamento imediato.

LICAO DE PROCESSO: teste em host vizinho nao prova nada sobre o host que interessa. O Crossref
funcionar com verificacao ativa nao autorizava concluir que a TomTom funcionaria.

### Validacao pela via do MCP, pos-reinicio (21/10/2026)
- `otimizar_rotas_ortools` e `otimizar_rotas_cuopt` na MESMA instancia de 10 pontos, frota 2,
  orcamento 5 s: AMBOS 333,0, mesma particao de rotas, verificacao independente aprovada nos dois.
  E a condicao de comparabilidade declarada obrigatoria: objetivo igualado nas duas pontas. cuOpt
  com 0,34 s de preparo e 0,48 s de solucao.
- `here-network`: geocodificacao, rota e matriz respondendo. A geocodificacao da Mussurunga devolveu
  "CCR Metro Bahia-Estacao Mussurunga" com escore 0,99, a 2,9 km do catalogo embutido no servidor do
  TomTom, confirmando o achado da comparacao com nome de POI explicito.
- `perplexity`: resposta ancorada com dez fontes e rodape de custo (US$ 0,0047 na consulta de teste).
- `kimi-assistant`: kimi-k3 respondendo em duas linhas, como pedido.

## Rodada de 21/10/2026 (22h): Google entra como terceira fonte e o catalogo de Salvador e corrigido

- Chave do Google Cloud (39 caracteres, prefixo AIza) com Geocoding, Places (New), Routes e Street
  View Static habilitadas. As tres primeiras testadas: 200 em todas. Novo servidor
  `mcp/windows/google_maps_server.py` com geocodificacao, busca de lugares tipada, rota e matriz.
- CONVENCOES VERIFICADAS CONTRA A API: a Routes devolve `duration` (com transito) e
  `staticDuration` (sem transito ao vivo); `computeRouteMatrix` devolve LISTA de itens com
  `originIndex`/`destinationIndex` e `condition`, e a ordem NAO e garantida (usar os indices); a
  Geocoding devolve `location_type` (ROOFTOP, GEOMETRIC_CENTER, APPROXIMATE); a Places (New)
  devolve o TIPO do lugar, o que separa estacao de metro de terminal de onibus no mesmo nome.
- CATALOGO DE POLOS DE SALVADOR CORRIGIDO no `tomtom_network_server.py`. Google e HERE
  concordaram entre si dentro de 29 m (Piraja), 79 m (Mussurunga) e 152 m (Acesso Norte), e os
  dois discordaram do catalogo em 1.672 m, 2.874 m e 1.138 m. REGRA: quando duas fontes
  independentes concordam entre si e discordam do registro, o suspeito e o registro.
  Em Lapa (211 m) e Iguatemi (190 m) a leitura se inverteu: o catalogo estava certo e erraram a
  HERE e o TomTom, por nome desatualizado (o antigo Shopping Iguatemi responde hoje como Shopping
  da Bahia). O TomTom foi a pior fonte para POI em Salvador: 10,3 km na Lapa, 14,1 km no Iguatemi,
  6,3 km no Aeroporto.
- O catalogo passou a guardar ATE DOIS pontos por polo, com o tipo declarado: acesso ao trilho e
  embarque no alimentador. Separacao medida: Lapa 70 m, Piraja 277 m, Aeroporto 1.116 m. A escolha
  entre os dois muda o tempo de acesso e nao se resolve por nome.

### CONCLUSAO CONSOLIDADA TRES FONTES (so estes numeros podem ser citados fora)
Desenho: 8 polos de Salvador com coordenada corrigida, 28 pares, um sentido, automovel, sem
transito ao vivo nas tres fontes.

| comparacao | mediana | p10 | p90 | sinal |
|---|---|---|---|---|
| Google sobre HERE | +17,6% | +9,3% | +27,2% | sempre positivo |
| Google sobre TomTom | +14,9% | +7,1% | +27,0% | misto |
| HERE sobre TomTom | -0,1% | -12,4% | +7,2% | misto |

- O Google e o maior dos tres em 27 dos 28 pares. Em distancia as tres concordam na mediana
  (+0,2% e +0,0%).
- A diferenca de TEMPO e DEFINICAO, nao ruido: o `staticDuration` do Google embute condicao
  tipica, enquanto o `noTrafficTravelTimeInSeconds` do TomTom e o `baseDuration` da HERE sao fluxo
  livre. Evidencia direta: as 22h15 o tempo COM transito do Google veio MENOR que o estatico.
- REGRA DE USO: para t0 de BPR usar TomTom ou HERE, que concordam na mediana. Misturar o estatico
  do Google infla o t0 em 15% a 18%, achata a curva volume-atraso e subestima o congestionamento.
  Para geocodificar equipamento de transporte, a ordem e Google (tipado), HERE, TomTom por ultimo.
- Ressalva: 8 polos de uma cidade, uma janela de coleta, automovel. A comparacao TomTom x HERE da
  tarde usou as coordenadas ANTIGAS, tres delas a mais de 1 km do equipamento: a divergencia
  relativa segue valida, mas os tempos absolutos de la nao sao estacao a estacao.

### VAZAMENTO DE CREDENCIAL (erro meu, 21/10/2026)
Ao incluir `str(erro)` na mensagem de falha de TLS do servidor do TomTom, a URL completa da
requisicao veio junto, e como a TomTom recebe a chave na query string, a chave foi parar na
conversa. Corrigido com `_sem_chave()`, que censura `key=...` em qualquer texto de erro antes de
sair, replicado no servidor do Google. REGRA: texto de excecao de API que leva chave na query
NUNCA sai sem censura. Chave do TomTom a rotacionar.

### FECHAMENTO DO CASO TLS DA TOMTOM (21/10/2026, 22h30)

Quatro rodadas de diagnostico, e o erro de metodo em cada uma vale mais que a solucao:

1. Testei o Crossref e conclui que o Python da maquina verificava certificado sem problema.
   ERRADO como generalizacao: host vizinho nao prova nada sobre o host que interessa.
2. Testei o interpretador de `C:\TransportMCP\.venv`. ERRADO: o servidor do TomTom roda com o de
   `D:\TransportMCP\.venv`, o que estava no proprio config que eu tinha lido.
3. Testei o interpretador certo pelo Explorador e passou, enquanto a ferramenta falhava. Isso sim
   foi informativo: mesma maquina, mesmo interpretador, mesmo host, resultado diferente conforme
   quem lanca o processo.
4. Fiz o servidor informar o motivo real do OpenSSL. Veio `unable to get local issuer certificate`,
   com SSL_CERT_FILE e REQUESTS_CA_BUNDLE vazias. Isso elimina interceptacao corporativa (daria
   'self signed certificate in chain') e variavel de ambiente herdada.

CAUSA: cadeia incompleta servida por parte dos nos da CDN da TomTom. O `certifi` e um arquivo
estatico e nao tem como completar cadeia que o servidor nao manda; o repositorio de certificados do
Windows busca o intermediario que falta pela extensao AIA. Por isso a falha e INTERMITENTE: depende
do no que atende.

SOLUCAO, sem desligar verificacao: `pip install truststore` no venv e `truststore.inject_into_ssl()`
no servidor. Instalado o truststore 0.10.5 em `D:\TransportMCP\.venv`, ligado no
`tomtom_network_server.py` e, preventivamente, no `google_maps_server.py`, que roda no mesmo venv.
Com o truststore ativo, `verify` TEM de ser True: passar caminho de arquivo substituiria o
repositorio do sistema pelo conjunto estatico e anularia o ganho. Chaves de escape mantidas:
`TOMTOM_USAR_TRUSTSTORE=0` e `TOMTOM_MCP_INSECURE_SSL=1`.

LICOES DE PROCESSO, as tres:
- Teste no host vizinho nao vale; testar o host que falha.
- Testar no interpretador que o servidor usa, nao em outro da mesma maquina.
- Antes de propor remedio, fazer o codigo dizer o motivo real. Tres hipoteses minhas cairam com uma
  unica linha de erro do OpenSSL.

NOTA DE INFRAESTRUTURA: a gravacao remota de arquivo nesta ponte devolveu conteudo DEFASADO em tres
ocasioes, mesmo reportando sucesso, inclusive com `force`. Contorno que funcionou: gravar com nome
novo, conferir o sha256 no destino e so entao copiar por cima pelo shell. Conferir hash no destino
antes de instalar deixou de ser zelo e passou a ser necessario.

### Pendencias antigas, fechadas e nao fechadas (21/10/2026, 22h40)

- FECHADA: `bin/inventario.py` nao varria `/mnt/nvme_lexar/envs`. Corrigido, e o registro agora
  mostra os DOIS ambientes cuOpt com os pacotes de cada um: `~/env_cuopt` (cuopt 26.8.0 com
  cuopt-server-cu13) e `/mnt/nvme_lexar/envs/cuopt` (cuopt 26.10.0 com ortools, o que a bateria
  CVRP e a ferramenta MCP usam). Lembrete de uso: `--resumo` so relê o `config/registro.json`
  gravado; para refletir mudanca de ambiente e preciso rodar sem argumento.
- NAO FECHADA, e nao e nossa: os 1.008 anexos do Manus seguem inacessiveis. A sonda do exportador
  devolveu HTTP 403 (InvalidKey) de novo em 21/10 as 22h37, mesmo diagnostico de 20/10: o
  Key-Pair-Id que assina as URLs nao esta entre os signatarios confiaveis da distribuicao
  CloudFront do Manus. Nao e expiracao de policy e nao tem contorno do nosso lado. O exportador
  aborta antes de tocar no acervo, como deve. Encaminhamento possivel: abrir chamado no suporte do
  Manus citando o codigo InvalidKey; enquanto isso, `--sem-anexos` exporta so as conversas.

## Auditoria independente antes de fechar entregavel

Antes de fechar entregavel tecnico, rodar job critico ou concluir calculo relevante, acionar o
servidor MCP `argon-auditor` (Argon, Gemini) como segunda opiniao e, quando houver numero, como
verificacao independente.

ESCOPO, QUE NAO E NEGOCIAVEL. A regra vale sobre METODO e CODIGO, nunca sobre dado de cliente.
O Argon e modelo de NUVEM: o conteudo sai da workstation. Submeter formulacao, premissa, rotina e
enunciado com o dado substituido por sintetico ou agregado. Nunca pesquisa bruta, microdado, nome
de cliente ou material sob NDA. O entregavel registra o que foi submetido a auditoria. Regra de
escopo mais larga que isso seria descumprida de rotina, e regra descumprida de rotina corroi as
outras.

AS TRES FERRAMENTAS, E O QUE CADA UMA E DE VERDADE

  argon_auditar_metodologia  Segunda opiniao sobre premissa e metodo, de 3 a 5 pontos. NAO e
                             verificacao independente: nenhum numero e conferido, so lido. Enviar
                             o material SEM a conclusao propria, para a leitura dele nao se
                             ancorar nela.

  argon_fiscalizar_codigo    Segunda opiniao sobre rotina, com caso concreto de entrada por
                             defeito. Defeito sem caso concreto e suspeita, nao defeito, e
                             reproduzir o caso continua sendo obrigacao de quem recebe o parecer.

  argon_prova_independente   Verificacao independente de verdade: o Argon escreve uma rotina
                             autocontida, a rotina e EXECUTADA em ambiente isolado e o veredito e
                             a comparacao dos dois numeros. O numero do solicitante nao vai no
                             prompt: o calculo dele e as cegas. Pela ponte do Windows a ferramenta
                             devolve a rotina SEM executar, porque codigo escrito por modelo nao
                             roda na estacao de trabalho; o veredito sai na Ubuntu, com
                             bin/llm.py --papel auditor-argon --nuvem --prova --referencia <numero>

LER O VEREDITO COM A MEDICAO NA MAO. 'SEM RESSALVA' e resposta valida, e esta no prompt de
proposito: auditor que nunca aprova nada nao informa nada. A suite `auditoria` de bench/bench.py
mede as DUAS metades, deteccao de erro plantado e falso positivo em item correto, e o campo
`teste` do papel em config/papeis.json traz o numero da ultima medicao. Comparar o parecer com
essa taxa antes de agir sobre ele.

QUANDO NAO DER. Se a ponte cair, a chave falhar ou a cota acabar, registrar no entregavel
"auditoria independente nao realizada: <motivo>" e seguir. Ausencia de parecer NAO e parecer
favoravel, do mesmo jeito que valor ausente nao vira zero.

CAMADAS. A logica vive em bin/argon_core.py na Ubuntu, que e fonte unica, e o servidor
mcp/windows/argon_mcp.py a carrega pela variavel ARGON_CORE apontando para a copia sincronizada
por Syncthing. Nao existe copia local dos prompts: prompt de auditoria duplicado em duas maquinas
vira dois criterios diferentes sem ninguem perceber.

## Rodada de 22/10/2026: o Argon (Gemini) entra por medicao como auditor

Construido: bin/argon_core.py (fonte unica dos prompts, da censura de credencial, da recusa por
orcamento e da prova real), mcp/windows/argon_mcp.py (servidor argon-auditor, quatro ferramentas),
integracao em bin/llm.py (provedor google, chamar_google, prova_real, --prova e --referencia) e a
suite `auditoria` em bench/bench.py.

### CONCLUSAO CONSOLIDADA AUDITORIA (so estes numeros podem ser citados fora)

Desenho: 9 itens, 6 com erro plantado e 3 de controle tecnicamente defensaveis, prompt identico ao
de producao (importado de argon_core, nao copiado), temperatura 0, uma passada por modelo.
Mede DUAS metades: deteccao do erro plantado e falso positivo em item correto.

  modelo                    total  deteccao  falso positivo  t medio
  gemini-4-argon             9/9      6/6         0/3         12,8 s   <- titular
  gemini-3.1-pro-preview     9/9      6/6         0/3         21,9 s
  gemini-3.8-flash           9/9      6/6         0/3         21,7 s
  qwen3:30b-a3b (local)      4/9      4/6         3/3         59,7 s

Leitura: o modelo local, no papel de auditor, perde um terco dos defeitos E acusa defeito nos tres
itens corretos, ou seja, nunca aprova nada, e um veredito dele nao carrega informacao. Alem disso
59,7 s por item excede o corte de 45 s da ponte MCP. Entre os tres de nuvem houve empate perfeito
no acerto, e a escolha foi pela latencia.

RESSALVAS OBRIGATORIAS AO CITAR:
  - uma passada por modelo, 9 itens. Diferenca de um item e empate tecnico.
  - com tres modelos de fronteira em 9/9 a suite CHEGOU AO TETO: ela separa nuvem de local, nao
    ordena modelos de nuvem. Para ordenar, precisa de itens mais dificeis.
  - os controles de CODIGO funcionam melhor que os de METODOLOGIA, porque codigo tem correcao
    decidivel. O unico controle de metodologia que sobreviveu teve de declarar explicitamente o
    proprio escopo para nao haver extrapolacao a criticar.

### ERRO NO PROPRIO INSTRUMENTO, achado pela medicao (22/10/2026)

O item `c_t0_correto`, escrito por mim como controle, foi reprovado pelos QUATRO modelos. A leitura
do parecer mostrou que eles estavam certos: a capacidade do HCM aparecia transposta sem os fatores
de ajuste locais (largura de faixa, rampa, pesados, razao de verde) e sem declarar alfa e beta, e a
validacao por mediana de pares esconde erro compensatorio no arco, que e a unidade de entrada da
BPR. O item foi RECLASSIFICADO como erro plantado (`d_capacidade_transposta`) e um controle novo
(`c_amostra_declarada`) entrou no lugar. Regra confirmada: quando fontes independentes concordam
entre si e discordam do registro, o suspeito e o registro, e isso vale contra quem escreveu a suite.

### LICOES DE INFRAESTRUTURA (22/10/2026)

1. O CACHE DA GRAVACAO REMOTA E DO LADO DA ORIGEM. Gravar na maquina Windows um arquivo editado de
   novo a partir do MESMO caminho de origem no contentor entrega o conteudo da versao ANTERIOR,
   reportando sucesso. Explica as cinco "gravacoes defasadas" de 21 e 22/10. Regra: toda gravacao
   sai de um nome de origem INEDITO, com conferencia de sha256 no destino antes de usar.

2. EXISTEM QUATRO claude_desktop_config.json NESTA MAQUINA, e o VIVO fica em
   %LOCALAPPDATA%\Claude-Data\claude_<sufixo aleatorio>\. Nao e %APPDATA%\Claude. Editei o
   errado por duas rodadas sem erro nenhum aparecer, so sem efeito. Regra: o caminho do arquivo
   vivo nao se deduz, se le de config_caminho.txt, e o script lista todos os candidatos.

3. EDITAR A CONFIGURACAO COM O APLICATIVO ABERTO NAO VALE. Fechar por completo, inclusive a
   bandeja. O script recusa rodar se detectar o processo.

4. google-genai 2.32.0: o Client COMPARTILHA o transporte HTTP. Criar um Client por chamada faz a
   segunda falhar com 'Cannot send a request, as the client has been closed', ANTES de sair da
   maquina. Derrubou a primeira bateria com 0/8 nos tres modelos, e o unico sinal foi a latencia
   de 0,0 s. Cliente e memorizado por processo, e o bench avisa quando a latencia maxima fica
   abaixo de 0,5 s.

5. MODELO DE RACIOCINIO COM max_tokens BAIXO devolve VAZIO com finish_reason=MAX_TOKENS, porque
   gastou o orcamento pensando. Fez o gemini-3.5-flash parecer quebrado numa sondagem com
   max_tokens=24. Piso de 512 no gateway e diagnostico explicito na mensagem.

6. 503 UNAVAILABLE e sobrecarga momentanea e pede nova tentativa (tres, com espera crescente).
   429 com 'limit: 0' NAO pede: e modelo nao liberado para a chave, e repetir so queima cota.
   Aparecer em models.list nao significa poder chamar: a listagem trouxe 46 modelos.

7. ISOLAMENTO DA PROVA REAL: 'unshare -rn' falha nesta workstation com 'write failed
   /proc/self/uid_map: Operation not permitted', porque
   kernel.apparmor_restrict_unprivileged_userns = 1. O bubblewrap funciona sem privilegio no mesmo
   kernel, entao a prova real roda em 'bwrap --unshare-net --ro-bind / /': sem rede e com sistema
   de arquivos somente leitura. Medido: sem bwrap a resolucao de nome funciona, com bwrap da
   gaierror.

8. GUARDA SOBRE PALPITE CUSTA RODADA. Exigi que a chave do Gemini comecasse com 'AIza', por
   analogia com a chave do Maps, e o guarda recusou uma chave CORRETA. Verificacao assumida nao e
   verificacao: trocada por conferencia estrutural (palavra unica, sem espaco, tamanho minimo) e
   comparativa (prefixo contra o da chave que ja estava na variavel).

9. CHAMADA EM PRIMEIRO PLANO QUE ESTOURA O CORTE DE 60 s DA PONTE PERDE A SAIDA, mesmo que o
   processo termine bem na Ubuntu. Sondagem de 12 modelos foi perdida assim. Acima de 45 s:
   background com registro em arquivo, sempre.

### VAZAMENTO DE CREDENCIAL (22/10/2026)

O claude_desktop_config.json com as SEIS chaves em texto puro foi anexado ao chat. Todas foram
rotacionadas e reinstaladas no mesmo dia, por transferencia cifrada (envelope AES-256-GCM com
RSA-OAEP-SHA256, par efemero gerado na Ubuntu e destruido apos o uso), com impressao digital
sha256 conferida nas duas pontas e nenhum valor passando pelo chat. Para inspecionar configuracao
de agora em diante: mcp/windows/claude_desktop_config.sanitizado.json, ou leitura pela ponte, nunca
anexo.

PENDENCIA ABERTA: a pasta ~/ecossistema nao tem .stignore, e o Syncthing sem lista de exclusao
sincroniza o .env para os quatro dispositivos pareados. Por isso a GEMINI_API_KEY foi gravada em
~/TransportMCP/.env, fora da pasta sincronizada. Decidir se cria o .stignore e se apaga as copias
ja propagadas nos outros dispositivos.
