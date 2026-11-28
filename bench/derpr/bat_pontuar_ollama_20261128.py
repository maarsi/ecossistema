#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Pontuador do braco B da rodada LOCAL de 28/11/2026 na versao OLLAMA 0.40.19.

Irmao de bat_pontuar_locais_20261128.py, com a mesma funcao de metricas, o mesmo gabarito
(ADENDO_04, 28 perguntas pontuaveis), a mesma granularidade de pagina e a MESMA PROVA DO
INSTRUMENTO: os seis bracos publicados no ADENDO_07 tem de sair exatamente iguais aos publicados,
ou o script encerra e o braco nao entra no relatorio.

Acrescenta os tres bracos medidos em 0.40.19 (P, Q, R) e muda o LADO DA COMPARACAO: o veredito sai
de P (candidato pelo Ollama) contra R (titular remedido no MESMO Ollama), nao mais contra o braco B
do ADENDO_07, que foi medido em outra versao de servidor. Nenhum adendo anterior e tocado; o
resultado sai como ADENDO_15, o numero seguinte ao ultimo existente.

Uso: bat_pontuar_ollama_20261128.py
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

NOMES = {"A": "Docling sem OCR", "B": "Docling com OCR + qwen3-embedding:4b (historico, 0.34.0)",
         "C": "ColQwen2.5 (interacao tardia)", "D": "nemotron embed-vl (denso)",
         "E": "D + reordenador VL (local)", "G": "Nemotron-3.5-Parse (pesos locais)",
         "H": "nemotron-ocr-v2 (ingles)", "I": "OCRmyPDF por+eng -> PyMuPDF",
         "J": "B + rerank-8b da nuvem (top-20)", "K": "nemotron-3.5-parse da nuvem",
         "L": "embeddinggemma-2 por sentence-transformers (query/document)",
         "N": "embeddinggemma-2 por sentence-transformers (QuestionAnswering/Document)",
         "P": "embeddinggemma-2:740m pelo Ollama 0.40.19 (query/document)",
         "Q": "embeddinggemma-2:270m pelo Ollama 0.40.19 (query/document)",
         "R": "qwen3-embedding:4b pelo Ollama 0.40.19 (TITULAR desta rodada)"}


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
    for campo in ("embedder", "digest", "dim", "revisao", "runtime", "ollama",
                  "prompt_nome_consulta", "prompt_nome_documento", "seg_indexacao",
                  "seg_consulta", "vram_pico_MB", "vram_pico_torch_MB",
                  "processador_ollama_ps"):
        if campo in (meta or {}):
            out[campo] = meta[campo]
    return out


# ---- PROVA DO INSTRUMENTO: reproduzir o ADENDO_07 antes de produzir numero novo
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

BRACOS = ("A", "B", "C", "D", "E", "G", "H", "I", "J", "K", "L", "N", "P", "Q", "R")
res = {br: avaliar(br) for br in BRACOS}

EMPATE = 100 / len(gab)                     # 1 pergunta = 3,57 pontos percentuais
vP, vQ, vR, vL = res["P"], res["Q"], res["R"], res["L"]
veredito = {
    "comparacao": "P (embeddinggemma-2:740m pelo Ollama 0.40.19) contra R (qwen3-embedding:4b "
                  "pelo MESMO Ollama 0.40.19)",
    "criterio": ("vencer exige superar R no acerto@5 por mais que 2 perguntas (criterio de 'vencer "
                 "por 2 itens ou mais' do pre-registro) E nao perder para R no acerto@1 por mais "
                 "que o empate tecnico de 1 pergunta"),
    "delta_acerto5": round(vP["acerto5"] - vR["acerto5"], 1),
    "delta_acerto1": round(vP["acerto1"] - vR["acerto1"], 1),
    "supera_no_5": vP["acerto5"] - vR["acerto5"] > 2 * EMPATE,
    "nao_perde_no_1": vR["acerto1"] - vP["acerto1"] <= EMPATE,
}
veredito["atendido"] = veredito["supera_no_5"] and veredito["nao_perde_no_1"]

