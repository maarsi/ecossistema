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

## Rodada de 23/10/2026 (madrugada): DeepSeek entra, o titular de nuvem reprova, e uma correcao

### CONCLUSAO CONSOLIDADA RACIOCINIO (so estes numeros podem ser citados fora)

Desenho: suite raciocinio, 8 itens numericos de engenharia de transportes com gabarito e
tolerancia (frota, logit binomial, elasticidade-arco, BPR, VPL, Little, capacidade, valor do
tempo), temperatura 0. Duas passadas nos candidatos de nuvem.

  modelo                                passada 1   passada 2   t medio
  deepseek-flash                          8/8         8/8       2,4 s e 3,1 s   <- titular
  deepseek-v4-pro                         8/8         8/8      13,2 s e 6,3 s
  qwen3:30b-a3b (local)                   8/8          -        26,2 s
  nvidia/nemotron-3-ultra (ex-titular)    6/8          -        51,1 s

ACHADO QUE MUDA PRATICA: o modelo LOCAL gabaritou tambem. Para esta classe de problema a
fronteira de dados NAO custa acerto, custa velocidade. Material sigiloso vai para o papel
conferencia sem perda de qualidade; a nuvem serve para quando o tempo importa.

O EX-TITULAR NUNCA HAVIA SIDO MEDIDO. O campo teste dele dizia apenas "2026-09-22: resposta
correta no problema de frota, 10 s", que e amostra de tamanho um. Medido na suite, fez 6/8 em
51,1 s, acima do corte de 45 s da ponte, e errou JUSTAMENTE o item frota, a unica tarefa que o
havia qualificado. Melhor ilustracao possivel da regra: amostra de um nao e resultado.

Observado de passagem: o nemotron emite o raciocinio em ingles SEM as etiquetas <think>, entao
limpar_raciocinio() nao o remove e esse texto iria para quem chamou o papel. Com max_tokens=300
ele gastou o orcamento raciocinando e nao entregou o numero.

RESSALVA: com tres modelos em 8/8, a suite raciocinio tambem chegou ao teto e nao os ordena por
acerto, so por velocidade.

### CORRECAO DO REGISTRO DO AUDITOR (23/10/2026)

O campo teste de auditor-argon citava "9/9, falso positivo 0/3, 12,8 s" a partir de UMA passada.
A segunda passada deu 8/9 com falso positivo 1/3 em 17,4 s, acusando o controle c_frota_correta.
Deteccao ficou estavel em 6/6 nas duas. O gemini-3.8-flash foi MAIS ESTAVEL no acerto, 9/9 e 9/9
com falso positivo 0/3 nas duas, porem 28% mais lento. Titular mantido por decisao de Mateus pela
latencia, com a diferenca de acerto dentro da faixa de empate tecnico (um item em dezoito
observacoes de controle). O campo teste foi reescrito com as duas passadas e as ressalvas.

LICAO: o campo teste de um papel deve trazer REPETICAO, nao uma passada. Uma passada produz
numero de ponto onde existe intervalo, e isso vale tanto para acerto quanto para latencia: a
latencia do mesmo modelo variou por fator de dois entre rodadas (deepseek-v4-pro, 13,2 s e 6,3 s;
gemini-4-argon, 12,8 s e 17,4 s).

### INFRAESTRUTURA

bin/llm.py deixou de ter o endpoint da NVIDIA chumbado: provedores de nuvem no formato OpenAI
ficam na tabela PROVEDORES_OPENAI, e acrescentar provedor e acrescentar uma linha. O Google segue
fora da tabela, porque o SDK dele tem outra forma e vive em bin/argon_core.py. chave_nvidia()
virou chave_env(nome), e a mensagem de erro passou a levar o corpo da resposta, censurado por
_sem_credencial.

CHAVE DO DEEPSEEK: transferida sem passar pelo chat e SEM precisar de script no Windows. A maquina
virtual Linux da estacao tem cryptography instalado, entao a cifragem RSA-OAEP-SHA256 aconteceu lA
DENTRO, contra a chave publica efemera da Ubuntu, e so a cifra trafegou. Impressao digital
conferida nas duas pontas, par destruido. Esse e o caminho mais barato quando a credencial so
precisa chegar a Ubuntu: papel de nuvem puro nao toca claude_desktop_config.json, logo nao exige
fechar e reabrir o aplicativo. Gravada em ~/TransportMCP/.env, fora da pasta sincronizada.

## Manutencao de 23/10/2026 (turno do Kimi) e o que ela obriga a mudar no metodo

Relatado: faxina de apt, fwupd, flatpak e snap, com snapshot Timeshift 2026-10-23_00-41-17 antes;
Open WebUI recriado com imagem nova, volume preservado, porta 3000 para 8080; Ubuntu Pro ativado
(assinatura free personal, esm-apps, esm-infra e livepatch habilitados, confirmado por
`pro status`: attached True, os tres enabled); envs Python e demais containers inalterados por
desenho. E, o item que mexe com medicao, cinco modelos do Ollama re-baixados: qwen3:14b,
qwen3:30b-a3b, gemma4:12b, qwen2.5vl:7b e qwen3-embedding:4b. O qwen2.5-coder:14b-fast falhou o
re-pull como previsto, tag fora do registro, copia local intacta.

### PESO DE MODELO LOCAL PASSA A SER REGISTRADO PELO DIGEST, NAO PELA DATA

Problema: resultado de bateria deixa de ser comparavel quando o peso muda, e nada no arquivo de
resultado dizia qual peso tinha sido usado. Depois de um re-pull, um numero antigo que nao
reproduz parece regressao do modelo quando e so outro modelo.

Resolvido no bench, de forma automatica em vez de anotada a mao: `identidade_modelo()` consulta
/api/tags e grava o DIGEST curto em cada linha de resultado, no campo `pesos`, e a linha impressa
tambem o mostra. Para modelo de nuvem grava provedor e nome. Digest e melhor que data porque e a
identidade real: peso diferente, digest diferente, sem depender de fuso nem de quem anotou.

Digests em uso em 23/10/2026, apos o re-pull:
  qwen3:30b-a3b           ad815644918f
  qwen3:14b               bdbd181c33f2
  qwen2.5-coder:14b-fast  6253ba1a6b4e  (nao re-baixado, 5 semanas)

### O QUE ISSO INVALIDOU, CONFERIDO PELO HORARIO E NAO SUPOSTO

Os pesos foram modificados por volta de 00h45 de 23/10. Comparando com os arquivos de resultado:
  - auditoria com qwen3:30b-a3b, 22/10 as 19h44: pesos ANTERIORES, medicao limpa porem velha.
  - raciocinio com qwen3:30b-a3b, 23/10 as 00h45:04: NA FRONTEIRA, nao certificavel. O bench chama
    o Ollama com keep_alive de 30 minutos, e a instancia carregada em VRAM continua servindo
    mesmo com o manifesto trocado, entao a rodada provavelmente usou os pesos antigos de ponta a
    ponta; provavelmente nao e certificacao.
  - modelos de nuvem: nao afetados.
As duas linhas de base locais foram REFEITAS com os pesos novos, o que serve tambem de verificacao
de regressao do proprio re-pull.

