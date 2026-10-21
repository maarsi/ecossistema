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
- Bateria CVRP (`bench/cvrp_cuopt_ortools.py`, mesma matriz inteira, capacidade 100, demanda 1-10,
  semente 42, 30 s por instancia, RTX 5060 Ti). Distancia total, as 6 solucoes validadas por codigo
  independente (cobertura, capacidade, distancia recalculada):
  - 50 clientes ..... empate em 7.425 (3 veiculos); cuOpt ja chega la com 1 s, OR-Tools so aos 21 s
  - 200 clientes .... cuOpt 20.950 x OR-Tools 23.126 (-9,4%); OR-Tools estaciona aos 5 s e nao sai mais
  - 1000 clientes ... cuOpt 62.387 x OR-Tools 69.127 (-9,8%); os dois usam 55 veiculos (minimo teorico)
  Leitura: abaixo de ~50 pontos o empate e esperado e o OR-Tools basta; de 200 para cima a GPU paga.
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
- Comparacao justa em 200 pontos (frota travada em 12 nos dois, cuOpt so distancia, semente 42,
  30 s, validacao independente OK nos dois): cuOpt 20.940 x OR-Tools 22.546.
  A vantagem ENCOLHE de 9,4% para ~7%, mas se mantem. Quem melhorou foi o OR-Tools
  (23.126 -> 22.546): com 14 veiculos ele gastava busca em frota que nao precisava.
  O cuOpt nao mudou (20.950 -> 20.940). Em 4 execucoes a amplitude do cuOpt foi 0,42%
  (20.940 a 21.028), ou seja vantagem entre 6,7% e 7,1% — maior que o ruido.
- Licao de metodo: comparar solvers com objetivos diferentes INFLA a diferenca. Antes de publicar
  qualquer numero, igualar frota e funcao objetivo, e repetir o solver estocastico ao menos 3 vezes
  para separar vantagem de ruido.
- `bin/manus_export.py`: o rotulo "link expirado" saiu. `motivo_cdn()` le o `<Code>` do corpo do
  CloudFront e grava o motivo real (InvalidKey, MissingKey, AccessDenied...). Importante: ler o
  corpo ANTES de fechar a resposta — com `stream=True` + `r.close()` o `<Code>` se perde e o
  motivo vira "sem codigo no corpo".
- `sondar_anexos()`: baixa UMA url de anexo antes de comecar e aborta com mensagem clara se nao
  vier 200/206, em vez de marcar milhares de falhas. `--sem-anexos` pula a sonda. Testado em 21/10
  contra a panne em curso: aborta com "HTTP 403 (InvalidKey)" sem escrever nada em disco.
