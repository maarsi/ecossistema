#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Pontuador do braco B da rodada LOCAL de 28/11/2026 (bracos L e N: embeddinggemma-2 sobre o texto
do braco vencedor), com PROVA DO INSTRUMENTO antes de qualquer numero novo: as metricas dos seis
bracos publicados no ADENDO_07 tem de sair exatamente iguais as publicadas. Se nao sairem, o script
encerra e o braco nao entra no relatorio.

Nao substitui bat_pontuar.py nem bat_pontuar_20261128.py e nao escreve nos arquivos deles. Mesma
funcao de metricas, mesmo gabarito (ADENDO_04, 28 perguntas pontuaveis), mesma granularidade de
pagina. Grava derpr/resultados/resultado_locais_20261128.json e o ADENDO_14 da suite.
"""
import datetime
import hashlib
import json
import pathlib
import statistics as st
import sys

B = pathlib.Path.home() / "ecossistema/bench"


def metricas(rank, gab):
    pos = []
    for q, pg in gab.items():
        if q not in rank:
            continue
        r = rank[q]
        pos.append(r.index(pg) + 1 if pg in r else len(r) + 1)
    n = len(pos)
    return {"n": n, "acerto1": sum(p == 1 for p in pos) / n, "acerto5": sum(p <= 5 for p in pos) / n,
            "pos_mediana": st.median(pos), "pos_media": round(sum(pos) / n, 2)}


# ---- autoteste do pontuador (as mesmas 4 assercoes de bat_pontuar.py)
g = {"Q1": 3, "Q2": 7}
assert metricas({"Q1": [3, 1, 2], "Q2": [7, 1, 2]}, g)["acerto1"] == 1.0
assert metricas({"Q1": [1, 2, 3], "Q2": [1, 2, 7]}, g)["acerto1"] == 0.0
assert metricas({"Q1": [1, 2, 3], "Q2": [1, 2, 7]}, g)["acerto5"] == 1.0
assert metricas({"Q1": [1, 2, 3], "Q2": [1, 2, 7]}, g)["pos_mediana"] == 3
print("  autoteste do pontuador: PASSOU (4 assercoes)")

a4 = json.loads((B / "suites/recuperacao_anuario_derpr_ADENDO_04.json").read_text())
gab = {r["id"]: r["gabarito_pagina"] for r in a4["respostas"] if r["gabarito_pagina"] is not None}
ausentes = [r["id"] for r in a4["respostas"] if r["gabarito_pagina"] is None]
assert len(gab) == 28, f"esperava 28 pontuaveis, achei {len(gab)}"
print(f"  gabarito: {len(gab)} pontuaveis, ausentes {', '.join(ausentes)}")

NOMES = {"A": "Docling sem OCR", "B": "Docling com OCR + qwen3-embedding:4b",
         "C": "ColQwen2.5 (interacao tardia)", "D": "nemotron embed-vl (denso)",
         "E": "D + reordenador VL (local)", "G": "Nemotron-3.5-Parse (pesos locais)",
         "H": "nemotron-ocr-v2 (ingles)", "I": "OCRmyPDF por+eng -> PyMuPDF",
         "J": "B + rerank-8b da nuvem (top-20)", "K": "nemotron-3.5-parse da nuvem",
         "L": "texto de B + embeddinggemma-2 (query/document)",
         "N": "texto de B + embeddinggemma-2 (QuestionAnswering/Document)"}


def avaliar(br):
    passadas, meta = [], None
    for p in (1, 2, 3):
        f = B / f"derpr/rank/{br}_p{p}.json"
        if f.exists():
            d = json.loads(f.read_text())
            passadas.append(d)
            meta = meta or d
    if not passadas:
        return {"status": "NAO EXECUTADO"}
    ms = [metricas(x["rank"], gab) for x in passadas]
    iguais = len({json.dumps(x["rank"], sort_keys=True) for x in passadas}) == 1
    out = {"status": "OK", "nome": NOMES[br], "passadas": len(ms),
           "acerto1": round(100 * st.mean(m["acerto1"] for m in ms), 1),
           "acerto5": round(100 * st.mean(m["acerto5"] for m in ms), 1),
           "acerto1_desvio": round(100 * (st.stdev([m["acerto1"] for m in ms]) if len(ms) > 1 else 0), 1),
           "acerto5_desvio": round(100 * (st.stdev([m["acerto5"] for m in ms]) if len(ms) > 1 else 0), 1),
           "acerto1_por_passada": [round(100 * m["acerto1"], 1) for m in ms],
           "acerto5_por_passada": [round(100 * m["acerto5"], 1) for m in ms],
           "pos_mediana": st.median([m["pos_mediana"] for m in ms]),
           "pos_media": round(st.mean(m["pos_media"] for m in ms), 2),
           "rankings_identicos_entre_passadas": iguais}
    for campo in ("embedder", "dim", "revisao", "runtime", "prompt_nome_consulta",
                  "prompt_nome_documento", "seg_indexacao", "seg_consulta",
                  "vram_pico_torch_MB"):
        if campo in (meta or {}):
            out[campo] = meta[campo]
    return out


# ---- PROVA DO INSTRUMENTO: reproduzir o ADENDO_07
a7 = json.loads((B / "suites/recuperacao_anuario_derpr_ADENDO_07.json").read_text())["resultado"]
divergencias = []
for br, pub in a7.items():
    v = avaliar(br)
    for campo in ("acerto1", "acerto5", "pos_media"):
        if abs(v[campo] - pub[campo]) > 1e-9:
            divergencias.append(f"{br}.{campo}: pontuador {v[campo]} contra ADENDO_07 {pub[campo]}")
if divergencias:
    print("  PROVA DO INSTRUMENTO FALHOU:")
    for d in divergencias:
        print("   ", d)
    sys.exit("rodada invalida: o pontuador nao reproduz o ADENDO_07")
print(f"  prova do instrumento: os {len(a7)} bracos do ADENDO_07 reproduzidos exatamente "
      "(acerto@1, acerto@5 e posicao media)")

BRACOS = ("A", "B", "C", "D", "E", "G", "H", "I", "J", "K", "L", "N")
res = {br: avaliar(br) for br in BRACOS}

# ---- criterio declarado no pre-registro de 28/11 e no seu ADENDO 01
EMPATE = 100 / len(gab)                     # 1 pergunta = 3,57 pontos percentuais
vL, vN, vB = res["L"], res["N"], res["B"]
veredito_L = {
    "criterio": ("L (principal) supera B no acerto@5 por mais que o empate tecnico de 1 pergunta "
                 "(na pratica 3 perguntas, conforme o criterio de 'vencer por 2 itens ou mais' do "
                 "pre-registro aplicado a esta amostra) E nao perde para B no acerto@1 por mais "
                 "que 1 pergunta"),
    "delta_acerto5": round(vL["acerto5"] - vB["acerto5"], 1),
    "delta_acerto1": round(vL["acerto1"] - vB["acerto1"], 1),
    "supera_no_5": vL["acerto5"] - vB["acerto5"] > 2 * EMPATE,
    "nao_perde_no_1": vB["acerto1"] - vL["acerto1"] <= EMPATE,
}
veredito_L["atendido"] = veredito_L["supera_no_5"] and veredito_L["nao_perde_no_1"]
exploratorio_N = {"papel": "EXPLORATORIO, nao decide veredito (ADENDO 01 ao pre-registro)",
                  "delta_acerto5_contra_B": round(vN["acerto5"] - vB["acerto5"], 1),
                  "delta_acerto1_contra_B": round(vN["acerto1"] - vB["acerto1"], 1),
                  "delta_acerto5_contra_L": round(vN["acerto5"] - vL["acerto5"], 1),
                  "delta_acerto1_contra_L": round(vN["acerto1"] - vL["acerto1"], 1)}

# ---- teto alcancavel: onde a pagina certa nem aparece, nao ha o que ordenar
def teto(br):
    r = json.loads((B / f"derpr/rank/{br}_p1.json").read_text())["rank"]
    return round(100 * sum(1 for q, pg in gab.items() if q in r and pg in r[q]) / len(gab), 1)


saida = {"gerado_em": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
         "corpus_sha256": "c19be5398997a7ae18117ac9cdd48ee866757a293652e5f4b26f7e689368649c",
         "gabarito_sha256": hashlib.sha256(
             (B / "suites/recuperacao_anuario_derpr_ADENDO_04.json").read_bytes()).hexdigest(),
         "texto_de_origem_sha256": {
             f"B_p{p}": hashlib.sha256((B / f"derpr/textos/B_p{p}.json").read_bytes()).hexdigest()
             for p in (1, 2, 3)},
         "perguntas_pontuaveis": len(gab), "ausentes": ausentes,
         "empate_tecnico_pontos": round(EMPATE, 2),
         "prova_do_instrumento": f"os {len(a7)} bracos do ADENDO_07 reproduzidos exatamente",
         "bracos": res, "veredito_L": veredito_L, "exploratorio_N": exploratorio_N}
alvo = B / "derpr/resultados/resultado_locais_20261128.json"
alvo.write_text(json.dumps(saida, ensure_ascii=False, indent=1))

print(f"\n  {'br':<4}{'ferramenta':<48}{'@1':>7}{'@5':>7}{'dp@1':>6}{'dp@5':>6}{'pos.med':>9}{'ident':>7}")
print("  " + "-" * 94)
for br in BRACOS:
    v = res[br]
    if v.get("status") != "OK":
        print(f"  {br:<4}{'NAO EXECUTADO':<48}")
        continue
    print(f"  {br:<4}{v['nome']:<48}{v['acerto1']:>6.1f}%{v['acerto5']:>6.1f}%"
          f"{v['acerto1_desvio']:>6.1f}{v['acerto5_desvio']:>6.1f}{v['pos_media']:>9.2f}"
          f"{'sim' if v['rankings_identicos_entre_passadas'] else 'nao':>7}")
print(f"\n  empate tecnico = 1 pergunta = {EMPATE:.2f} pontos percentuais")
print(f"  veredito L (principal): {'ATENDIDO' if veredito_L['atendido'] else 'NAO ATENDIDO'} "
      f"(@5 {veredito_L['delta_acerto5']:+.1f}, @1 {veredito_L['delta_acerto1']:+.1f} contra B)")
print(f"  N (exploratorio): @5 {exploratorio_N['delta_acerto5_contra_B']:+.1f}, "
      f"@1 {exploratorio_N['delta_acerto1_contra_B']:+.1f} contra B; "
      f"@5 {exploratorio_N['delta_acerto5_contra_L']:+.1f}, "
      f"@1 {exploratorio_N['delta_acerto1_contra_L']:+.1f} contra L")
print("  gravado em", alvo)
