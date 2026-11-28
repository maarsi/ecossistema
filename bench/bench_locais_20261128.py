#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""Rodada LOCAL de 28/11/2026: candidatos novos contra os titulares nas suites raciocinio, doc,
codigo e visao. Pre-registro em /mnt/nvme_lexar/bench_locais_20261128/logs/PRE_REGISTRO.md.

Por que nao bench.py direto: o gerar() do bench.py devolve so o texto e o tempo de parede. Esta
rodada exige eval_count, eval_duration, prompt_eval_count e prompt_eval_duration (que estao na
resposta do Ollama e sao descartados ali), a VRAM de pico (que nao esta em resposta nenhuma) e a
fracao em CPU lida de `ollama ps` quando houver offload. Os ENUNCIADOS, GABARITOS e CONFERIDORES
vem IMPORTADOS de bench.py: a suite medida e a mesma, nao uma copia que derivou.

Irmao mais velho deste arquivo: bench_local_20261128.py, da rodada NVIDIA do mesmo dia. Este
acrescenta a suite visao, o prefixo hf: (modelo servido por transformers fora do Ollama, para o
candidato que o Ollama 0.34.0 recusa por versao) e a saida por braco.

Parametros, iguais nos dois lados de cada braco: temperature 0, think desligado quando o modelo
aceita, num_predict e num_ctx por suite (codigo 4096/8192, raciocinio 4096/8192, doc 300/16384,
visao 200/8192).

Uso: bench_locais_20261128.py --braco A --modelos a,b [--suites raciocinio,doc] [--passadas 2]
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "bin"))
sys.path.insert(0, str(RAIZ / "bench"))
import llm      # noqa: E402
import bench    # noqa: E402

PARAM = {"codigo": (4096, 8192), "raciocinio": (4096, 8192), "doc": (2048, 16384),
         "visao": (1024, 8192)}
SERVIDOR_HF = "http://127.0.0.1:8765/gerar"

# Versao do servidor, exigida em toda linha de resultado pela ATUALIZACAO DO AMBIENTE de 14h10.
# Medida do binario, nao suposta.
VERSAO_OLLAMA = subprocess.run(["ollama", "--version"], capture_output=True,
                               text=True).stdout.strip().split()[-1]


def limpar(texto, thinking=None):
    """llm.limpar_raciocinio() casa apenas `<think>...</think>` COMPLETO. No Ollama 0.40.19, com
    `think: false`, o qwen3:30b-a3b ignora o pedido, raciocina, e entrega o raciocinio dentro de
    `response` SEM a etiqueta de abertura e COM a de fechamento. O regex nao casa e o raciocinio
    fica no texto. Medido por execucao as 14:12 de 28/11/2026 (eval_count 814, `</think>` presente
    e `<think>` ausente). Aqui se corta tudo o que vem ANTES do ultimo `</think>`, o que cobre os
    dois formatos, e o campo `thinking` (que o 0.40.19 usa quando `think: true`) nunca se soma ao
    texto pontuado."""
    t = llm.limpar_raciocinio(texto or "")
    if "</think>" in t:
        t = t[t.rindex("</think>") + len("</think>"):].strip()
    return t


def vram_mb():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return int(out[0]) if out else 0


class Vigia(threading.Thread):
    """Amostra a VRAM a cada 0,25 s enquanto a geracao roda. O modelo e servido por outro processo
    (o do Ollama, ou o servidor hf): torch.cuda.max_memory_allocated nao enxerga nada aqui, e a
    unica medida disponivel e a da placa inteira. Por isso tambem se registra a linha de base
    ANTES de carregar qualquer modelo."""

    def __init__(self):
        super().__init__(daemon=True)
        self.pico = 0
        self.parar = threading.Event()

    def run(self):
        while not self.parar.is_set():
            self.pico = max(self.pico, vram_mb())
            self.parar.wait(0.25)


def processador():
    """Fracao GPU/CPU por modelo residente, lida de `ollama ps`. A coluna PROCESSOR e a unica
    fonte dessa fracao: a resposta da API nao a traz."""
    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout.strip()
    linhas = {}
    for l in ps.splitlines()[1:]:
        m = re.match(r"^(\S+)\s+(\S+)\s+(\S+\s+\S+)\s+(.+?)\s{2,}", l)
        if m:
            linhas[m.group(1)] = {"tamanho": m.group(3), "processador": m.group(4).strip()}
    return ps, linhas


