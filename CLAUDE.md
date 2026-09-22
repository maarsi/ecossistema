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