### PROCEDIMENTO APROVADO: credencial cifrada pela maquina virtual da estacao

Quando a credencial so precisa chegar a Ubuntu, este e o caminho mais barato, e nao exige script
no Windows nem fechar o aplicativo:
  1. a Ubuntu gera par RSA 3072 efemero com permissao 600 e imprime apenas a chave publica;
  2. a maquina virtual Linux da estacao, que tem o pacote cryptography, le o arquivo de chave na
     pasta conectada e cifra com RSA-OAEP-SHA256 contra essa publica, imprimindo so a cifra em
     base64 e a impressao digital sha256 de 12 hex;
  3. a Ubuntu decifra, confere a impressao digital, grava em ~/TransportMCP/.env com permissao 600
     e destroi o par.
A chave em claro nunca existe fora das duas pontas. Para mais de uma credencial de uma vez, usar
envelope: AES-256-GCM nos dados e RSA-OAEP-SHA256 na chave simetrica, porque quatro credenciais
nao cabem numa unica cifragem RSA de 3072 bits.
Observacao de escopo: isso vale para papel de nuvem puro. Credencial que precisa entrar no bloco
`env` de um servidor MCP ainda exige o script no Windows com o aplicativo FECHADO, e o alvo e o
arquivo de %LOCALAPPDATA%\Claude-Data\claude_<sufixo>\, declarado em config_caminho.txt.

## Rodada de 23/10/2026 (noite): o Kimi entra atras do gateway, e um furo antigo do gateway

Decisao de Mateus: trazer o Kimi para tras do gateway, que e correcao de seguranca que se
sustenta sozinha, sem ainda criar papel titular.

### O FURO QUE EXISTIA, E QUE ERA MAIOR DO QUE PARECIA

O Kimi era alcancavel SO pelo servidor MCP kimi-assistant, fora de bin/llm.py. Logo nao tinha a
exigencia de autorizacao para saida de dado nem a recusa por orcamento de contexto, justamente
num servidor cujo nicho declarado e documento extenso, que e o pior lugar possivel para a segunda
trava faltar. A advertencia sobre dado de cliente existia em DOCSTRING, e docstring e aviso, nao
trava.

E ao fechar isso apareceu um furo que nao era do Kimi: O GATEWAY NUNCA TEVE A RECUSA POR
ORCAMENTO PARA PAPEL DE NUVEM. A verificacao existia apenas no ramo local; raciocinio-nuvem e
redacao-nuvem mandavam o insumo inteiro e deixavam o provedor cortar em silencio, e o Argon so
estava protegido porque bin/argon_core.py faz a sua propria conferencia. Corrigido em bin/llm.py:
papel de nuvem com ctx_max declarado agora recusa, com a estimativa pessimista de 2,5 caracteres
por token. Papel SEM ctx_max declarado nao e verificado, de proposito: contexto que nao foi
conferido na API nao entra como numero.

### O QUE A API DA MOONSHOT DISSE, MEDIDO EM 23/10/2026

GET /v1/models devolve muito mais que o padrao OpenAI, inclusive context_length e modalities:
  kimi-k3, kimi-k3.1-pro, kimi-k3.1-pro-highspeed .... contexto 1.048.576
  kimi-k2.6, kimi-k2.7-code, kimi-k2.7-code-highspeed  contexto   262.144
  todos aceitam texto, IMAGEM e VIDEO na entrada

Tres consequencias:
1. CONTEXTO IGUAL, NAO MAIOR. Um milhao e o MESMO do gemini-4-argon. Para documento longo de
   texto puro o Argon ja cobre, e um segundo caminho seria redundancia, nao capacidade.
2. O DIFERENCIAL REAL E A ENTRADA MULTIMODAL. Video na entrada nao existe em nenhum outro papel
   do ecossistema. Para consultoria de transportes isso aponta para contagem volumetrica em
   video, filmagem de campo e gravacao de travessia. O caminho do gateway hoje NAO monta mensagem
   multimodal, entao essa capacidade esta identificada e nao esta implementada.
3. O CATALOGO MUDOU EM DOIS DIAS. Em 21/10 a conta via quatro modelos; kimi-k3.1-pro e
   kimi-k3.1-pro-highspeed apareceram depois. Nenhum foi promovido: nao ha medicao.

### reasoning_effort: HONRADO, POReM NAO VALIDADO

Quatro repeticoes de cada, mesmo enunciado:
  low  4,2 s (3,3 a 5,7)  raciocinio   112 caracteres (61 a 161)   126 tokens de saida
  max 10,9 s (8,3 a 13,0) raciocinio 1.748 caracteres (1.171 a 2.221) 549 tokens de saida
Intervalos sem sobreposicao, logo o parametro e honrado, e 'low' custa 2,6 vezes menos tempo.

MAS A API ACEITA PARAMETRO E VALOR DESCONHECIDOS EM SILENCIO, com HTTP 200: tanto
reasoning_effort="valor_que_nao_existe" quanto um nome de parametro que eu inventei passaram.
Consequencia pratica: erro de digitacao no esforco NAO da erro, so cobra o padrao, que e max.
Por isso a validacao e LOCAL, em bin/llm.py e em kimi_server.py. Regra geral que isso confirma:
validar aqui o que o remoto nao valida, porque sondar nome de parametro por uma chamada nao
distingue "funcionou" de "foi ignorado". O teste que distingue e o valor invalido, e depois a
repeticao comparando o efeito.

A temperatura segue travada: a familia k3 recusa valor diferente de 1 com HTTP 400 explicito.
Esse campo e omitido para esses modelos, nos dois caminhos.

### O QUE ENTROU

bin/llm.py: provedor moonshot na tabela PROVEDORES_OPENAI, que passou de tupla a dicionario para
carregar as particularidades; omissao de temperatura por modelo; esforco validado localmente; e
diagnostico de resposta vazia com raciocinio cheio, que significa orcamento de saida gasto
pensando e nao modelo quebrado.
mcp/windows/kimi_server.py: funcao _conferir_saida com as duas travas, esforco repassado,
catalogo atualizado na mensagem de 404. EXIGE REINICIO do Claude Desktop para as assinaturas
novas das ferramentas (nao_sigiloso, esforco) aparecerem.
config/papeis.json: papel auditor-kimi como CANDIDATO, explicitamente nao titular, com o campo
teste dizendo que nao foi medido e por que a medicao hoje nao decidiria.

### HIPOTESE A TESTAR, DE UMA AMOSTRA SO

No mesmo material de dimensionamento de frota, o Kimi apontou OS MESMOS tres defeitos que o
Argon havia apontado: amostra de tamanho um, ausencia de tempo de terminal e arredondamento para
baixo. Se isso se repetir, a tese de que um auditor de linhagem diferente traz falha
complementar ENFRAQUECE, e o segundo auditor passa a ser eco caro em vez de informacao. E
amostra de um, nao conclusao, e e exatamente o que a suite de auditoria mais dificil tera de
medir. Enquanto a suite estiver no teto, essa pergunta fica aberta.

### ESPELHO NAO E PRODUCAO (23/10/2026, erro meu, segunda vez na mesma semana)

