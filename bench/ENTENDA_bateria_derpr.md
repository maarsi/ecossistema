# O que e esta bateria, e por que ela existe

Documento para o Mateus. O arquivo vizinho, `ESPEC_bateria_derpr.md`, e para o Claude
Code executar, e por isso e telegrafico. Este aqui explica.

---

## 1. A pergunta, em uma frase

**Qual ferramenta acha melhor uma informacao que esta dentro de uma tabela ou de um
grafico num PDF?**

E so isso. Tudo o mais e consequencia.

---

## 2. Por que essa pergunta importa para o seu trabalho

Pense no auditor do TPC RMS. Para ele funcionar, ele precisa responder coisas como
"o TCE da Bahia ja se manifestou sobre verificador independente?" e citar a pagina.

O acervo dele, as decisoes de tribunal de contas e os editais, e cheio de **tabela
digitalizada**. Se a ferramenta nao enxerga dentro de tabela, o auditor nao acha, e a
resposta dele vira "nao encontrei" quando a informacao estava la.

O mesmo vale para o anuario do DER-PR, para edital de licitacao, para planilha de
custo de operadora. **E o mesmo problema sempre.**

---

## 3. O problema concreto, com um exemplo que voce mesmo viu

Voce leu a pagina 13 do anuario e anotou: 6028 sinistros, 641 vitimas fatais,
5084 feridos. Estava la, voce viu com os olhos.

Agora veja **tudo** o que o computador consegue extrair dessa mesma pagina 13:

```
13
SERIE HISTORICA
SERIE HISTORICA ANUAL
Fonte: Coordenadoria de Engenharia de Trafego e Seguranca Rodoviaria - DER/PR
Nota: Utilizacao e conversao de dados do BATEU/BPRv
por Ocorrencias
```

O titulo, a fonte e um rotulo. **Os numeros nao estao ali.** Eles existem na pagina como
desenho, como pixel, do mesmo jeito que uma fotografia. O PDF guarda a tabela como
imagem, nao como texto.

Isso vale para **23 das 28 perguntas** que voce respondeu. Foi exatamente o que a sua
leitura revelou, e e a razao de esta bateria existir.

---

## 4. Os dois caminhos que um computador tem

### Caminho 1: transformar a pagina em texto, e depois procurar no texto

E o que fazemos hoje. Uma ferramenta chamada Docling abre o PDF e tenta tirar o texto.
Quando o texto esta la, funciona bem. Quando a informacao e desenho, ela tenta um
**OCR**, que e o programa que olha a imagem e tenta reconhecer as letras, como quando
voce digitaliza um documento e ele vira texto pesquisavel.

Ponto fraco: OCR erra em tabela, erra em grafico, e erra feio em numero dentro de
celula pequena.

### Caminho 2: nao transformar em texto; comparar imagens

Em vez de ler a pagina, o computador tira uma especie de **impressao digital numerica**
da imagem inteira da pagina. Faz o mesmo com a sua pergunta. Depois compara as
impressoes digitais e devolve as paginas mais parecidas.

E contraintuitivo, mas funciona: ele nunca "le" o 6028. Ele aprende que paginas com
aquela cara respondem a perguntas com aquela cara.

Ponto fraco: guardar essas impressoes digitais ocupa espaco, as vezes espaco absurdo.
Isso vai voltar no item 7.

---

## 5. Os oito bracos, em portugues

"Braco" aqui quer dizer **uma receita completa a ser testada**. Todos recebem as mesmas
30 perguntas e o mesmo documento, e a gente ve quem acha a pagina certa.