NUM_GPU = None   # None = o Ollama decide; valor inteiro limita as camadas na placa (ver ADENDO 03)


def gerar_ollama(modelo, prompt, max_tokens, ctx, imagem=None):
    j = {"model": modelo, "prompt": prompt, "stream": False, "keep_alive": "30m",
         "options": {"num_ctx": ctx, "num_predict": max_tokens, "temperature": 0}}
    if NUM_GPU is not None:
        j["options"]["num_gpu"] = NUM_GPU
    if imagem:
        j["images"] = [base64.b64encode(imagem).decode()]
    t = time.time()
    r = requests.post(f"{llm.OLLAMA}/api/generate", json={**j, "think": False}, timeout=3600).json()
    if r.get("error") and "think" in str(r.get("error")).lower():
        r = requests.post(f"{llm.OLLAMA}/api/generate", json=j, timeout=3600).json()
    seg = time.time() - t
    if r.get("error"):
        return f"[ERRO API: {r['error'][:160]}]", seg, {"erro": str(r["error"])[:200]}
    m = {"tokens_prefill": r.get("prompt_eval_count"),
         "ns_prefill": r.get("prompt_eval_duration"),
         "tokens_geracao": r.get("eval_count"),
         "ns_geracao": r.get("eval_duration"),
         "ns_carga": r.get("load_duration"),
         # done_reason == "length" e a PROVA de corte por orcamento de saida. Sem isso, resposta
         # truncada entra na planilha como erro do modelo.
         "done_reason": r.get("done_reason"),
         "tem_campo_thinking": bool(r.get("thinking")),
         "ignorou_think_false": "</think>" in (r.get("response") or "")}
    if m["ns_prefill"]:
        m["tps_prefill"] = round(m["tokens_prefill"] / (m["ns_prefill"] / 1e9), 1)
    if m["ns_geracao"]:
        m["tps_geracao"] = round(m["tokens_geracao"] / (m["ns_geracao"] / 1e9), 1)
    return limpar(r.get("response", "")), seg, m


def gerar_hf(modelo, prompt, max_tokens, ctx, imagem=None):
    """Modelo servido por bench/mimo_servidor_20261128.py (transformers), so em 127.0.0.1.
    O servidor devolve os mesmos campos de contagem, medidos por ele."""
    j = {"prompt": prompt, "max_tokens": max_tokens}
    if imagem:
        j["imagem_b64"] = base64.b64encode(imagem).decode()
    t = time.time()
    try:
        r = requests.post(SERVIDOR_HF, json=j, timeout=3600).json()
    except Exception as e:
        return f"[ERRO hf: {type(e).__name__}]", time.time() - t, {"erro": type(e).__name__}
    seg = time.time() - t
    m = {k: r.get(k) for k in ("tokens_prefill", "tokens_geracao", "ns_prefill", "ns_geracao",
                               "tps_prefill", "tps_geracao", "pico_torch_MB") if r.get(k) is not None}
    if r.get("erro"):
        m["erro"] = r["erro"]
    return limpar(r.get("texto", "")), seg, m


def gerar(modelo, *a, **kw):
    return (gerar_hf if modelo.startswith("hf:") else gerar_ollama)(modelo, *a, **kw)