A pasta mcp/windows/ do ecossistema e ESPELHO DE VERSIONAMENTO, nao o codigo que roda. Os
servidores sao lancados de C:\TransportMCP e D:\TransportMCP, declarados nos args do
claude_desktop_config.json. Editar o espelho versiona a correcao e NAO a coloca no ar: o
Syncthing leva o arquivo para C:\Users\mateu\ecossistema, que e outro caminho.
Aconteceu com o kimi_server.py: as travas foram escritas, commitadas e nao estavam valendo, e so
apareceu porque o esquema da ferramenta continuou sem os parametros novos depois do reinicio.
E a MESMA classe de erro do claude_desktop_config.json de 22/10: eu editei o arquivo errado,
sem erro nenhum aparecer, so sem efeito.
UNICA EXCECAO: argon_mcp.py roda da copia sincronizada, porque foi configurado assim de
proposito. Nele, editar na Ubuntu e reiniciar basta.
REGRA: depois de alterar servidor MCP, conferir o arquivo que o config aponta, nao o espelho, e
confirmar pelo ESQUEMA da ferramenta apos o reinicio, que e a unica prova de que a versao nova
subiu.

### COMPARAR ARQUIVO ENTRE MAQUINAS EXIGE NORMALIZAR FIM DE LINHA

Na mesma varredura, o tomtom_network_server.py apareceu como divergente entre espelho e
producao. Era falso: 341 linhas "diferentes" e exatamente 341 bytes de diferenca, ou seja, CRLF
contra LF, conteudo identico. A propria instrucao ja avisava disso e eu comparei sha256 cru
assim mesmo. Varredura de divergencia normaliza antes: tr -d '\r' e corte de espaco a direita,
e so entao o hash.
Resultado da varredura normalizada de 23/10: todos os servidores iguais entre espelho e
producao, exceto o kimi_server.py, corrigido nas duas pastas.

### PENDENCIA ESTRUTURAL IDENTIFICADA

Enquanto os servidores rodarem de C:\TransportMCP e D:\TransportMCP, toda correcao exige copia
manual e a divergencia pode voltar. Apontar todos para a copia sincronizada do ecossistema, como
ja e feito com o argon-auditor, elimina a classe de erro: edita-se na Ubuntu, o Syncthing
propaga, reinicia. Exige uma edicao do config com o aplicativo FECHADO. Nao feito ainda.


================================================================================
24/10 - CLAUDE CODE DA UBUNTU EQUIPADO COM OS SERVIDORES DO ECOSSISTEMA
================================================================================

O PROBLEMA QUE ISSO RESOLVE. A regra de auditoria independente exige acionar o
argon-auditor antes de fechar entregavel. Mas o lugar designado para TAREFA LONGA e o
Claude Code instalado na Ubuntu, e ele nao tinha o argon-auditor declarado. Ou seja, o
unico lugar que roda bateria, exportacao e lote era justamente o que nao podia auditar
o proprio resultado. Contradicao fechada agora.

O QUE ELE JA TINHA, e eu afirmei errado que nao tinha. O Claude Code da Ubuntu ja estava
conectado a transport-modeling, assistente-juridico, perplexity e memory, no escopo user,
mais os conectores da conta (Docs, Drive, Sheets, Slides, Gmail, Calendar, BigQuery,
Notion, Gamma, Composio, Adobe). Eu disse que ele era mal equipado porque meu
`claude mcp list | head -20` cortou a lista antes dos locais. Ele e mal equipado nos
servidores DO ECOSSISTEMA, que e outra afirmacao.

DECLARADOS EM 24/10, escopo user, ambos Connected e provados por chamada real:
  argon-auditor    mcp_local.sh argon_mcp.py, com ARGON_CORE e ARGON_MODELO por -e
  kimi-assistant   mcp_local.sh kimi_server.py

O ollama-remote NAO vai para la, de proposito: ele e a ponte PARA a Ubuntu, e o Claude
Code ja esta dentro dela, com shell. Declarar seria a maquina falando com ela mesma.

bin/mcp_local.sh, E POR QUE ELE EXISTE. O `claude mcp add` aceita -e CHAVE=valor, mas isso
gravaria a credencial em texto puro em ~/.claude.json, que nao tem permissao 600. Seria a
quinta copia de cada chave e multiplicaria o trabalho de rotacao. O involucro carrega
~/TransportMCP/.env (600, fora do versionamento e do Syncthing) e passa o controle ao
servidor. O arquivo nao contem credencial e por isso e versionado. Conferido: o campo
Environment do kimi-assistant esta VAZIO em ~/.claude.json.

INTERPRETADOR. O Claude Code usa ~/TransportMCP/.venv/bin/python, que ja tinha
mcp 1.29.0 e fastmcp 3.4.7. Faltava google-genai, que o argon_core carrega de forma
preguicosa: por isso o modulo importava sem erro e so a chamada falharia. Instalado
2.33.0. ERRO MEU no caminho: rodei o primeiro `pip install` no ~/env_transporte, que nao
e o ambiente de producao do Claude Code. Mesma classe do erro de editar o espelho em vez
da producao. Antes de instalar, conferir QUAL interpretador o alvo usa.

RISCO ABERTO, mcp 2.x DERRUBA OS NOVE SERVIDORES. Um `pip install mcp` sem restricao traz
o mcp 2.x, onde FastMCP foi renomeado para MCPServer e mcp.server.fastmcp deixou de
existir. Os nove servidores usam FastMCP. Hoje nada fixa a versao em nenhuma das duas
maquinas. Enquanto nao houver arquivo de restricao, NUNCA rodar `pip install -U mcp` nem
`pip install mcp` sem `"mcp<2"` nos ambientes de producao. Versoes medidas em 24/10 estao
em config/versoes_criticas.txt.

DIVERGENCIA DE VERSAO ENTRE AS MAQUINAS. google-genai 2.33.0 na Ubuntu contra 2.32.0 no
Windows. O singleton de cliente do argon_core continua correto nas duas, porque o
problema do transporte HTTP compartilhado nao depende da versao menor, mas o mesmo codigo
rodando contra versoes diferentes e como comparar ferramenta sem equalizar condicao: se
o comportamento divergir, a causa fica ambigua.

CONNECTED NAO E PROVA DE CREDENCIAL. O `claude mcp get` diz Connected quando o servidor
sobe e lista ferramentas. Nao diz que a chave resolve, porque a chave so e lida na
chamada. Mesma estrutura do erro de tomar ausencia de vazamento por prova de censura.
Prova aceita: chamada real pelo proprio Claude Code, em segundo plano com nohup setsid
porque chamada de modelo estoura o corte de 60 s da ponte.
  argon_diagnostico   GEMINI_API_KEY presente, digital 6f815a1c6ee5, gemini-4-argon na
                      chave, 46 modelos com generateContent
  consultar_kimi      devolveu PONTE OK com nao_sigiloso=true
  argon_fiscalizar_codigo  parecer real em 14,1 s sobre rotina BPR plantada: achou a
                      media de razoes, achou capacidade nula, e classificou alfa/beta
                      fixos como SUSPEITA e nao como defeito, que e o comportamento
                      calibrado que a bateria mediu