| Braco | O que e, em portugues comum | O que queremos saber com ele |
|---|---|---|
| **A** | Caminho 1 com o Docling, **sem** OCR. E o que roda hoje. | O ponto de partida. Quanto perdemos hoje? |
| **B** | Caminho 1 com o Docling, **com** OCR ligado. | O concorrente justo. Ligar o OCR ja resolve? |
| **C** | Caminho 2 com o ColQwen, ferramenta da geracao passada. | Serve de regua: quanto a geracao nova avancou? |
| **D** | Caminho 2 com um modelo novo da NVIDIA, versao **barata**: uma impressao digital por pagina. | Da para ter o caminho 2 sem pagar o preco dele? |
| **E** | O braco D **mais um segundo olhar**: pega as paginas mais promissoras e examina cada uma com cuidado. | **Este e o candidato a entrar em producao.** |
| **F** | Caminho 2 na versao **cara**: centenas de impressoes digitais por pagina. | Qual e o teto? Quanto D e E estao deixando na mesa? |
| **G** | Caminho 1, mas trocando o Docling por um extrator novo que **entende tabela e grafico**. | Um extrator melhor resolve sem precisar do caminho 2? |
| **H** | Caminho 1 so com um **OCR novo**, sem a parte que entende estrutura. | Separa "entende tabela" de "le letra melhor". |

### Por que oito e nao dois

Porque senao a gente nao saberia **a que atribuir o resultado**.

Exemplo: imagine que so testassemos A contra G, e G ganhasse. G muda duas coisas ao
mesmo tempo: usa um extrator novo **e** esse extrator tem OCR melhor. Quem ganhou? O
entendimento de tabela, ou so o OCR? **Nao da para saber.** Por isso existe o H, que muda
so o OCR. Com os tres, a conta fecha.

E a mesma logica de um ensaio de laboratorio: so se troca uma variavel por vez.

Pelo mesmo motivo, os bracos G e H usam **o mesmo** programa de busca que A e B
(o `qwen3-embedding`). Se trocassemos tambem o buscador, voltariamos a nao saber a quem
creditar a diferenca.

---

## 6. O que voce ja fez, e por que tinha de ser voce

As 30 perguntas foram escritas em 24 de outubro **sem abrir o documento**, de proposito:
quem escreve a pergunta olhando a resposta escreve a pergunta que a ferramenta favorita
acerta.

Hoje voce leu as 58 paginas e disse, para cada pergunta, **em que pagina esta a
resposta**. Isso se chama gabarito, e e a verdade contra a qual os oito bracos vao ser
medidos.

**Por que voce e nao eu:** eu sou um modelo de visao. Ler imagem de pagina e procurar
resposta e exatamente o que os bracos C, D, E e F fazem. Se eu fizesse o gabarito, eu
estaria escrevendo a prova e corrigindo a prova, e os bracos parecidos comigo sairiam na
frente sem merecer.

Uma coisa deu errado e ja foi corrigida: eu te ofereci tres opcoes, "no texto", "em
imagem" e "ausente". Tabela **parece texto** para quem olha, e e **imagem** para o
computador. Voce marcou 26 como texto, com razao do seu ponto de vista. Eu recalculei
esse campo por programa, e deu 5 texto e 23 imagem. **As paginas que voce anotou valem
todas**; so o rotulo estava mal perguntado, e a culpa e do formulario que eu fiz.

---

## 7. O custo escondido, que e a parte menos obvia

O caminho 2, de comparar imagens, tem um preco que nao aparece no teste.

Guardar as impressoes digitais de **50 mil paginas** custaria, dependendo do braco:

| Braco | Espaco em disco para 50 mil paginas |
|---|---|
| D e E, versao barata | **0,2 GB** |
| F, versao cara (4B) | **198 GB** |
| F na versao 8B, que descartamos | 317 GB |
| Uma versao 3B que eu quase escolhi por engano | 708 GB |

Mil vezes de diferenca.

**E aqui esta a armadilha:** o anuario tem 58 paginas. Nessa escala, **todos cabem**, e o
teste nunca mostraria esse problema. Se a gente escolhesse so pelo acerto, adotaria o
braco mais caro e descobriria o custo mais tarde, no acervo de verdade, quando ja
estivesse tudo montado.

Por isso voce fixou, antes de rodar, um limite de **200 GB para 50 mil paginas**. Quem
passar disso esta fora da disputa, por mais que acerte.

---

## 8. O que voce vai ter de fazer, e quando

**Um passo so, e ele interrompe a execucao.** Chama-se pre-voo.