# ---- previsao do pre-registro: 270m e 740m dao embedding IDENTICO em texto (manifesto: mesma
# camada de modelo 111e84992a04; a diferenca e so um projector de imagem/audio no 740m)
previsao = {"enunciada_em": "pre-registro, secao 'Braco B', antes de medir",
            "texto": "as tags 270m e 740m dariam embedding identico numa suite de TEXTO",
            "rank_identico_P_vs_Q": all(
                json.loads((B / f"derpr/rank/P_p{p}.json").read_text())["rank"]
                == json.loads((B / f"derpr/rank/Q_p{p}.json").read_text())["rank"]
                for p in (1, 2, 3)
                if (B / f"derpr/rank/P_p{p}.json").exists()
                and (B / f"derpr/rank/Q_p{p}.json").exists()),
            "delta_acerto1": round(vQ["acerto1"] - vP["acerto1"], 1),
            "delta_acerto5": round(vQ["acerto5"] - vP["acerto5"], 1)}

# ---- os dois caminhos do mesmo peso, que a ATUALIZACAO DO AMBIENTE manda registrar juntos
dois_caminhos = {"Ollama 0.40.19 (P)": {"acerto1": vP["acerto1"], "acerto5": vP["acerto5"],
                                        "pos_media": vP["pos_media"], "dim": vP.get("dim")},
                 "sentence-transformers (L)": {"acerto1": vL["acerto1"], "acerto5": vL["acerto5"],
                                               "pos_media": vL["pos_media"], "dim": vL.get("dim")},
                 "delta_acerto1_ollama_menos_st": round(vP["acerto1"] - vL["acerto1"], 1),
                 "delta_acerto5_ollama_menos_st": round(vP["acerto5"] - vL["acerto5"], 1)}

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
         "bracos": res, "veredito": veredito,
         "previsao_do_pre_registro_270m_vs_740m": previsao,
         "dois_caminhos_do_mesmo_peso": dois_caminhos}
alvo = B / "derpr/resultados/resultado_locais_ollama_20261128.json"
alvo.write_text(json.dumps(saida, ensure_ascii=False, indent=1))

print(f"\n  {'br':<4}{'ferramenta':<58}{'@1':>7}{'@5':>7}{'dp@1':>6}{'dp@5':>6}{'pos.med':>9}{'ident':>7}")
print("  " + "-" * 104)
for br in BRACOS:
    v = res[br]
    if v.get("status") != "OK":
        print(f"  {br:<4}{NOMES[br][:58]:<58}{'NAO EXECUTADO':>20}")
        continue
    print(f"  {br:<4}{v['nome'][:58]:<58}{v['acerto1']:>6.1f}%{v['acerto5']:>6.1f}%"
          f"{v['acerto1_desvio']:>6.1f}{v['acerto5_desvio']:>6.1f}{v['pos_media']:>9.2f}"
          f"{'sim' if v['rankings_identicos_entre_passadas'] else 'nao':>7}")
print(f"\n  empate tecnico = 1 pergunta = {EMPATE:.2f} pontos percentuais")
print(f"  VEREDITO P contra R: {'ATENDIDO' if veredito['atendido'] else 'NAO ATENDIDO'} "
      f"(@5 {veredito['delta_acerto5']:+.1f}, @1 {veredito['delta_acerto1']:+.1f})")
print(f"  previsao 270m == 740m: rank identico nas passadas = "
      f"{previsao['rank_identico_P_vs_Q']}, @1 {previsao['delta_acerto1']:+.1f}, "
      f"@5 {previsao['delta_acerto5']:+.1f}")
print(f"  dois caminhos do mesmo peso: Ollama @1 {vP['acerto1']:.1f}% @5 {vP['acerto5']:.1f}% "
      f"contra sentence-transformers @1 {vL['acerto1']:.1f}% @5 {vL['acerto5']:.1f}%")
print("  gravado em", alvo)