AUTORIZACAO DE FERRAMENTA NO MODO -p. `claude -p "<pedido>" --allowedTools
"mcp__<servidor>__<ferramenta>"`. Sem isso o modo nao interativo nao chama a ferramenta
e devolve texto sem ter feito nada, que e falso negativo silencioso.

PENDENTE. here-network, google-maps e tomtom-transport ainda nao declarados la: as tres
chaves de rede nao estao na Ubuntu. Transporte pelo caminho aprovado de credencial
cifrada, par RSA-3072 efemero gerado NA UBUNTU com a privada nunca saindo de lá,
executavel D:\95 - TEMP\rede_cifrar.bat.


================================================================================
24/10 - CLAUDE SCIENCE NO ECOSSISTEMA, E A TRAVA QUE O TORNA USAVEL
================================================================================

O FATO QUE DECIDE TUDO. O Claude Science e daemon local, sandbox local de execucao de
codigo e MODELO REMOTO. Nao ha engine local: o help nao oferece modelo proprio, nem modo
offline, nem pin de engine, e ele exige login na Anthropic. Logo, o que ele LE sai da
maquina.

A FALACIA A EVITAR. "Roda local, logo protege dado sob NDA" e falso, e e a mesma falacia
que ja esta registrada aqui: o que protege nao e rodar local, e o modelo nao alcancar o
microdado. Pior, num aspecto ele e MAIS FROUXO que um script: script tem escopo fixo, le
a base inteira e devolve tres numeros; o Claude Science da ao modelo acesso de leitura
DISCRICIONARIO, e a decisao sobre o que sai passa a ser do modelo a cada passo.

O QUE SALVA O ARRANJO, e e verificado no help do serve, nao suposto: "outbound network
hosts and host files need your approval, an approval card in the UI, before Claude can
reach them". A contencao e ESTRUTURAL e POR CAMINHO, nao disciplinar. Arquivo nao
aprovado e inalcancavel; rede nao aprovada tambem.

PROTOCOLO ADOTADO (decisao do Mateus em 24/10): dado de cliente E permitido, com a regra
de que o modelo so le agregado produzido antes por rotina local, nunca o microdado.
  1. ~/ciencia/<projeto>/ e a UNICA arvore que recebe cartao de aprovacao.
  2. NUNCA aprovar caminho acima dela. Aprovar $HOME uma vez anula o protocolo inteiro.
     Este e o unico ponto de disciplina, e e UMA decisao, nao uma por analise.
  3. O microdado fica onde sempre esteve, fora dali, e nunca e aprovado.
  4. Nada entra a mao. Entra por bin/ciencia_liberar.py.
  5. Entregavel que usar material dali cita o manifesto da liberacao.

bin/ciencia_liberar.py, A TRAVA. Recebe --origem (microdado), --candidato (agregado) e
--projeto; copia para ~/ciencia/<projeto>/ so se passar, e RECUSA em vez de avisar:
  nome de coluna identificador (lista explicita, nao heuristica de prefixo)
  coluna de texto com alta unicidade e comprimento tipico de nome ou endereco, que pega
    o caso em que o nome da coluna e inocente
  candidato nao suficientemente menor que a origem, que pega copia disfarcada de agregado
  celula de contagem abaixo de 5, por controle de divulgacao estatistica
  candidato que ja esteja dentro de ~/ciencia antes de passar pela trava
Todo resultado, liberado ou nao, vai para ~/ciencia/_manifestos/ com sha256 da origem e do
candidato, contagens, colunas e os motivos. --forcar "<justificativa>" libera com as
recusas registradas, e a justificativa tem de ser citada no entregavel.

MEDICAO DA TRAVA, 24/10: bateria sintetica de 7 casos, 7/7 conforme esperado, com as duas
metades presentes (5 defeitos plantados detectados, 2 controles corretos liberados).

DEFEITO ENCONTRADO E CORRIGIDO NA PROPRIA BATERIA. A primeira versao nomeava o manifesto
so com horario em segundos mais o nome do candidato: duas decisoes sobre o mesmo arquivo
no mesmo segundo se sobrescreviam EM SILENCIO, perdendo registro de auditoria sem erro
nenhum. So apareceu porque a bateria conferiu a CONTAGEM de manifestos contra a de casos
(6 para 7), e nao apenas o conteudo do ultimo. Corrigido com sufixo sequencial e provado
com tres execucoes no mesmo segundo gerando tres manifestos. Licoes: conferir contagem e
nao so conteudo; e compilar nao e funcionar.

PENDENTE E NAO VERIFICADO. O cache de conectores do Claude Science lista apenas conectores
de nuvem do diretorio (Adobe, Claude Docs, COMPOSIO, Gamma, BigQuery, Drive, Notion,
Gmail, Calendar, visualize). Nao encontrei suporte a servidor MCP stdio local neste build
(0.1.70), e a rota que responderia isso, mcp-env-check, devolve HTTP 401 quando chamada
pelo shell, porque exige o token da sessao do navegador. Nao afirmar que os servidores do
ecossistema estao disponiveis la ate isso ser verificado na interface.
Tambem anotado: daemon.engine.prefetch em estado failed, sem efeito observado ainda.

LISTA DE FERRAMENTAS PROXIADAS DEPOIS DE REINICIAR O CLAUDE DESKTOP. Logo apos o
reinicio, servidores podem aparecer como desconectados na lista de ferramentas enquanto
get_device_info ja os mostra como announced: a lista foi calculada antes de o handshake
terminar. Reconsultar com RefreshMcpTools antes de concluir que um servidor caiu. Ocorrido
em 24/10 com argon-auditor e tomtom-transport, e resolvido pela reconsulta, sem nenhuma
intervencao.


================================================================================
24/10 - AS TRES CHAVES DE REDE NA UBUNTU, E O CLAUDE SCIENCE POR DENTRO
================================================================================

TRANSFERENCIA CONCLUIDA. HERE_API_KEY, GOOGLE_MAPS_API_KEY e TOMTOM_API_KEY entraram em
~/TransportMCP/.env (600, nove chaves agora) pelo caminho aprovado: par RSA-3072 efemero
gerado NA UBUNTU, privada nunca saiu de la, cifragem no Windows, envelope conferido por
sha256 na transferencia, digitais conferidas nas duas pontas contra a rotacao de 22/10, e
par efemero destruido. Nenhum valor de chave trafegou pelo chat nem foi impresso.

SEIS SERVIDORES DO ECOSSISTEMA NO CLAUDE CODE DA UBUNTU, todos escopo user, todos com
Environment VAZIO em ~/.claude.json porque as chaves vem do involucro bin/mcp_local.sh:
argon-auditor, kimi-assistant, here-network, google-maps, tomtom-transport, e o
transport-modeling que ja existia. Provados por chamada real, nao por Connected:
geocodificar_here e geocodificar_google devolveram o mesmo eixo de via com cerca de 90 m
entre os centros geometricos, e obter_coordenadas_polos_salvador devolveu os 8 polos.