**O problema:** os dois modelos novos de extracao, usados nos bracos G e H, **nao dizem
que funcionam em portugues**. Um deles lista ingles, chines, japones, coreano e russo. O
outro se contradiz na propria documentacao.

O risco concreto e o **acento**. Um programa treinado em ingles tende a errar o til, a
cedilha e as vogais acentuadas. Se isso acontecer, o braco vai perder a disputa, e a
gente concluiria "essa ferramenta e pior" quando a verdade e "essa ferramenta nao sabe
portugues".

**O que vai te ser pedido:** o Claude Code vai pegar tres paginas do anuario, passar por
cada ferramenta, e deixar as saidas lado a lado numa pasta. Voce **olha e responde uma
coisa so**: os acentos sobreviveram?

Algo assim:

```
original:  Seguranca Rodoviaria, condicao meteorologica, ocorrencias por extensao
saida X:   Seguranca Rodoviaria, condicao meteorologica, ocorrencias por extensao   bom
saida Y:   Seguran?a Rodovi?ria, condi??o meteorol?gica, ocorr?ncias por extens?o   ruim
```

**O criterio ja esta escrito e nao muda depois** (senao seria escolher o resultado):

- **95% ou mais dos acentos preservados:** o braco vale, entra na disputa.
- **entre 80% e 95%:** entra, mas com a taxa anotada, e se perder o relatorio dira que ha
  duas explicacoes possiveis.
- **abaixo de 80%:** o braco sai, e o relatorio diz que aquela comparacao nao pode ser
  feita, em vez de fingir que foi.

Deve te custar poucos minutos.

---

## 9. O que sai no fim, e o que fica com voce

Um relatorio com, para cada um dos oito bracos: quantas das 28 perguntas ele acertou na
primeira pagina devolvida, quantas acertou entre as cinco primeiras, quanto demorou, e
quanto espaco o indice dele ocuparia no acervo de verdade.

**O relatorio nao decide nada.** Ele apresenta o resultado contra o criterio que voce
fixou. A decisao de qual ferramenta entra no ecossistema e sua, com o numero na mao.

Se um braco venceu com folga, ele vira um "papel" no `papeis.json`, que e a lista de
quais ferramentas o ecossistema usa para cada tipo de tarefa. Dai em diante, **a conversa
da auditoria do TPC RMS passa a ter essa ferramenta disponivel** sem precisar saber de
nada disto.

---

## 10. Glossario dos termos que aparecem no arquivo tecnico

| Termo | O que quer dizer |
|---|---|
| **braco** | uma receita completa sendo testada, das oito |
| **corpus** | o documento usado no teste (o anuario do DER-PR, 58 paginas) |
| **gabarito** | a sua lista de qual pagina responde cada pergunta |
| **acerto@1** | com que frequencia a primeira pagina devolvida e a certa |
| **acerto@5** | com que frequencia a pagina certa esta entre as cinco primeiras |
| **embedder** | o programa que transforma texto ou imagem em numeros comparaveis |
| **OCR** | programa que olha a imagem e reconhece as letras |
| **indice** | o arquivo onde ficam guardados esses numeros, para busca rapida |
| **ambiente isolado** | uma instalacao separada de programas, para que um nao quebre o outro |
| **sha256** | uma assinatura de 64 caracteres que prova que um arquivo nao mudou |
| **pre-registro** | escrever as regras do teste antes de ve-lo, para nao ajustar depois |
| **passada** | uma execucao completa. Sao tres, porque uma so nao e resultado |

---

## 11. Por que o outro arquivo e tao seco

Porque o leitor dele e um programa, e programa nao se beneficia de explicacao: se
beneficia de comando exato, caminho exato e proibicao explicita. As frases duras que voce
viu la ("nao instalar em", "braco que falhe e reportado, nunca substituido") existem para
impedir que ele improvise quando algo der errado, porque improviso dele seria entregar
numero errado com cara de certo.

Os dois arquivos descrevem a mesma coisa. Quando houver duvida entre eles, **este aqui e
o que explica a intencao**, e o outro e o que a executa.
