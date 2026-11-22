#!/bin/bash
# Indexacao do acervo 40 - REFERENCIAS em colecoes ref40_<subarea> (decisao de Mateus, 17/11/2026),
# em ORDEM DE PRIORIDADE DOS PROJETOS ATIVOS (22/11/2026). Fase 1: PyMuPDF (e texto do OCR para os
# digitalizados), rapida, completa. Fase 2: Docling para norma_manual e relatorio_institucional,
# que substitui os trechos desses documentos; roda depois, sozinha, e pode passar das 8h.
# Reentrante: o indice pula o que ja foi feito (hash e manifesto parcial a cada 25 arquivos).
set -u
PY=/home/mateus/env_transporte/bin/python; IX=/home/mateus/ecossistema/bin/indice.py
ACERVO="/mnt/nvme_lexar/acervo/40 - REFERENCIAS"; CAT=/home/mateus/base_conhecimento/catalogo_indice_v2.jsonl
ORDEM="transporte_publico_tpc economia_avaliacao_regulacao planejamento_politica_legislacao
demanda_escolha_discreta demanda_4sm_geral pesquisa_levantamento_dados demanda_distribuicao_od demanda_geracao_pgt demanda_abm_comportamento
trafego_capacidade_sinalizacao trafego_fluxo_simulacao trafego_seguranca_viaria redes_alocacao_equilibrio
logistica_transporte_carga modos_ferro_aero_hidro infraestrutura_rodoviaria_pavimentos
uso_solo_acessibilidade_espacial mobilidade_ativa_tdm sustentabilidade_energia_clima acessibilidade_arquitetonica_nbr
metodos_quantitativos_sig fora_de_escopo"
[ -s "$CAT" ] || { echo "ERRO: $CAT ausente; rodar taxonomia_v2_final.py antes"; exit 1; }
for fase in 1 2; do
  for s in $ORDEM; do
    echo "=== [$(date +%H:%M)] fase $fase: $s"
    if [ $fase = 1 ]; then $PY $IX indexar "$ACERVO" --nome ref40_$s --catalogo $CAT --subarea $s --pular-duplicatas --sem-docling 2>&1 | grep -E "^filtro|^INDICE|pendente:|ERRO|Traceback"
    else $PY $IX indexar "$ACERVO" --nome ref40_$s --catalogo $CAT --subarea $s --pular-duplicatas --refazer-docling 2>&1 | grep -E "^filtro|^INDICE|pendente:|ERRO|Traceback"; fi
  done
done
echo "FIM $(date +%H:%M)"
