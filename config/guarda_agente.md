# Regras obrigatorias para agente com shell nesta maquina

Voce esta na workstation `mateus-ryzen` (Ubuntu, RTX 5060 Ti), que e o CENTRO DE COMANDO do
ecossistema de Mateus Araujo e Silva (CITATIS Engenharia, consultoria em Engenharia de
Transportes). Esta maquina guarda as credenciais, os modelos locais, os nove servidores MCP de
producao, o acervo e os indices. Erro aqui nao e erro de arquivo, e perda de ativo de trabalho.

Este arquivo e AUTOSSUFICIENTE de proposito: o registro completo tem mais de 200 KB e esta em
`~/ecossistema/CLAUDE.md`, que pode estar FORA da sua raiz de projeto. Se precisar do completo,
PECA a Mateus em vez de supor. Cada regra abaixo nasceu de um erro ja cometido e medido.

## 1. ATIVO NAO RECUPERAVEL: nunca remover este modelo

    ollama rm qwen2.5-coder:14b-fast      <-- NUNCA. IRREVERSIVEL.

A tag saiu do registro do Ollama e o re-pull FALHA. A copia local e a unica que existe. Backup
em `/media/mateus/DADOS_01/99 - BACKUPS/modelos/`. Qualquer limpeza de modelos passa por
conferencia previa com Mateus, e nao por julgamento proprio.

## 2. NAO ATUALIZAR O PACOTE mcp

    pip install mcp            <-- quebra os nove servidores MCP
    pip install -U mcp         <-- idem

No `mcp` 2.x o `FastMCP` virou `MCPServer` e `mcp.server.fastmcp` deixou de existir. Os nove
servidores usam `FastMCP`. A trava esta em `install.constraint` no `pip.conf` de cada venv,
apontando para `~/ecossistema/config/restricoes_pip.txt`. NAO apagar nem mover esse arquivo: se
ele desaparecer, o pip passa a RECUSAR toda instalacao naquele ambiente.

## 3. CREDENCIAL

Nove credenciais vivem em `~/TransportMCP/.env`, modo 600. Regras, sem excecao:
- NUNCA imprimir o valor de uma chave. Só a impressao digital sha256 de 12 hex.
- NUNCA copiar credencial para dentro de codigo, de log, de mensagem ou de pasta sincronizada.
- NUNCA gravar `.env` em `~/ecossistema`: essa pasta e replicada para tres outras maquinas.
- Texto de erro de API que leva chave na query string NAO SAI SEM CENSURA.
- Classificar credencial por FORMATO e por digital, nunca lendo o valor.

## 4. FRONTEIRA DE DADOS: o que protege nao e rodar local

Voce e modelo de nuvem. O que voce le SAI desta maquina. "Roda local, logo protege dado sob NDA"
e FALSO. O que protege e o script devolver AGREGADO em vez de registro individual.
- Dado de cliente, pesquisa bruta, microdado e material sob NDA: processar por rotina local e
  devolver apenas estatistica, agregado ou conclusao.
- NUNCA ler, listar ou varrer `~/GoogleDrive`. E montagem `fuse.rclone` do Google Drive inteiro,
  com acervo de cliente, e varrer ali puxa conteudo pela rede sem terminar.
- `/media/mateus/DADOS_01` e CIFS sobre Tailscale, servido pela maquina Windows. Nao e disco
  local. Veja a regra 5.

## 5. LOTE LE DE DISCO LOCAL, PONTO

Antes de processar um diretorio em lote: `mount | grep <ponto>`. Se for cifs, nfs ou fuse,
COPIAR para `/mnt/nvme_lexar/` primeiro. Medido em 18/11/2026 lendo direto do CIFS: 11 s por
documento com a GPU em 0% e o processo em estado `D`; apos a copia local, 2,9 s com a GPU em 100%.
Toda varredura de home usa `-xdev`. Sem `-xdev` o `find` atravessa a montagem do Drive e nao
termina nunca (custou 32 e 19 minutos de varredura travada em 12/11/2026).

## 6. PASTA SINCRONIZADA

`~/ecossistema` e pasta `sendonly` do Syncthing para tres dispositivos, e esta maquina e a FONTE.
Alterar sempre AQUI e deixar o Syncthing levar. O `.gitignore` e o `.stignore` sao listas de
PERMISSAO: nunca relaxar. Ordem obrigatoria ao excluir arquivo ignorado: APAGAR PRIMEIRO,
IGNORAR DEPOIS, senao o arquivo congela no destino para sempre.

## 7. TRABALHO LONGO

A ponte do chat corta em cerca de 80 s. Qualquer coisa acima de 45 s vai para segundo plano:

    nohup setsid <comando> > saida.log 2>&1 </dev/null &

Acompanhar pelo TAMANHO DO LOG crescendo, nunca pela existencia do processo: processo pode
existir travado, e `pgrep` casa com o proprio comando de teste. Conferir `bash -n` e
`py_compile` ANTES de lancar, nunca depois.

## 8. BACKUP NOTURNO

`~/.local/bin/restic-backup.sh` roda as 03h00 e le `/media/mateus/DADOS_01` pela rede. Nao
alterar, nao desabilitar e nao mexer no agendamento sem autorizacao de Mateus. Se precisar do
enlace livre, SUSPENDER o processo com `kill -STOP` e RETOMAR com `kill -CONT` dentro de 30
minutos, que e a janela em que a trava do repositorio ainda vale.

## 9. METODO, QUE AQUI VALE TANTO QUANTO CODIGO

- Amostra de tamanho um nao e resultado. Solver estocastico: repetir no minimo 3 vezes.
- Comparacao entre ferramentas exige CONDICOES IGUALADAS nas duas pontas. Padrao de cada
  ferramenta nao declarado e condicao nao equalizada, e infla a diferenca.
- Quando a validacao discorda da referencia, desconfiar PRIMEIRO do criterio de comparacao.
- Conferir contagem contra ferramenta independente. Contagem de uma passada so nao e contagem.
- Numero relevante exige verificacao independente: ordem de grandeza, caso limite ou recalculo
  por caminho alternativo.
- Erro proprio se corrige EM VOZ ALTA, nao em silencio.
- Antes de propor qualquer compra ou instalacao, conferir a capacidade JA INSTALADA.
- Nao inventar titulo, autor, periodico, DOI nem URL.

## 10. FORMA

Portugues do Brasil. NAO usar travessao (em dash): trocar por virgula, ponto e virgula,
dois-pontos ou parenteses. Terminologia tecnica de Engenharia de Transportes, sem simplificacao
didatica: o interlocutor e especialista. Rotular origem do dado nos entregaveis:
`[verificado: fonte]`, `[premissa]`, `[estimativa]`.
