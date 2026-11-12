> **Este arquivo e para o Claude Code executar.**
> Se voce e o Mateus e quer entender o que esta bateria testa, por que ela existe e o
> que vai ser pedido a voce, leia primeiro `ENTENDA_bateria_derpr.md`, na mesma pasta.
> Os dois descrevem a mesma coisa: aquele explica a intencao, este executa.

# Especificacao de instalacao e execucao: bateria de recuperacao do anuario DER-PR

Para o Claude Code da Ubuntu. Escrita em 11/11/2026 pela sessao de configuracao do
ecossistema. Tarefa longa: roda aqui, nao no chat.

## 0. O que ja esta pronto, e nao se mexe

```
~/ecossistema/bench/suites/recuperacao_anuario_derpr.json          dde54454c84ddd7e...
                          ..._ADENDO_01.json   bracos D,E,F; limite de indice 200 GB
                          ..._ADENDO_02.json   bracos G,H; pre-voo de diacritico
                          ..._ADENDO_03.json   identidade do corpus
                          ..._ADENDO_04.json   gabarito  f0c4a8703428c405...
~/ecossistema/bench/dados/DERPR_Anuario_..._2022_v2.pdf  c19be5398997a7ae...  58 pag
```

REGRA DURA: nenhum destes arquivos e alterado. O pre-registro e o gabarito estao
fechados e com hash. Conferir os hashes no inicio de cada rodada; divergencia PARA a
rodada, nao se corrige o arquivo.

## 1. Mandato e proibicoes

FAZ: criar ambientes isolados, baixar pesos, rodar o pre-voo, rodar a bateria, medir,
gravar manifesto e resultado.

NAO FAZ, em nenhuma hipotese:
- `pip install` em `~/TransportMCP/.venv`. E producao e serve cinco servidores MCP.
- `pip install` em `~/env_transporte`. Ele tem Docling 2.126.0 e LanceDB 0.39.0, que
  sao os bracos A e B e o indexador de todos. Quebra-lo quebra o incumbente E a medicao.
- alterar `papeis.json` por conta propria. O vencedor entra la depois, por decisao do
  Mateus, com o resultado na mao.
- substituir um braco que falhe por outro. Braco que nao roda e reportado como nao
  rodado, com o erro. Substituicao silenciosa destroi a comparacao.

## 2. Arquitetura: um indexador, um pontuador, muitos extratores

Cada braco produz VETORES, e so isso. A indexacao e a pontuacao sao as mesmas para
todos, num unico lugar.

```
braco (ambiente isolado)  ->  vetores em arquivo  ->  indexador unico  ->  pontuador unico
                              derpr/vetores/<braco>.npz   env_transporte     env_transporte
```

POR QUE: se cada braco indexasse com codigo proprio, diferenca de resultado poderia vir
do indice e nao do modelo, e a comparacao mediria duas coisas ao mesmo tempo. Com um
indexador so, a unica variavel entre bracos e o extrator ou o embedder.

Formato de `<braco>.npz`: `vetores` (float32; 2D para braco denso, lista de 2D para
multivetor), `pagina` (int32, 1 a 58, uma entrada por vetor ou por bloco), `meta` (JSON
com modelo, versao, dimensao, vetores por pagina, tempo frio e quente).

## 3. Ambientes

Interpretador 3.12, ja presente na maquina (gerenciado pelo uv):

```
PY312=/home/mateus/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12
```

| Ambiente | Bracos | Conteudo |
|---|---|---|
| `~/env_transporte` (EXISTE, nao instalar nada) | A, B, indexador, pontuador | Docling 2.126.0, LanceDB 0.39.0, torch 2.14.0+cu130 |
| `~/env_colpali` (criar) | C | colpali-engine, que REBAIXA o torch. E a razao de existir isolado. |
| `~/env_nemotron_vl` (criar) | D, E, F | transformers>=4.56, torch, sentence-transformers |
| `~/env_nemotron_parse` (criar) | G | Nemotron-3.5-Parse; conferir no cartao a versao exigida de transformers antes de fixar |
| `~/env_nemotron_ocr` (criar) | H | Python 3.12 + torch cu128, instalado do fonte do repositorio |

Criar cada um com `$PY312 -m venv ~/env_<nome>`. Apos instalar, gravar
`pip freeze > ~/ecossistema/bench/derpr/ambientes/<nome>.txt`, para a rodada ser
reproduzivel. Ambiente que falhe ao montar e reportado; nao se tenta instalar no vizinho.

Nota para H: `~/env_trtllm` ja tem Python 3.12.14 com torch 2.9.1+cu128, que e quase
exatamente o que o cartao do ocr-v2 pede. Serve de referencia das versoes, mas NAO se
instala nele: ele e de outra finalidade.

## 4. Ordem de execucao

```
1. conferir hashes da suite, dos 4 adendos e do corpus        para se divergir
2. montar os 4 ambientes novos, um a um, gravando pip freeze
3. baixar os pesos                                            medir e registrar o disco
4. PRE-VOO DE DIACRITICO (secao 5)                            PARA e aguarda o Mateus
5. bateria dos bracos validados (secao 6)
6. custo de indice e projecao (secao 7)
7. manifesto e relatorio (secao 8)
```

O passo 4 interrompe. Nao siga para a bateria sem a conferencia humana.

## 5. Pre-voo de diacritico