ERRO MEU NO CAMINHO, E A LICAO. A primeira versao do executavel de cifragem abortou com
"a publica embutida nao bate com a declarada". O guarda estava certo, o numero declarado
e que estava errado: eu calculei o sha256 sobre os BYTES do PEM na Ubuntu, que terminam
com salto de linha, e transcrevi o PEM para um literal no script sem esse salto. Mesma
classe do CRLF contra LF. Provado, nao suposto: o sha do PEM sem o salto final e
exatamente o ec46ddc9b6b739cc que o Windows viu.
REGRA: nunca comparar impressao digital de TEXTO transcrito entre maquinas. Para chave
publica, comparar o sha256 do DER da chave CARREGADA, que e canonico e imune a fim de
linha, a salto final e a espaco em branco.

================================ CLAUDE SCIENCE =================================

VERIFICADO NO BANCO, nao suposto. O build 0.1.70 guarda estado em
~/.claude-science/orgs/<org>/operon-cli.db, 67 tabelas.

SERVIDOR MCP PROPRIO SO POR HTTP. A tabela custom_mcp_servers tem url NOT NULL, transport,
oauth_server_url, client_id, scopes, headers_helper, e NAO tem coluna de comando nem de
argumentos. Logo stdio nao e representavel: os nove servidores do ecossistema, que sao
todos stdio, NAO podem ser declarados la sem uma ponte HTTP. Hoje a tabela tem 0 linhas.
O Claude Science traz 17 servidores locais proprios, todos de biologia e quimica
(_mcp-genomes, _mcp-variants, _mcp-literature, _mcp-chemistry e afins), mais um
__byoc_helper__.

CONCESSAO DE PASTA, estado ambiguo e NAO resolvido. A tabela host_grants esta VAZIA, mas
~/.claude-science/sandbox-grant-scans.json guarda um registro de
/media/mateus/DADOS_01/12 - LOGISTICA/ECOPLAN_CORREDORES, writable true, 279 arquivos
varridos, seenAt 24/10 00:08:13Z, que e o instante de arranque do daemon. host_call_log
tem 2374 chamadas, mas a ultima e de 16/09. Leitura mais provavel: o JSON e cache de uma
varredura antiga e nao ha concessao persistente ativa. NAO AFIRMAR isso sem conferir na
interface: as duas fontes discordam e so a interface desempata.

ERRO MEU: afirmei que directory_attachments guardava as pastas anexadas. Nao guarda. O
esquema e (server_uuid, agent_name, user_id, excluded_tools): e atribuicao de servidor
MCP a agente. Palpite sobre nome de tabela nao e leitura de esquema.

ONDE PROCURAR NA INTERFACE. Nao existe "Customize" na tela inicial do Claude Science, que
so tem Projects e Recent sessions. O controle de permissoes vive dentro de um projeto ou
sessao, e as concessoes aparecem como cartao de aprovacao no momento em que o modelo pede
o arquivo ou o host.

O CLAUDE SCIENCE JA ESTAVA EM USO, o que muda a ordem das coisas. Cinco projetos
(ECOPLAN Logistica, Nino, Marco Legal, PD MODOS URBANOS, PD Rodovias), 199 frames, 8278
mensagens, sessoes de agosto e setembro. O protocolo de ~/ciencia pressupoe comeco do
zero e o historico nao esta no zero: material de cliente ja passou por la antes de o
protocolo existir. O protocolo vale dali para a frente; o passado e passado e nao se
reescreve.


================================================================================
24/10 - DUAS DECISOES SOBRE O CLAUDE SCIENCE
================================================================================

1. SEM PONTE HTTP POR ENQUANTO. Servidor MCP proprio no Claude Science so por HTTP
(custom_mcp_servers tem url NOT NULL e nenhuma coluna de comando), e os nossos nove sao
stdio. Construir a ponte custaria um servico novo sempre no ar, com autenticacao e mais
uma superficie para manter, para um ganho pequeno: quando faltar HERE, Google, TomTom ou
Argon numa analise, o pedido vai para o chat ou para o Claude Code, que ja os tem.
Reavaliar quando aparecer um caso concreto em que a falta doa, e nao no abstrato.

2. O CRITERIO DE FRONTEIRA E "CONTEM REGISTRO INDIVIDUAL", NAO "E DE CLIENTE". Acervo de
cliente publico ou ja agregado (fluxo de carga, PNL, matriz OD consolidada, documento de
contrato, saida de simulacao) pode receber cartao de aprovacao direto. Pesquisa bruta,
cadastro e microdado, nao. A formulacao importa: "e de cliente" seria juizo caso a caso, e
juizo caso a caso e regra descumprida de rotina; "contem registro individual" e conferivel
por rotina.

A ROTINA QUE TORNA O ITEM 2 ESTRUTURAL. bin/ciencia_liberar.py ganhou o modo
  --varrer <pasta>
que confere uma pasta ANTES de ela receber cartao de aprovacao. Le so o cabecalho de cada
tabela e devolve nome de arquivo e tipo de marca, nunca nome de coluna nem valor, para a
propria conferencia nao virar vazamento. Codigo 0 libera a concessao, 1 significa nao
conceder. Medido em caso sintetico: pasta limpa 0 marcas codigo 0, pasta suja 2 marcas
codigo 1, pegando tanto a coluna identificadora quanto o texto livre em coluna de nome
inocente.
LIMITE DECLARADO, e que nao deve ser esquecido ao citar: so examina tabela. PDF, DOCX,
shapefile e imagem nao sao examinados, e ausencia de marca nao e atestado sobre eles.

NOTA SOBRE O REGISTRO DE VARREDURA DO PROPRIO CLAUDE SCIENCE, corrigida pelo Mateus.
O sandbox-grant-scans.json declara listed 279 para a pasta ECOPLAN_CORREDORES, que hoje
tem 2549 arquivos. Eu levantei duas hipoteses, varredura truncada ou contagem de outra
coisa, e as duas estavam erradas. A varredura foi feita para um projeto especifico, na
epoca, e a pasta cresceu desde entao.

O QUE FICA DISSO, e e o util. No mesmo registro convivem complete true, wasComplete true,
listed 279 e seenAt 24/10 00:08:13Z, que e o arranque do daemon de hoje. Ou seja, o seenAt
e reaproveitado no arranque enquanto o listed permanece do levantamento original: OS DOIS
CAMPOS ENVELHECEM EM RITMOS DIFERENTES. Ler o par como retrato do mesmo instante induz ao
erro que eu cometi. Para saber o que esta concedido agora, a fonte e a interface, nao este
arquivo.


================================================================================
24/10 - O DETECTOR DA TRAVA REPROVADO PELA PRIMEIRA VARREDURA REAL
================================================================================

O QUE ACONTECEU. A primeira varredura real, no acervo ECOPLAN_CORREDORES, 2549 arquivos e
563 tabelas, marcou 122 arquivos. Inspecionada a amostra de 40 que o relatorio mostra: 36
vinham so de "texto livre de alta unicidade", e os 4 acertos ditos fortes foram disparados
por colunas chamadas 'nome', que ali sao nome de via, de municipio e de terminal.