def rodar(modelo, suite, passada, cache_doc, cache_img):
    max_tokens, ctx = PARAM[suite]
    itens = {"codigo": bench.CODIGO, "raciocinio": bench.RAC, "doc": bench.DOC,
             "visao": bench.VIS}[suite]
    linhas = []
    for t in itens:
        imagem = None
        if suite == "codigo":
            prompt = (f"Escreva em Python a seguinte funcao, com os imports necessarios. "
                      f"{t['enunciado']}\nResponda apenas com o codigo em um bloco ```python```, "
                      "sem exemplos de uso.")
        elif suite == "raciocinio":
            prompt = t["enunciado"] + bench.SUFIXO_RAC
        elif suite == "visao":
            # A MESMA imagem serve os dois lados do braco: gerada uma vez e guardada em cache.
            if t["id"] not in cache_img:
                cache_img[t["id"]] = bench._fig_png(t["img"])
            imagem = cache_img[t["id"]]
            prompt = t["pergunta"]
        else:
            if t["id"] not in cache_doc:
                cache_doc[t["id"]] = t["doc"]()      # converte uma vez, serve todos os modelos
            prompt = llm.montar_prompt(t["pergunta"], cache_doc[t["id"]])
        v = Vigia()
        v.start()
        texto, seg, m = gerar(modelo, prompt, max_tokens, ctx, imagem=imagem)
        v.parar.set()
        v.join(timeout=2)
        if suite == "codigo":
            ok, det = bench.rodar_codigo(bench.extrair_codigo(texto), t["testes"])
        elif suite == "raciocinio":
            vs = bench.ler_numeros(texto)
            ok = any(abs(x - t["esperado"]) <= max(t["tol"], 1e-9) for x in vs)
            det = f"resposta={vs} esperado={round(t['esperado'], 4)}"
        else:
            ok = bool(t["checar"](texto))
            det = texto.strip().replace("\n", " ")[:90]
        linhas.append({"suite": suite, "passada": passada, "modelo": modelo,
                       "tarefa": t["id"], "ok": bool(ok), "seg": round(seg, 1),
                       "detalhe": str(det)[:200], "vram_pico_MB": v.pico,
                       "num_ctx": ctx, "num_predict": max_tokens,
                       "num_gpu_pedido": NUM_GPU,
                       "ollama": VERSAO_OLLAMA, **m})
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--braco", required=True, help="A, C ou D: define o arquivo de saida")
    ap.add_argument("--modelos", required=True)
    ap.add_argument("--suites", required=True)
    ap.add_argument("--passadas", type=int, default=2)
    ap.add_argument("--num-gpu", type=int, default=None, dest="num_gpu",
                    help="limita as camadas na placa. Existe por causa do inkling-2-mini, cujo "
                         "ajuste automatico de memoria do Ollama 0.40.19 falha com cudaMalloc "
                         "(ver ADENDO 03 ao pre-registro). Fora desse caso, nao usar.")
    a = ap.parse_args()
    global NUM_GPU
    NUM_GPU = a.num_gpu
    saida = RAIZ / "bench" / "resultados" / f"20261128_locais_{a.braco}.jsonl"
    cache_doc, cache_img = {}, {}
    base = vram_mb()
    print(f"  VRAM de linha de base, sem modelo carregado: {base} MB", flush=True)
    for modelo in a.modelos.split(","):
        digest = (bench.identidade_modelo(modelo) if not modelo.startswith("hf:")
                  else "hf/" + modelo[3:])
        print(f"\n=== braco {a.braco} | {modelo}  pesos={digest} ===", flush=True)
        for suite in a.suites.split(","):
            for passada in range(1, a.passadas + 1):
                linhas = rodar(modelo, suite, passada, cache_doc, cache_img)
                ps_txt, ps = processador()
                proc = next((v for k, v in ps.items() if k.startswith(modelo.split(":")[0])), {})
                for x in linhas:
                    x.update({"braco": a.braco, "pesos": digest, "vram_base_MB": base,
                              "processador_ollama_ps": proc.get("processador"),
                              "tamanho_residente_ollama_ps": proc.get("tamanho")})
                with saida.open("a", encoding="utf-8") as fh:
                    for x in linhas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")
                ac = sum(x["ok"] for x in linhas)
                segs = sorted(x["seg"] for x in linhas)
                tg = [x["tps_geracao"] for x in linhas if x.get("tps_geracao")]
                tp = [x["tps_prefill"] for x in linhas if x.get("tps_prefill")]
                print(f"  {suite:11} p{passada} {ac}/{len(linhas)}  "
                      f"mediana={segs[len(segs) // 2]:.1f}s maxima={segs[-1]:.1f}s  "
                      f"geracao={sum(tg) / len(tg) if tg else 0:.1f} tok/s  "
                      f"prefill={sum(tp) / len(tp) if tp else 0:.1f} tok/s  "
                      f"VRAM pico={max(x['vram_pico_MB'] for x in linhas)} MB  "
                      f"proc={proc.get('processador')}  "
                      f"cortes={sum(x.get('done_reason') == 'length' for x in linhas)}  "
                      f"think_ignorado={sum(bool(x.get('ignorou_think_false')) for x in linhas)}  "
                      + " ".join(("+" if x["ok"] else "-") + x["tarefa"] for x in linhas),
                      flush=True)
        print("  ollama ps:\n    " + ps_txt.replace("\n", "\n    "), flush=True)
        if not modelo.startswith("hf:"):
            requests.post(f"{llm.OLLAMA}/api/generate",
                          json={"model": modelo, "keep_alive": 0}, timeout=120)
        time.sleep(5)
    print(f"\ngravado em {saida}", flush=True)


if __name__ == "__main__":
    main()
