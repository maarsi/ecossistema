#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""bench.py - bateria de avaliacao de modelos do ecossistema, com correcao automatica e gabarito deterministico.
Suites: codigo (testes executaveis), raciocinio (numerico, gabarito calculado aqui), visao (imagens geradas com valores conhecidos).
  bench.py --autoteste                      valida testes e gabaritos com solucoes de referencia
  bench.py --suite codigo|raciocinio|visao|todas [--modelos a,b] [--limite N]
Modelo de nuvem: prefixo "nuvem:" (so tarefas sinteticas, sem dado sigiloso).
"""
import argparse, base64, io, json, math, re, subprocess, sys, tempfile, time
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "bin"))
import llm
PY = "/home/mateus/env_transporte/bin/python"
RES = RAIZ / "bench" / "resultados"
IMG = RAIZ / "bench" / "imagens"

# ------------------------------------------------------------------ CODIGO
CODIGO = [
 {"id": "frota", "enunciado": "Funcao frota(tempo_percurso_ida_volta_min, tempo_terminal_min, headway_min) -> int: numero de veiculos em operacao, "
  "arredondado para cima, sendo o tempo de ciclo a soma do percurso de ida e volta com o tempo de terminal.",
  "testes": "assert frota(80,10,4)==23\nassert frota(60,0,10)==6\nassert frota(61,0,10)==7\nassert isinstance(frota(60,0,10),int)",
  "ref": "import math\ndef frota(a,b,h): return math.ceil((a+b)/h)"},
 {"id": "bpr", "enunciado": "Funcao bpr(t0, volume, capacidade, alpha=0.15, beta=4) -> float: tempo de viagem pela funcao BPR.",
  "testes": "assert abs(bpr(10,1000,1000)-11.5)<1e-9\nassert abs(bpr(10,0,1000)-10)<1e-9\nassert abs(bpr(5,2000,1000)-17.0)<1e-9",
  "ref": "def bpr(t0,v,c,alpha=0.15,beta=4): return t0*(1+alpha*(v/c)**beta)"},
 {"id": "logit", "enunciado": "Funcao logit_mnl(utilidades: dict) -> dict com as probabilidades do logit multinomial para cada alternativa. "
  "Deve ser numericamente estavel para utilidades grandes (ex.: 1000).",
  "testes": "import math\nr=logit_mnl({'a':0.0,'b':0.0}); assert abs(r['a']-0.5)<1e-9\n"
            "r=logit_mnl({'a':1000.0,'b':1000.0+math.log(3)}); assert abs(r['a']-0.25)<1e-6 and abs(r['b']-0.75)<1e-6\n"
            "assert abs(sum(logit_mnl({'x':-2,'y':1,'z':0.5}).values())-1)<1e-9",
  "ref": "import math\ndef logit_mnl(u):\n    m=max(u.values()); e={k:math.exp(v-m) for k,v in u.items()}; s=sum(e.values())\n    return {k:v/s for k,v in e.items()}"},
 {"id": "gtfs_headway", "enunciado": "Funcao headways_gtfs(stop_times) que recebe um pandas DataFrame com colunas trip_id, stop_id e departure_time "
  "no formato HH:MM:SS do GTFS (a hora pode passar de 24, ex.: 24:05:00). Retornar DataFrame com colunas stop_id e headway_medio_min: "
  "media, em minutos, dos intervalos entre partidas consecutivas em cada parada.",
  "testes": "import pandas as pd\nst=pd.DataFrame({'trip_id':['t1','t2','t3','t1','t2','t3'],'stop_id':['S1','S1','S1','S2','S2','S2'],"
            "'departure_time':['07:00:00','07:10:00','07:30:00','23:50:00','24:05:00','24:25:00']})\n"
            "d=dict(zip(headways_gtfs(st)['stop_id'],headways_gtfs(st)['headway_medio_min']))\n"
            "assert abs(d['S1']-15)<1e-6 and abs(d['S2']-17.5)<1e-6, d",
  "ref": "import pandas as pd\ndef headways_gtfs(st):\n    s=st.copy(); p=s['departure_time'].str.split(':',expand=True).astype(int)\n"
         "    s['m']=p[0]*60+p[1]+p[2]/60\n    r=s.sort_values('m').groupby('stop_id')['m'].apply(lambda x:x.diff().mean()).reset_index()\n"
         "    return r.rename(columns={'m':'headway_medio_min'})"},
 {"id": "duckdb_receita", "enunciado": "Funcao receita_por_linha(caminho_parquet) usando duckdb para consultar o arquivo Parquet diretamente "
  "(colunas linha, tarifa, passageiros). Retornar pandas DataFrame com colunas linha e receita (soma de tarifa*passageiros), "
  "ordenado por receita decrescente.",
  "testes": "import pandas as pd, tempfile, os\ndf=pd.DataFrame({'linha':['A','B','A','C','B'],'tarifa':[5.0,4.5,5.0,6.0,4.5],'passageiros':[100,200,50,10,20]})\n"
            "p=os.path.join(tempfile.mkdtemp(),'v.parquet'); df.to_parquet(p)\nr=receita_por_linha(p)\n"
            "assert list(r['linha'])==['B','A','C'], list(r['linha'])\nassert abs(float(r.iloc[0]['receita'])-990)<1e-6",
  "ref": "import duckdb\ndef receita_por_linha(p):\n    return duckdb.sql(f\"select linha, sum(tarifa*passageiros) receita from '{p}' group by linha order by receita desc\").df()"},
 {"id": "geo_comprimento", "enunciado": "Funcao comprimento_km(gdf) que recebe um GeoDataFrame de LineStrings em EPSG:4326 (Sao Paulo) e retorna "
  "o comprimento de cada linha em quilometros, reprojetando para SIRGAS 2000 UTM 23S (EPSG:31983).",
  "testes": "import geopandas as gpd\nfrom shapely.geometry import LineString\n"
            "g=gpd.GeoDataFrame(geometry=[LineString([(-46.63,-23.55),(-46.63,-23.56)])],crs='EPSG:4326')\n"
            "v=float(list(comprimento_km(g))[0]); assert 1.09<v<1.12, v",
  "ref": "def comprimento_km(g): return g.to_crs(31983).length/1000"},
]

# ------------------------------------------------------------------ RACIOCINIO (gabaritos calculados)
RAC = [
 {"id": "frota", "enunciado": "Uma linha de onibus tem tempo de percurso de ida e volta de 80 min, que NAO inclui o tempo de terminal. "
  "O tempo de terminal e de 10 min por ciclo. O headway e 4 min. Quantos veiculos em operacao sao necessarios?",
  "esperado": math.ceil(90 / 4), "tol": 0},
 {"id": "logit_bin", "enunciado": "Logit binomial: utilidade do onibus V_on = -1,2 e do carro V_car = -0,8. Qual a probabilidade de escolha do onibus? (4 casas decimais)",
  "esperado": 1 / (1 + math.exp(0.4)), "tol": 0.005},
 {"id": "elasticidade_arco", "enunciado": "A tarifa subiu de R$ 4,00 para R$ 4,40 e a demanda caiu de 10.000 para 9.500 passageiros por dia. "
  "Qual a elasticidade-preco da demanda pelo metodo do arco (ponto medio)? (3 casas decimais, com sinal)",
  "esperado": ((9500 - 10000) / 9750) / ((4.4 - 4.0) / 4.2), "tol": 0.01},
 {"id": "bpr", "enunciado": "Funcao BPR com t0 = 12 min, alfa = 0,15, beta = 4 e relacao volume/capacidade = 1,2. Qual o tempo de viagem em minutos? (2 casas)",
  "esperado": 12 * (1 + 0.15 * 1.2 ** 4), "tol": 0.05},
 {"id": "vpl", "enunciado": "Investimento de 100 no ano 0 e beneficios de 30 por ano do ano 1 ao ano 5, taxa de desconto de 10% ao ano. Qual o VPL? (2 casas)",
  "esperado": -100 + sum(30 / 1.1 ** t for t in range(1, 6)), "tol": 0.05},
 {"id": "little", "enunciado": "Chegam 1.200 passageiros por hora a uma estacao e cada um permanece em media 6 minutos nela. "
  "Pela lei de Little, quantos passageiros ha na estacao em media?", "esperado": 1200 * 6 / 60, "tol": 0.5},
 {"id": "capacidade", "enunciado": "Um metro opera com headway de 90 segundos e trens de 4 carros com 250 passageiros por carro. "
  "Qual a capacidade em passageiros por hora por sentido?", "esperado": 3600 / 90 * 4 * 250, "tol": 1},
 {"id": "valor_tempo", "enunciado": "Em um modelo logit, o coeficiente do tempo de viagem e -0,05 por minuto e o do custo e -0,25 por real. "
  "Qual o valor subjetivo do tempo em reais por HORA?", "esperado": 0.05 / 0.25 * 60, "tol": 0.1},
]
SUFIXO_RAC = ("\n\nResolva e termine com uma linha no formato exato: RESPOSTA: <numero> "
              "(apenas o numero, ponto como separador decimal, sem separador de milhar).")

# ------------------------------------------------------------------ VISAO (imagens com valores conhecidos)
def _fig_png(desenhar):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110); desenhar(ax, plt)
    b = io.BytesIO(); fig.tight_layout(); fig.savefig(b, format="png"); plt.close(fig); return b.getvalue()

def _barras(ax, plt):
    v = {"L1": 1200, "L2": 850, "L3": 1530, "L4": 640}; bs = ax.bar(v.keys(), v.values(), color="#4a7")
    for b_, x in zip(bs, v.values()): ax.text(b_.get_x() + b_.get_width() / 2, x + 20, str(x), ha="center")
    ax.set_title("Demanda diaria por linha (pass/dia)")

def _curva(ax, plt):
    h = list(range(5, 23)); base = {5: 300, 6: 1500, 7: 2400, 8: 1900, 9: 1100, 17: 1700, 18: 2100, 19: 1400}
    ax.plot(h, [base.get(x, 800) for x in h], marker="o"); ax.set_xticks(h); ax.grid(True)
    ax.set_title("Volume horario no corredor (veic/h)"); ax.set_xlabel("hora")

def _tabela(ax, plt):
    ax.axis("off"); t = ax.table(cellText=[["A", "42", "5,20"], ["B", "38", "4,80"], ["C", "57", "6,10"], ["D", "31", "5,50"]],
                                 colLabels=["Lote", "Frota", "Tarifa (R$)"], loc="center"); t.scale(1, 2); t.set_fontsize(12)
    ax.set_title("Quadro de lotes")

def _rede(ax, plt):
    pos = {"A": (0, 0), "B": (2, 1), "C": (4, 2), "D": (4, 0), "E": (6, 1)}
    arestas = {("A", "B"): 8, ("B", "C"): 11, ("B", "D"): 14, ("C", "E"): 9, ("D", "E"): 6}
    for (a, b), t in arestas.items():
        (x1, y1), (x2, y2) = pos[a], pos[b]; ax.plot([x1, x2], [y1, y2], "k-")
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, f"{t} min", ha="center", color="darkred", fontsize=11)
    for n, (x, y) in pos.items():
        ax.plot(x, y, "o", ms=22, color="#9cf"); ax.text(x, y, n, ha="center", va="center", fontsize=12, weight="bold")
    ax.axis("off"); ax.set_title("Rede com tempos de percurso por trecho")

def _mapa(ax, plt):
    import random; random.seed(3)
    ax.scatter([random.uniform(0, 10) for _ in range(9)], [random.uniform(0, 10) for _ in range(9)], c="blue", marker="o", label="Parada")
    ax.scatter([2, 5, 8], [8, 3, 6], c="red", marker="s", s=120, label="Terminal")
    ax.legend(); ax.set_title("Pontos da rede"); ax.grid(True)

def _num(txt):
    m = re.findall(r"\d+", txt.replace(".", "").replace(",", "")); return int(m[0]) if m else None

VIS = [
 {"id": "barras", "img": _barras, "pergunta": "Qual linha tem a maior demanda e qual o valor? Responda no formato: LINHA, VALOR",
  "checar": lambda r: "L3" in r.upper() and "1530" in r.replace(".", "").replace(",", "")},
 {"id": "curva_pico", "img": _curva, "pergunta": "Em que hora ocorre o maior volume? Responda so a hora (numero inteiro).", "checar": lambda r: _num(r) == 7},
 {"id": "tabela", "img": _tabela, "pergunta": "Qual a frota do lote C? Responda so o numero.", "checar": lambda r: _num(r) == 57},
 {"id": "rede", "img": _rede, "pergunta": "Qual o tempo indicado no trecho entre B e D? Responda so o numero.", "checar": lambda r: _num(r) == 14},
 {"id": "mapa_contagem", "img": _mapa, "pergunta": "Quantos terminais aparecem no grafico? Responda so o numero.", "checar": lambda r: _num(r) == 3},
]

# ------------------------------------------------------------------ EXECUCAO
def gerar(modelo, prompt, max_tokens, ctx=8192, imagem=None):
    t = time.time()
    if modelo.startswith("nuvem:"):
        try:
            txt, _, tout = llm.chamar_nuvem(modelo[6:], prompt, max_tokens, 0)
        except SystemExit as e:
            return f"[erro nuvem: {e}]", time.time() - t
        return llm.limpar_raciocinio(txt), time.time() - t
    j = {"model": modelo, "prompt": prompt, "stream": False, "keep_alive": "30m",
         "options": {"num_ctx": ctx, "num_predict": max_tokens, "temperature": 0}}
    if imagem:
        j["images"] = [base64.b64encode(imagem).decode()]
    # Modelos com modo de pensamento gastariam o limite de tokens raciocinando; desliga quando suportado.
    r = requests.post(f"{llm.OLLAMA}/api/generate", json={**j, "think": False}, timeout=900).json()
    if r.get("error") and "think" in str(r.get("error")).lower():
        r = requests.post(f"{llm.OLLAMA}/api/generate", json=j, timeout=900).json()
    if r.get("error"):
        return f"[ERRO API: {r['error'][:120]}]", time.time() - t
    return llm.limpar_raciocinio(r.get("response", "")), time.time() - t

def extrair_codigo(txt):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", txt, re.S); return m.group(1) if m else txt

def rodar_codigo(codigo, testes):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "t.py"; f.write_text(codigo + "\n\n" + testes, encoding="utf-8")
        try:
            r = subprocess.run([PY, str(f)], capture_output=True, text=True, timeout=90)
            linhas = r.stderr.strip().splitlines()
            erro = [l for l in linhas if re.match(r"^\w*(Error|Exception)\b", l)]
            return r.returncode == 0, ((erro or linhas or [""])[-1])[:160]
        except subprocess.TimeoutExpired:
            return False, "timeout"

def ler_numeros(txt):
    """Leituras possiveis do numero final. Formato ambiguo (ex.: 40.000) gera as duas leituras:
    erro de formatacao nao deve reprovar raciocinio correto."""
    m = re.findall(r"RESPOSTA:\s*\**\s*([-+]?\d[\d.,]*)", txt)
    s = m[-1] if m else (re.findall(r"[-+]?\d[\d.,]*", txt) or [""])[-1]
    s = s.rstrip(".,")
    cands = []
    if "," in s and "." in s:
        cands.append(s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", ""))
    elif "," in s:
        cands.append(s.replace(",", "."))
    else:
        cands.append(s)
        if re.fullmatch(r"-?[1-9]\d{0,2}(\.\d{3})+", s):
            cands.append(s.replace(".", ""))
    out = []
    for c in cands:
        try: out.append(float(c))
        except ValueError: pass
    return out


def suite_codigo(m, lim):
    out = []
    for t in CODIGO[:lim]:
        p = (f"Escreva em Python a seguinte funcao, com os imports necessarios. {t['enunciado']}\n"
             "Responda apenas com o codigo em um bloco ```python```, sem exemplos de uso.")
        txt, s = gerar(m, p, 4096)
        ok, det = rodar_codigo(extrair_codigo(txt), t["testes"])
        out.append({"tarefa": t["id"], "ok": ok, "seg": round(s, 1), "detalhe": det})
    return out

def suite_raciocinio(m, lim):
    out = []
    for t in RAC[:lim]:
        txt, s = gerar(m, t["enunciado"] + SUFIXO_RAC, 4096)
        vs = ler_numeros(txt); ok = any(abs(v - t["esperado"]) <= max(t["tol"], 1e-9) for v in vs); v = vs
        out.append({"tarefa": t["id"], "ok": ok, "seg": round(s, 1), "detalhe": f"resposta={v} esperado={round(t['esperado'], 4)}"})
    return out

def suite_visao(m, lim):
    out = []
    for t in VIS[:lim]:
        txt, s = gerar(m, t["pergunta"], 200, imagem=_fig_png(t["img"]))
        out.append({"tarefa": t["id"], "ok": bool(t["checar"](txt)), "seg": round(s, 1), "detalhe": txt.strip().replace("\n", " ")[:80]})
    return out


# ------------------------------------------------------------------ DOCUMENTOS (texto variado + PDF real com citacao de pagina)
def _doc_marcadores():
    import random; random.seed(11)
    temas = ["frota", "tarifa", "demanda", "headway", "terminal", "garagem", "bilhetagem", "subsidio", "corredor", "reajuste"]
    L = [f"Item {i}: a {random.choice(temas)} do lote {random.randint(1, 9)} sera revista em {random.randint(2027, 2035)} "
         f"conforme o anexo {random.choice('ABCDEFG')}." for i in range(1, 330)]
    L.insert(0, "MARCADOR_INICIO=ZEBRA"); L.insert(165, "MARCADOR_MEIO=TUCANO"); L.append("MARCADOR_FIM=GIRAFA")
    return "\n".join(L)

def _doc_artigo():
    import converter
    md, _ = converter.converter(RAIZ / "bench" / "dados" / "artigo_transformer.pdf")
    return md.read_text(encoding="utf-8")

def _tem_pagina(r, n):
    return bool(re.search(rf"p[aá]g(?:ina|\.)?\s*{n}\b", r.lower()))

DOC = [
 {"id": "marcadores", "doc": _doc_marcadores, "pergunta": "Liste os valores de todas as linhas que comecam com MARCADOR_.",
  "checar": lambda r: all(x in r.upper() for x in ("ZEBRA", "TUCANO", "GIRAFA"))},
 {"id": "tabela_valor_pagina", "doc": _doc_artigo, "pergunta": "Qual o BLEU EN-DE do Transformer (big) na tabela que compara BLEU e custo de treinamento? Informe valor e pagina.",
  "checar": lambda r: "28.4" in r.replace(",", ".") and _tem_pagina(r, 8)},
 {"id": "figura_pagina", "doc": _doc_artigo, "pergunta": "Em que pagina esta a legenda da Figura 1, que mostra a arquitetura do modelo? Informe a pagina.",
  "checar": lambda r: _tem_pagina(r, 3)},
 {"id": "texto_valor_pagina", "doc": _doc_artigo, "pergunta": "Qual a taxa de dropout residual do modelo base e em que pagina isso e informado?",
  "checar": lambda r: "0.1" in r.replace(",", ".") and _tem_pagina(r, 8)},
]

def suite_doc(m, lim):
    out = []
    for t in DOC[:lim]:
        txt, s = gerar(m, llm.montar_prompt(t["pergunta"], t["doc"]()), 300, ctx=16384)
        out.append({"tarefa": t["id"], "ok": bool(t["checar"](txt)), "seg": round(s, 1), "detalhe": txt.strip().replace("\n", " ")[:90]})
    return out

# ------------------------------------------------------------------ EMBEDDINGS (busca semantica com parafrase)
TRECHOS = [
 "O reajuste tarifario anual sera calculado pela variacao do IPCA acumulado nos doze meses anteriores a data-base do contrato.",
 "A frota operacional minima exigida e de 120 veiculos, com idade media maxima de cinco anos.",
 "Os veiculos deverao dispor de ar-condicionado e piso baixo para acessibilidade de pessoas com mobilidade reduzida.",
 "O descumprimento das partidas programadas sujeita a concessionaria a multa de 0,5% da receita diaria por viagem nao realizada.",
 "A pesquisa de origem e destino domiciliar tera amostra de 3% dos domicilios, estratificada por zona de trafego.",
 "O modelo de alocacao utilizara equilibrio do usuario com funcoes de desempenho do tipo BPR calibradas por contagens.",
 "A integracao tarifaria permitira ate duas transferencias gratuitas em um intervalo de noventa minutos.",
 "O prazo da concessao e de quinze anos, prorrogavel uma unica vez por igual periodo mediante reequilibrio.",
 "Os terminais de integracao deverao ter cobertura, bicicletario e sanitarios acessiveis.",
 "A remuneracao da concessionaria sera por passageiro transportado equivalente, com fator de ajuste pela qualidade do servico.",
 "As contagens volumetricas classificadas serao realizadas em dias uteis tipicos, de terca a quinta-feira, das 6h as 20h.",
 "A garantia de execucao contratual corresponde a 5% do valor estimado do contrato.",
]
CONSULTAS = [("Como o preco da passagem e corrigido todo ano?", 0), ("Qual a penalidade quando a empresa nao cumpre as viagens?", 3),
             ("Quanto tempo dura o contrato de operacao?", 7), ("Qual o tamanho da amostra do levantamento em domicilios?", 4),
             ("Quantas baldeacoes sem pagar o usuario pode fazer?", 6), ("Como a empresa operadora e paga?", 9),
             ("Em que dias e horarios sao feitas as contagens de trafego?", 10), ("Que exigencias existem para cadeirantes nos onibus?", 2),
             ("Qual o metodo de carregamento da rede viaria?", 5), ("Qual o valor da caucao do contrato?", 11)]

def suite_embeddings(m, lim):
    def emb(textos):
        r = requests.post(f"{llm.OLLAMA}/api/embed", json={"model": m, "input": textos, "keep_alive": "30m"}, timeout=300).json()
        if r.get("error"): raise RuntimeError(r["error"][:120])
        return r["embeddings"]
    def cos(a, b):
        return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
    t0 = time.time()
    try:
        E = emb(TRECHOS); Q = emb([q for q, _ in CONSULTAS[:lim]])
    except Exception as e:
        return [{"tarefa": "embed", "ok": False, "seg": 0, "detalhe": str(e)}]
    seg = (time.time() - t0) / max(1, len(Q)); out = []
    for (q, alvo), vq in zip(CONSULTAS, Q):
        ordem = sorted(range(len(E)), key=lambda i: -cos(vq, E[i]))
        out.append({"tarefa": f"q{alvo:02d}", "ok": ordem[0] == alvo, "seg": round(seg, 2),
                    "detalhe": f"posicao do trecho certo: {ordem.index(alvo) + 1}"})
    return out

SUITES = {"codigo": (suite_codigo, ["qwen2.5-coder:14b-fast", "qwen2.5:14b", "deepseek-r1:14b-fast", "glm4:9b"]),
          "raciocinio": (suite_raciocinio, ["deepseek-r1:14b-fast", "qwen2.5:14b", "glm4:9b", "qwen2.5-coder:14b-fast",
                                            "nuvem:nvidia/nemotron-3-ultra-550b-a55b"]),
          "visao": (suite_visao, ["qwen2.5vl:7b"]),
          "doc": (suite_doc, ["qwen2.5:14b"]),
          "embeddings": (suite_embeddings, ["nomic-embed-text:latest"])}

def autoteste():
    falhas = 0
    for t in CODIGO:
        ok, det = rodar_codigo(t["ref"], t["testes"]); falhas += not ok
        print(f"  codigo/{t['id']:16} referencia {'OK' if ok else 'FALHOU ' + det}")
    for t in RAC:
        print(f"  raciocinio/{t['id']:18} gabarito = {round(t['esperado'], 4)}")
    IMG.mkdir(parents=True, exist_ok=True)
    for t in VIS:
        (IMG / f"{t['id']}.png").write_bytes(_fig_png(t["img"]))
    print(f"  visao: {len(VIS)} imagens geradas em {IMG}")
    assert len(_doc_marcadores()) > 20000; art = _doc_artigo(); ok = "28.4" in art and "Figure 1" in art; falhas += not ok
    print(f"  doc: texto de marcadores e artigo convertido ({len(art)} caracteres) {'OK' if ok else 'FALHOU'}")
    ok = len(TRECHOS) == 12 and all(0 <= a < 12 for _, a in CONSULTAS); falhas += not ok
    print(f"  embeddings: {len(TRECHOS)} trechos, {len(CONSULTAS)} consultas {'OK' if ok else 'FALHOU'}")
    for s, esp in [("RESPOSTA: 40000", 40000), ("RESPOSTA: 40.000", 40000), ("RESPOSTA: 0,4013", 0.4013),
                   ("RESPOSTA: **-0.538**", -0.538), ("RESPOSTA: 15.73", 15.73), ("RESPOSTA: 1.234,5", 1234.5)]:
        v = ler_numeros(s); ok = esp in v; falhas += not ok; print(f"  leitor '{s}' -> {v} {'OK' if ok else 'FALHOU'}")
    print("AUTOTESTE:", "APROVADO" if not falhas else f"{falhas} FALHA(S)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--suite"); ap.add_argument("--modelos")
    ap.add_argument("--limite", type=int, default=99); ap.add_argument("--autoteste", action="store_true")
    a = ap.parse_args()
    if a.autoteste:
        autoteste(); sys.exit()
    todas = []
    for nome in (SUITES if a.suite == "todas" else [a.suite]):
        f, padrao = SUITES[nome]
        for m in (a.modelos.split(",") if a.modelos else padrao):
            r = f(m, a.limite)
            for x in r: x.update({"suite": nome, "modelo": m})
            todas += r
            ac = sum(x["ok"] for x in r)
            print(f"{nome:10} {m:42} {ac}/{len(r)}  t_medio={sum(x['seg'] for x in r)/len(r):.1f}s  "
                  + " ".join(("+" if x["ok"] else "-") + x["tarefa"] for x in r), flush=True)
    arq = RES / f"{time.strftime('%Y%m%d_%H%M')}_{a.suite}.json"
    arq.write_text(json.dumps(todas, indent=1, ensure_ascii=False), encoding="utf-8"); print("resultados:", arq)