O DIAGNOSTICO, E ELE E DE METODO. A lista de identificadores fora escrita para microdado
de pesquisa domiciliar e foi aplicada a dado de rede e logistica. Isso e TRANSPOSICAO DE
PARAMETRO ENTRE CONTEXTOS, que e um dos gatilhos de contraditorio da nossa propria regra,
e eu cai nele ao escrever o detector. Guarda que marca quase tudo numa pasta legitima e
guarda que passa a ser ignorada: a mesma falha de regra descumprida de rotina, so que em
forma de detector.

A CORRECAO, EM DOIS NIVEIS.
  FORTE, bloqueia: cpf, rg, titulo_eleitor, prontuario, email, telefone, celular,
    whatsapp, numero_casa, complemento, matricula, respondente, entrevistado,
    nome_entrevistado e irmaos, lat_domicilio, lon_domicilio, id_pessoa, id_individuo.
    Campos sem leitura inocente em dado de transporte.
  FRACO, so reporta: nome, sobrenome, cnpj, documento, endereco, logradouro, cep,
    cadastro, motorista, placa, chassi. Em transporte e logistica aparecem o tempo todo
    com sentido nao pessoal.
  TEXTO LIVRE passa a exigir CORROBORACAO: alta unicidade sozinha pega titulo de
    documento, citacao bibliografica, nome de trecho e prompt. So vira bloqueio se o
    proprio texto trouxer email, telefone, CPF ou endereco urbano (rua, avenida, travessa,
    alameda, praca seguidos de numero). 'rodovia' e 'estrada' ficam FORA de proposito: em
    dado de transporte sao o assunto, nao o identificador.

ASSIMETRIA DELIBERADA ENTRE AS DUAS PORTAS, com razao declarada. --varrer olha pasta que
pode nao ter nada de pessoal e usa so o nivel FORTE. --origem/--candidato olha agregado
DERIVADO DE MICRODADO, onde 'nome' quase certamente e pessoa, e usa FORTE mais FRACO. A
probabilidade a priori e diferente por construcao, entao o limiar tem de ser diferente;
limiar unico daria ou ruido na pasta ou buraco no agregado.

MEDICAO APOS A CORRECAO: 8 de 8 casos, cobrindo as duas portas. Na porta de arquivo,
'nome' e 'endereco' continuam bloqueando, e o agregado legitimo continua passando. Na
porta de pasta, pasta de rede viaria mais bibliografia passa com 0 bloqueios e 2 avisos,
e pasta com endereco dentro de texto livre bloqueia.

LIMITES QUE CONTINUAM VALENDO. So examina tabela: PDF, DOCX, shapefile e imagem nao sao
examinados, e ausencia de marca nao e atestado sobre eles. Na primeira varredura real
houve ainda 126 arquivos ilegiveis, que sao buraco silencioso e nao ausencia de marca.


================================================================================
24/10 - CREDENCIAL DENTRO DA PASTA SINCRONIZADA
================================================================================

O ACHADO. ~/ecossistema/.env existia com MANUS_API_KEY, NGC_API_KEY e NVIDIA_API_KEY, modo
600 AQUI, e a pasta e sendonly do Syncthing para Duebendorf, fedora e vivobook-go. Logo as
chaves estavam replicadas em tres outras maquinas, uma delas portatil, com a permissao e a
cifragem de disco que aquelas maquinas tiverem. Confirmado por verificacao e nao por
suposicao: C:\Users\mateu\ecossistema\.env existia, 279 bytes, igual ao original.

AUTOCRITICA, E E A PARTE QUE IMPORTA. O bin/llm.py JA AVISAVA, na mensagem de erro, que
~/ecossistema/.env e sincronizado para quatro dispositivos. O risco estava escrito dentro
do proprio codigo e nunca foi consertado. AVISO EM MENSAGEM DE ERRO NAO E GUARDA: so e
lido por quem ja errou, e nao impede nada. Pior, a ordem de busca preferia RAIZ/.env, ou
seja, o arquivo EXPOSTO era o que vencia.

O QUE FOI FEITO.
  1. Ordem de busca invertida em bin/llm.py e bin/argon_core.py: ~/TransportMCP/.env, que
     NAO e sincronizado, passa a vir primeiro.
  2. bin/manus_export.py ganhou queda. Ele lia SOMENTE ~/ecossistema/.env, sem alternativa,
     e era o unico consumidor que travava a remocao do arquivo.
  3. Precedencia provada com sentinela em HOME falso, 4 de 4, mais prova de que a queda ao
     ~/ecossistema/.env continua funcionando quando a variavel so existe la.
  4. ~/ecossistema/.env REMOVIDO. As tres chaves ja estavam em ~/TransportMCP/.env com as
     mesmas digitais, entao nao houve perda. Conferido depois: llm.chave_env e
     argon_core.chave() seguem achando tudo.

A ORDEM DAS OPERACOES E CONTRAINTUITIVA E E O PONTO CENTRAL. O Syncthing PROPAGA EXCLUSAO,
mas NAO sincroniza arquivo ignorado, nem para apagar. Entao:
  APAGAR PRIMEIRO, e so DEPOIS gravar o .stignore.
Invertido, o arquivo congela no destino e fica la para sempre. Gravar .stignore antes de a
exclusao chegar em todos os dispositivos e o erro a evitar.

ESTADO EM 24/10, incompleto de proposito, e pior do que "offline no momento".
  Duebendorf  exclusao CHEGOU, conferida pela ponte: o .env nao esta mais la.
  Zurich      (antigo 'fedora', renomeado a pedido do Mateus em 24/10)
              NAO SINCRONIZA HA 20 DIAS: visto por ultimo em 04/10, 69,9% completo,
              655 itens pendentes. Ainda tem a copia do .env.
  vivobook-go idem: visto por ultimo em 04/10, 655 itens pendentes.
  .stignore   AINDA NAO GRAVADO, de proposito, para nao congelar a copia nos dois.

