"""Suite REDACAO (22/11/2026): o papel redacao-nuvem nunca havia sido medido em redacao.
Conferencia AUTOMATICA, sem juiz por modelo, baseada nas regras de Mateus:
  R1 fidelidade numerica: todos os numeros dados aparecem e nenhum numero novo e inventado
  R2 sem travessao (— ou – usado como pausa)
  R3 obedece ao numero de frases pedido
  R4 nao inventa referencia (nem DOI, URL, 'et al.' ou autor-ano) quando nenhuma fonte foi dada
  R5 portugues do Brasil: sem marcadores lusitanos (facto, equipa, registo, utilizador, autocarro)
Material sintetico, sem dado de cliente. Duas passadas por modelo. Cada chamada com prazo de 90 s."""
import json, re, sys, time, concurrent.futures as cf
sys.path.insert(0, "/home/mateus/ecossistema/bin"); import llm
ITENS = [
 {"id": "R1", "prompt": "Escreva UM paragrafo de metodologia, em portugues do Brasil, usando EXATAMENTE estes dados e nenhum outro numero: "
  "pesquisa de contagem classificada em 6 postos; 12 horas por posto; fator de expansao diaria de 1,18; volume medio de 4.350 veiculos por dia. Nao use travessao.",
  "numeros": ["6", "12", "1,18", "4.350"]},
 {"id": "R2", "prompt": "Reescreva em portugues do Brasil, sem travessao e sem anglicismo desnecessario, mantendo o sentido: "
  "'O headway — que foi medido no pico da manha — ficou acima do planejado; o feedback dos operadores — ainda preliminar — confirma o gap.'", "numeros": []},
 {"id": "R3", "prompt": "Resuma em EXATAMENTE 3 frases, em portugues do Brasil: a calibracao de um modelo de escolha discreta compara as "
  "participacoes modais observadas e estimadas, ajusta as constantes especificas de alternativa ate a diferenca ficar abaixo da tolerancia, "
  "e confere os sinais e a magnitude dos coeficientes de tempo e custo, cuja razao fornece o valor do tempo implicito.", "frases": 3, "numeros": []},
 {"id": "R4", "prompt": "Escreva duas frases, em portugues do Brasil, afirmando que a elasticidade da demanda do transporte coletivo em relacao a tarifa "
  "costuma ser inelastica no curto prazo. NAO cite autores, anos, DOI nem links, porque nenhuma fonte foi fornecida.", "numeros": []},
]
LUSO = re.compile(r"\b(facto|equipa|registo|utilizador|autocarro|ecr[ãa]|telem[óo]vel)\b", re.I)
REF = re.compile(r"doi|https?://|www\.|et al\.|\(\s*[A-Z][a-z]+[^)]*\d{4}\s*\)|\b(19|20)\d{2}\b")
def conferir(it, txt):
    falhas = []
    if "—" in txt or re.search(r"\s–\s", txt): falhas.append("travessao")
    if LUSO.search(txt): falhas.append("lusitano")
    if it["numeros"]:
        nums = set(re.findall(r"\d[\d.,]*\d|\d", txt))
        faltam = [n for n in it["numeros"] if n not in nums]
        extras = [n for n in nums if n not in it["numeros"]]
        if faltam: falhas.append(f"faltam {faltam}")
        if extras: falhas.append(f"inventou {extras[:4]}")
    if it.get("frases"):
        n = len([f for f in re.split(r"(?<=[.!?])\s+", txt.strip()) if len(f) > 3])
        if n != it["frases"]: falhas.append(f"{n} frases")
    if it["id"] == "R4" and REF.search(txt): falhas.append("referencia inventada")
    return falhas
CAND = [("nvidia", "mistralai/mistral-large-4-1t-a52b"), ("nvidia", "moonshotai/kimi-k3.1-pro"),
        ("nvidia", "minimaxai/minimax-m3.1-flash"), ("nvidia", "z-ai/glm-5.3-flash"), ("nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b"),
        ("nvidia", "nvidia/nemotron-3-ultra-550b-a55b"), ("google", "gemini-4-argon"), ("moonshot", "kimi-k3"),
        ("deepseek", "deepseek-v4-pro"), ("deepseek", "deepseek-flash")]
def chamar(p, m, prompt):
    if p == "google": return llm.chamar_google(m, prompt, 2048, 0.2)[0]
    return llm.chamar_nuvem(m, prompt, 2048, 0.2, p, timeout=60)[0]   # prazo NA chamada: o da thread nao interrompia
def rodar(pm, it):
    p, m = pm; t0 = time.time()
    with cf.ThreadPoolExecutor(1) as ex:
        fut = ex.submit(chamar, p, m, it["prompt"])
        try: txt = llm.limpar_raciocinio(fut.result(timeout=150)); return conferir(it, txt), time.time()-t0, txt
        except cf.TimeoutError: return ["SEM RESPOSTA EM 90 s"], 90.0, ""
        except SystemExit as e: return [f"ERRO {str(e)[:80]}"], time.time()-t0, ""
        except Exception as e: return [f"SEM RESPOSTA ({type(e).__name__})" if "Timeout" in type(e).__name__ else f"ERRO {type(e).__name__}"], time.time()-t0, ""
res = []
for pm in CAND:
    acertos, tempos, erros = 0, [], []
    for passada in (1, 2):
        for it in ITENS:
            f, s, txt = rodar(pm, it)
            if f and (f[0].startswith("ERRO") or f[0].startswith("SEM")):
                erros.append(f[0]); break
            acertos += not f; tempos.append(s)
            res.append({"provedor": pm[0], "modelo": pm[1], "passada": passada, "item": it["id"], "falhas": f, "s": round(s, 1), "texto": txt[:600]})
        if erros: break
    med = sorted(tempos)[len(tempos)//2] if tempos else 0
    print(f"{pm[0]:8s} {pm[1]:42s} {('%d/8' % acertos) if not erros else 'FORA ':5s} mediana {med:5.1f}s {erros[0][:70] if erros else ''}", flush=True)
json.dump(res, open("/home/mateus/ecossistema/bench/resultados/20261122_suite_redacao.json", "w"), ensure_ascii=False, indent=1)
print("FIM")