Declarado no ADENDO_02. Nem o Nemotron-3.5-Parse nem o nemotron-ocr-v2 nomeiam o
portugues entre os idiomas avaliados, e o ocr-v2 se contradiz no proprio cartao.

Procedimento:
1. escolher 3 paginas do anuario com densidade de diacritico: uma de texto corrido
   (sugestao: pagina 10 ou 12, que tem 1300+ caracteres extraiveis), uma com legenda de
   figura e uma com celula de tabela;
2. extrair com G, com H nas DUAS variantes (inglesa no nivel de palavra, multilingue no
   nivel de linha) e com o Docling do braco B, como referencia conhecida;
3. gravar as saidas lado a lado em `derpr/prevoo/` e AVISAR O MATEUS;
4. ele confere a olho e informa a taxa de caractere acentuado preservado.

Criterio ja declarado, nao se renegocia: 95% ou mais o braco e valido; entre 80 e 95
entra com a taxa registrada e qualquer derrota dele passa a ter duas explicacoes
concorrentes no resultado; abaixo de 80 o braco SAI e o resultado diz que a decomposicao
nao esta disponivel.

## 6. A bateria

Oito bracos. Todos consultam as 30 perguntas e sao pontuados contra o gabarito do
ADENDO_04, que tem 28 perguntas pontuaveis (D09 e N20 sao ausentes e saem do acerto@k).

```
A  Docling SEM OCR   -> qwen3-embedding:4b (Ollama)       producao hoje
B  Docling COM OCR   -> qwen3-embedding:4b                incumbente justo
C  ColQwen2.5-v0.2 sobre imagem de pagina, multivetor      geracao anterior
D  nvidia/llama-nemotron-embed-vl-1b-v2  (denso)
E  D + nvidia/llama-nemotron-rerank-vl-1b-v2               candidato a producao
F  nvidia/nemotron-colembed-vl-4b-v2  (interacao tardia)   CONDICIONAL a licenca
G  nvidia/Nemotron-3.5-Parse -> qwen3-embedding:4b         CONDICIONAL ao pre-voo
H  nvidia/nemotron-ocr-v2    -> qwen3-embedding:4b         CONDICIONAL ao pre-voo
```

G e H usam o MESMO embedder de A e B de proposito. Sem isso a comparacao mediria
"trocamos duas coisas" e atribuiria o ganho ao extrator sem base.

F so roda se a licenca for conferida no cartao e permitir uso compativel. O
`nemotron-colembed-vl-8b-v2` esta FORA: 8,76B de parametros nao cabem nos 16.311 MiB da
placa em fp16, e rodar quantizado invalidaria a comparacao com o numero publicado.

Metricas, ja declaradas na suite original: acerto@1, acerto@5 e posicao do certo, com
granularidade de PAGINA. Tres passadas. Latencia registrada separando fria, com carga do
modelo, de quente, com ele residente.

Um braco por vez na GPU. Conferir VRAM livre antes de cada um e registrar `nvidia-smi`
no inicio e no fim. A placa tem 16.311 MiB.

## 7. Custo de indice

Medir, por braco, os bytes de indice de fato gravados para as 58 paginas, e dividir por
58. Projetar para 10.000 e 50.000 paginas.

ADVERTENCIA que vai no relatorio, literal: o corpus tem 58 paginas e nessa escala o
indice cabe em qualquer braco, entao ESTA BATERIA E INCAPAZ DE REVELAR O PROBLEMA DE
ARMAZENAMENTO. A projecao e calculo declarado, nao resultado medido.

Criterio de decisao, confirmado pelo Mateus em 11/11 antes de qualquer execucao: vence o
maior acerto@5 entre os bracos cuja projecao para 50.000 paginas fique em 200 GB ou
menos. Empate de um braco em uma passada e empate tecnico, nao vitoria. Se nenhum couber,
entra o melhor que couber e a distancia para o teto fica registrada como divida tecnica.

## 8. Manifesto e relatorio

Manifesto por rodada em `derpr/manifestos/manifesto_NNNN.json`, com SUFIXO SEQUENCIAL.
Nome por instante deixa duas rodadas no mesmo segundo sobrescreverem a anterior em
silencio; calcular o proximo numero lendo o maior existente e gravar com modo `x`.

Conteudo: data e hora, hashes conferidos, ambientes com pip freeze, bracos que rodaram e
bracos que nao rodaram com o motivo, tolerancias, nvidia-smi de inicio e fim, metricas
por braco e por passada, custo de indice medido e projetado, e o que ficou fora.

O relatorio NAO decide o papel do `papeis.json`. Ele apresenta o resultado contra o
criterio declarado e para. A decisao e do Mateus.

## 9. Disciplina

- Codigo que produz resultado roda com assercoes: 58 paginas, 30 perguntas, 28
  pontuaveis, vetores com a dimensao declarada no meta.
- Resultado de uma unica passada nao e resultado. Tres passadas, sempre.
- Ausencia de divergencia nao e prova de que a medicao funcionou. Testar o pontuador com
  caso sintetico de resposta conhecida antes de confiar em qualquer numero.
- Erro proprio se corrige em voz alta, citando a rodada e o manifesto onde o numero
  errado foi gravado.
- Falha de instalacao, de download ou de execucao e REPORTADA, nunca contornada por
  substituicao de modelo, de versao ou de ambiente.