DIAGNOSTICO DA DESCONEXAO, com uma hipotese ja falseada. O Zurich tinha endereco FIXO num
IP do Tailscale (tcp://100.89.23.85:22000), e levantei a hipotese de que o IP tivesse
mudado. Acrescentei 'dynamic' ao lado do fixo e observei: a descoberta devolve ZERO
anuncios daquele dispositivo. Se o Syncthing dele estivesse no ar com rota de saida, ele
apareceria na descoberta mesmo sem rota direta. Hipotese do endereco FALSEADA; o endereco
alternativo fica porque e inocuo. Sobra a explicacao simples: o Syncthing daquela maquina
nao esta rodando, ou ela nao tem rota. Maquina ligada nao e Syncthing no ar.

CONSEQUENCIA QUE NAO DEVE SER ESQUECIDA. Aquelas duas maquinas tem uma copia do ecossistema
de 20 dias atras, nao so o .env. Quando reconectarem, recebem 655 itens de uma vez, e so
entao a exclusao da credencial chega.
Enquanto os dois nao conectarem e receberem a exclusao, as duas chaves continuam naquelas
maquinas. Apagar na origem reduz a exposicao futura; so a ROTACAO mata a exposicao que ja
existe. Decisao pendente do Mateus.


================================================================================
24/10 - O PINO DO mcp DEIXA DE SER ANOTACAO E VIRA TRAVA
================================================================================

O MECANISMO. config/restricoes_pip.txt, versionado e sincronizado, contem `mcp<2`. Cada
ambiente de producao declara esse arquivo em install.constraint na configuracao do proprio
pip, de modo que ele e lido em TODA instalacao daquele interpretador, inclusive num
`pip install -U mcp` distraido. Anotacao em arquivo de texto nao impedia nada; isto impede.
  Ubuntu   ~/TransportMCP/.venv/pip.conf
  Windows  C:\TransportMCP\.venv\pip.ini e D:\TransportMCP\.venv\pip.ini

PROVA POR DIFERENCA, na Ubuntu, com --dry-run:
  com a trava   Would install mcp-1.30.0
  sem a trava   Would install mcp-2.3.0 httpx2-2.16.0 httpcore2-2.16.0 mcp-types-2.3.0
Ou seja, a afirmacao de que um upgrade sem restricao derruba os nove servidores estava
certa, e agora esta medida e nao suposta.

MODO DE FALHA, DECLARADO. Se o arquivo de restricao sumir, o pip passa a RECUSAR qualquer
instalacao naquele ambiente, com erro claro. E falha fechada de proposito: melhor recusar
a instalar do que subir a versao que derruba tudo. Para desfazer, apagar o pip.conf ou o
pip.ini; nada mais depende deles.

DOIS ERROS MEUS NO CAMINHO, e o segundo e o grave.

1. TESTEI A TRAVA COM O COMANDO REAL, EM PRODUCAO. Rodei `pip install -U mcp` de verdade
   para ver se a trava segurava. Ela segurou, mas o comando MUDOU O ESTADO: o mcp saiu de
   1.29.0 para 1.30.0 e quebrou a paridade com o Windows. Restaurado para 1.29.0 e os
   cinco servidores reconferidos. Para testar guarda existe --dry-run. Testar com a acao
   de verdade em producao e o tipo de premissa que eu critico nos outros.

2. O MEU BRACO DE CONTROLE NAO ERA CONTROLE. Para medir "o que aconteceria sem a trava" eu
   passei --constraint /dev/null, supondo que a linha de comando SUBSTITUI a configuracao.
   Ela nao substitui: o pip SOMA os arquivos de restricao. O braco "sem trava" estava com
   a trava ativa o tempo todo, devolveu mcp-1.30.0, e eu quase conclui que o risco que eu
   mesmo havia levantado era falso.
   O jeito correto de ignorar a configuracao e PIP_CONFIG_FILE=/dev/null.
   LICAO QUE GENERALIZA: isto e comparacao com condicoes NAO equalizadas, que ja esta na
   lista de gatilhos do contraditorio deste arquivo por causa de cuOpt contra OR-Tools.
   Antes de ler qualquer diferenca, conferir que o braco de controle e mesmo controle.

PENDENTE E EXPLICITAMENTE NAO PROVADO. No Windows o pip.ini foi ESCRITO nos dois ambientes
pela ponte, mas NAO foi testado la: a prova exige rodar pip naquela maquina. Ate que isso
aconteca, a trava do Windows esta declarada e nao verificada, e nao deve ser citada como
verificada.


================================================================================
24/10 - IDENTIDADE DO SYNCTHING RECRIADA, E O .stignore FINALMENTE GRAVADO
================================================================================

A DESCOBERTA QUE MUDOU O PLANO. O Mateus ligou o portatil 'fedora' (renomeado para
'Zurich' a pedido dele) e o Syncthing la nao conectava. A sequencia de diagnostico, cada
passo descartando uma hipotese:
  1. Ping no IP do Tailscale: responde, 0% de perda. Rota existe.
  2. Porta 22000: "Connection refused", nao tempo esgotado. Firewall DESCARTA e da tempo
     esgotado; RECUSADA significa maquina viva sem ninguem escutando. Hipotese de rede
     descartada.
  3. systemctl --user status syncthing no Zurich: inactive (dead) e disabled. Era isso.
     Janela aberta nao e servico rodando.
  4. Depois de `systemctl --user enable --now syncthing`, ainda nao conectava, mas o log
     daqui passou a registrar conexoes recusadas vindas daquele IP com um identificador
     DIFERENTE do cadastrado: BY6KN7X no lugar de SV2VXF5.

IDENTIDADE RECRIADA, E A CONSEQUENCIA E GRAVE PARA O PLANO ANTERIOR. Configuracao e
certificado daquele Syncthing foram refeitos (instalacao limpa, pasta de configuracao
apagada ou outro usuario). Quando isso acontece, O VINCULO QUE CARREGARIA A EXCLUSAO
DEIXA DE EXISTIR: esperar que a remocao do .env "chegue" e esperar por algo que nunca vai
ocorrer, porque nao ha mais par. A espera prudente vira espera inutil.
Por isso o plano mudou: APAGAR A MAO na maquina de destino e gravar o .stignore, em vez de
aguardar propagacao. Vale para o vivobook-go, que esta desligado ha 5 dias no Tailscale e
sem sincronizar ha 20, e que e candidato ao mesmo problema.

RE-PAREAMENTO, decidido pelo Mateus. Cadastro morto SV2VXF5 removido, identidade nova
BY6KN7X cadastrada como 'Zurich' com 'dynamic' ao lado do IP fixo, pasta compartilhada.
Conectou e fechou 100% com 0 itens pendentes em cerca de 25 s, o que confirma que os
arquivos ja estavam no disco dele e o Syncthing novo apenas os reconheceu.

.stignore GRAVADO E PROVADO. 13 padroes: credencial (.env, .env.*, *.pem, *.key, *.p12,
*_key.txt, *_token.txt) e lixo de execucao espelhando as exclusoes do .gitignore (cache,
__pycache__, *.log, *.tmp, bench/imagens, bench/dados). O criterio fica facil de lembrar:
o que nao e versionado nao e replicado.
PROVA, e nao suposicao: criei um .env sintetico na pasta, forcei varredura, e o indice
global continuou com o arquivo deletado e tamanho 0, ou seja, ele nao entrou. Arquivo de
teste removido em seguida.
O .stignore NAO e sincronizado entre dispositivos; cada maquina tem o seu. Como esta e a
origem sendonly, ignorar aqui basta para o arquivo nunca mais sair.

ZURICH CONFERIDO E ENCERRADO, em 24/10 14:18, com as tres checagens que importavam:
  ls ~/ecossistema/CLAUDE.md   existe, com data do dia: a pasta sincronizada E aquela,
                               logo "o .env nao existe" significa APAGADO e nao caminho
                               errado. Descartar esse "nao existe" ambiguo foi necessario:
                               arquivo ausente e o que se ve tambem quando se olha o lugar
                               errado.
  find ~ -maxdepth 5 -name .env   NADA. Nenhuma copia esquecida em outro canto da pasta
                               pessoal, que era a hipotese aberta depois da identidade
                               recriada.
  loginctl ... Linger          yes. O servico de usuario sobrevive ao logout, senao o
                               Syncthing morreria ao deslogar e voltariamos ao problema de
                               hoje sem ninguem perceber.
Estado pelo lado de ca: conectado, 100%, 0 itens pendentes, 0 erros, .env deletado no
indice global.

PENDENTE, apenas um.
  vivobook-go  desligado ha 5 dias no Tailscale, sem sincronizar ha 20. Ao ligar: conferir
               se o Syncthing dele subiu (pode estar disabled como o Zurich estava),
               conferir se a identidade tambem foi recriada, e apagar ~/ecossistema/.env a
               mao em vez de esperar propagacao.


================================================================================
24/10 - A FAXINA DE CREDENCIAL ERROU PARA O LADO PERMISSIVO, E FOI CORRIGIDA
================================================================================

O DEFEITO. A primeira versao de bin/chaves_faxina classificava como credencial TODO valor
do bloco env com 16 caracteres ou mais. Na execucao real, isso preservou o
claude_desktop_config.json antigo, que carrega as chaves da rotacao passada em texto puro,
porque ele coincidia com a configuracao viva em CROSSREF_MAILTO, MEMORY_FILE_PATH,
SSH_KEY_PATH, OLLAMA_HOST, UBUNTU_JOBS_DIR, UBUNTU_CUOPT_PY e UBUNTU_ECOSSISTEMA. Nenhum
deles e credencial: sao caminhos, uma URL e um e-mail.

POR QUE ISTO E GRAVE E NAO COSMETICO. O guarda errou para o lado PERMISSIVO: manteve um
arquivo que devia apagar. Guarda que erra para o lado restritivo gera ruido e irritacao;
guarda que erra para o lado permissivo gera falsa seguranca, que e pior, porque o
relatorio diz "mantido porque contem credencial em uso" e a pessoa acredita.

MESMA CLASSE DO DEFEITO DO DETECTOR DO ECOPLAN, no mesmo dia. Nos dois casos eu classifiquei
pela propriedade FACIL DE MEDIR em vez da propriedade que IMPORTA: la, unicidade de texto
no lugar de "contem registro individual"; aqui, tamanho do valor no lugar de "e credencial".
REGRA QUE FICA: ao escrever classificador, perguntar explicitamente se a propriedade medida
e a propriedade de interesse ou apenas uma correlata conveniente.

A CORRECAO. Classificacao pelo NOME da variavel mais a FORMA do valor, exigindo as duas:
  nome com forma de segredo   API_KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, _KEY
  e NAO ter forma de nao-segredo   PATH, DIR, HOST, URL, MAILTO, FILE, HOME, PORT, MODEL,
                                   CORE, _PY
  valor sem espaco, com 20 caracteres ou mais, que nao pareca caminho, URL nem e-mail.
Medido: 14 de 14 casos, incluindo os sete falsos positivos exatos que causaram a falha.
Teste estrutural refeito: o config antigo passa a ser APAGADO, o arquivo com chave viva
continua MANTIDO, e OLLAMA_HOST e SSH_KEY_PATH somem da contagem de credenciais.

ACHADO QUE VALE MAIS QUE A PROPRIA FAXINA. Existe em
%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\ uma copia de seguranca
claude_desktop_config.antes_da_rotacao_20261023_001808.json que carrega EM TEXTO PURO as
chaves EM USO de TOMTOM, NVIDIA, PERPLEXITY, NGC, MOONSHOT, HERE, GOOGLE_MAPS e GEMINI.
Copia de seguranca de configuracao e exposicao igual a do original, e e facil de esquecer
porque ninguem pensa nela como arquivo de credencial. A faxina passa a sinalizar isso como
RISCO ATIVO, e nao apaga sozinha: decisao do Mateus.

TAMBEM APURADO NA EXECUCAO REAL, sem acao necessaria: os arquivos de 'api keys' conferem
com a configuracao viva (gemini, google, here, moonshot, nvidia, perplexity, tomtom EM
USO), e deepseek, manus e ubuntu_key nao aparecem la porque vivem no ~/TransportMCP/.env
da Ubuntu. 'Nao aparece na config viva' nao e sinonimo de morta, e por isso a rotina nunca
apaga arquivo de 'api keys'.


================================================================================
24/10 - r5py VALIDADO COM DADO REAL, E O QUE O DADO REVELOU
================================================================================

FERRAMENTAS QUE JA ESTAVAM INSTALADAS E PARADAS. O env_transporte ja tinha aequilibrae
1.6.0, r5py 1.1.7, gtfs-kit, partridge, osmnx, pandana, networkx e duckdb com extensao
espacial, mais QGIS 3.40, osmium, Java 25, o JAR r5-v7.5.1 em cache e uma build OSRM do
Nordeste. A lacuna do ecossistema nao era ferramenta, era uso.

r5py VALIDADO, em bench/r5_validacao.py. Recorte OSM por osmium (442 MB para 9,4 MB),
rede R5 em 6 s, matriz 8x8 em menos de 1 s. Quatro assercoes, todas passaram: diagonal
nula; MONOTONICIDADE, acrescentar oferta nao aumentou tempo em nenhum dos 64 pares;
cobertura subindo de 38/64 para 64/64 ao somar o segundo feed; velocidade aparente em
linha reta entre 2 e 60 km/h nos 56 pares.
A MONOTONICIDADE E O ACHADO DE METODO: e verificacao interna, nao depende de fonte
externa, e e mais forte que comparar com um roteador de mercado, porque o roteador pode
estar consumindo o MESMO GTFS e a comparacao mediria reimplementacao, nao correcao.

QUATRO DEFEITOS NO GTFS ENTREGUE, achados por tentar usar o dado a serio. Registrados
aqui pelo METODO; o detalhe por projeto fica no projeto.
  1. Pacote com DOIS feeds de operador em subpastas, e nao arquivos na raiz do zip. O R5
     recusa. O gtfs-kit, permissivo, leu sem reclamar e devolveu os numeros de apenas UM
     dos dois, mascarando o problema: FERRAMENTA TOLERANTE ESCONDE DEFEITO DE DADO, e
     numero obtido dela nao e atestado de integridade.
  2. Um dos operadores com vigencia de DOIS DIAS no calendar.txt, so dias uteis. NAO HA
     DATA em que todos os feeds do pacote tenham servico ao mesmo tempo.
  3. Tabelas opcionais presentes e VAZIAS, que consumidor estrito recusa. Pela
     especificacao, tabela opcional vazia equivale a ausente, entao omitir e normalizacao.
  4. SO ONIBUS. As 510 linhas sao route_type 3; nao ha metro, travessia nem ascensor,
     embora varios polos principais SEJAM estacoes de metro. Analise montada sobre o
     pacote leva passageiro de onibus entre estacoes de metro, e o resultado sai plausivel.

ERRO MEU NO CAMINHO: afirmei que calendar_dates.txt era obrigatorio. E CONDICIONALMENTE
obrigatorio, exigido so quando calendar.txt falta. Apliquei regra de especificacao de
memoria em vez de aplicar a condicao.

CONFIDENCIALIDADE NA VERSAO: o script foi generalizado antes de comitar, sem nome de
gestor, de operador, de cidade nem caminho de projeto, porque nao consegui confirmar se o
repositorio e publico. VISIBILIDADE NAO CONFERIDA SE TRATA COMO PUBLICA.
