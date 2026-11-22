# PRE-REGISTRO: bateria VRPTW cuOpt x OR-Tools (Solomon, 100 clientes)

Escrito em 22/11/2026, ANTES da rodada de producao. Mudanca posterior entra como ADENDO datado, nunca edicao.
Autorizacao: Mateus, 22/11/2026 08h45 (bloco II, proposta a).

## Pergunta
A vantagem de 5% a 10% do cuOpt sobre o OR-Tools medida em 21/10 vale para CVRP sintetico de deposito unico.
Operacao real tem janela de horario. Esta bateria mede a diferenca com JANELA DE TEMPO, em instancias publicas
de referencia, contra a melhor solucao conhecida da literatura.

## Instancias
As 56 de Solomon (C1, C2, R1, R2, RC1, RC2), 100 clientes, copiadas de github.com/dietmarwo/VRPTW (licenca MIT),
pasta problems. Melhores solucoes conhecidas (BKS): pasta sintef do mesmo repositorio, 49 de 56.
CONFERENCIA DO VALIDADOR: o validador proprio reproduziu a BKS de C101 (10 veiculos, 828,94) e de R101
(19 veiculos, 1.650,80) a partir das rotas publicadas. Validador que reproduz a literatura vale como referencia.

## Condicoes igualadas
- Matriz unica: euclidiana em dupla precisao x1000; custo arredondado; tempo arredondado PARA CIMA.
- Objetivo identico e ESCRITO nas duas pontas: custo fixo de 10^7 por veiculo usado + distancia
  (convencao de Solomon: veiculos primeiro, distancia depois). No cuOpt por set_vehicle_fixed_costs com pesos
  explicitos; no OR-Tools por SetFixedCostOfAllVehicles.
- Frota disponivel K, capacidade, janelas, servico e janela do deposito da propria instancia.
- Orcamento de 30 s de parede por resolucao. OR-Tools com GUIDED_LOCAL_SEARCH; estrategia de primeira solucao
  fixada pelo PILOTO abaixo. cuOpt com 3 repeticoes (solver estocastico); OR-Tools 1 (deterministico em 1 fio).
- GPU LIVRE: a rodada so comeca depois que a indexacao do acervo terminar. O nvidia-smi do inicio vai em cada
  linha do resultado; utilizacao acima de 10% no inicio invalida a linha.

## Medidas
Por instancia: veiculos e distancia de cada solver (do VALIDADOR, nao do solver), viabilidade, e diferenca
para a BKS. Comparacao hierarquica: menos veiculos vence; empate em veiculos, menor distancia vence.
Resumo por familia (C1, C2, R1, R2, RC1, RC2): soma de veiculos (CNV) e soma de distancias (CTD), que e o
formato da literatura.

## Regra de leitura, fixada antes
- Diferenca de distancia abaixo de 1% com mesmo numero de veiculos: EMPATE.
- cuOpt: usar a MEDIANA das 3 repeticoes; reportar tambem a melhor e a pior.
- Solucao inviavel no validador conta como derrota daquele solver naquela instancia, e e reportada.
- O resultado vale para Solomon 100 clientes. Nao extrapolar para frota heterogenea, multiplos depositos,
  jornada ou instancia real sem nova medicao.

## Piloto (22/11/2026 ~09h, GPU DISPUTADA pela indexacao, serve so para escolher parametro)
C101, R101, RC101 e R201 a 30 s, cuOpt x1, com PATH_CHEAPEST_ARC e PARALLEL_CHEAPEST_INSERTION no OR-Tools.
Os numeros do piloto NAO entram no resultado.

Resultado do piloto (so para escolher parametro):
| inst. | BKS | OR PATH_CHEAPEST_ARC | OR PARALLEL_CHEAPEST_INSERTION | cuOpt (2 execucoes) |
|---|---|---|---|---|
| C101 | 10 / 828,94 | 10 / 828,94 | 10 / 828,94 | 12 / 869,30 e 11 / 848,94 |
| R101 | 19 / 1.650,80 | SEM SOLUCAO | 19 / 1.653,53 | 19 / 1.650,80 nas duas |
| R201 | 4 / 1.252,37 | 4 / 1.303,60 | 4 / 1.254,57 | 4 / 1.275,55 e 4 / 1.265,71 |
| RC101 | 14 / 1.696,95 | SEM SOLUCAO | 16 / 1.669,37 | 15 / 1.659,08 e 15 / 1.647,41 |
DECISAO: OR-Tools com PARALLEL_CHEAPEST_INSERTION. PATH_CHEAPEST_ARC nao encontra solucao viavel em 30 s nas
instancias de janela apertada (R1, RC1), o que mediria a heuristica de partida e nao o solver.
OBSERVACAO que a rodada vai responder: o cuOpt oscilou no NUMERO DE VEICULOS em C101 (12 e 11, contra 10 da BKS)
com a GPU disputada. Com GPU livre e 3 repeticoes se vera se e efeito da disputa ou do solver.
