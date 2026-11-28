#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Resumo das linhas de resultado da rodada local de 28/11/2026, para a tabela do relatorio.

Le os jsonl de bracos/suites e devolve, por modelo e suite: acerto por passada, latencia mediana e
maxima, tokens/s de prefill e de geracao, VRAM de pico, fracao em CPU do `ollama ps`, cortes por
orcamento de saida e quantas vezes o `think: false` foi ignorado. Nada e recalculado a partir de
texto: todos os campos saem do dado bruto gravado durante a medicao.

Uso: resumo_locais_20261128.py
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

R = Path(__file__).resolve().parent / "resultados"

for braco in ("A", "C", "D"):
    f = R / f"20261128_locais_{braco}.jsonl"
    if not f.exists():
        print(f"\n### BRACO {braco}: sem arquivo")
        continue
    g = defaultdict(list)
    for l in f.read_text(encoding="utf-8").splitlines():
        d = json.loads(l)
        g[(d["modelo"], d["suite"], d["passada"])].append(d)
    print(f"\n### BRACO {braco}  ({f.name})")
    print(f"{'modelo':<44}{'suite':<11}{'p':>2}{'acerto':>8}{'med_s':>7}{'max_s':>7}"
          f"{'ger':>7}{'pre':>9}{'VRAM':>7}{'proc':>18}{'crt':>4}{'thk':>4}{'ngpu':>5}  itens")
    for (modelo, suite, p), xs in sorted(g.items()):
        segs = sorted(x["seg"] for x in xs)
        tg = [x["tps_geracao"] for x in xs if x.get("tps_geracao")]
        tp = [x["tps_prefill"] for x in xs if x.get("tps_prefill")]
        print(f"{modelo:<44}{suite:<11}{p:>2}"
              f"{sum(x['ok'] for x in xs):>4}/{len(xs):<3}"
              f"{st.median(segs):>7.1f}{segs[-1]:>7.1f}"
              f"{(sum(tg) / len(tg) if tg else 0):>7.1f}{(sum(tp) / len(tp) if tp else 0):>9.1f}"
              f"{max(x['vram_pico_MB'] for x in xs):>7}"
              f"{str(xs[0].get('processador_ollama_ps')):>18}"
              f"{sum(x.get('done_reason') == 'length' for x in xs):>4}"
              f"{sum(bool(x.get('ignorou_think_false')) for x in xs):>4}"
              f"{str(xs[0].get('num_gpu_pedido')):>5}  "
              + " ".join(("+" if x["ok"] else "-") + x["tarefa"] for x in xs))
        erros = {str(x.get("erro"))[:90] for x in xs if x.get("erro")}
        for e in erros:
            print(f"{'':>44}  ERRO: {e}")

for nome in ("20261128_locais_B_suite_embeddings_ollama.jsonl",
             "20261128_locais_B_suite_embeddings.jsonl"):
    f = R / nome
    if not f.exists():
        continue
    g = defaultdict(list)
    for l in f.read_text(encoding="utf-8").splitlines():
        d = json.loads(l)
        g[(d["modelo"], d["passada"])].append(d)
    print(f"\n### SUITE embeddings do bench.py  ({nome})")
    for (modelo, p), xs in sorted(g.items()):
        print(f"  {modelo:<48} p{p} {sum(x['ok'] for x in xs)}/{len(xs)}  dim {xs[0]['dim']:>5}  "
              f"runtime {xs[0].get('runtime')}  "
              f"posicoes={[x['posicao_do_trecho_certo'] for x in xs]}")
