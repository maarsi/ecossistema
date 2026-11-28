#!/home/mateus/env_nemotron_vl/bin/python
# -*- coding: utf-8 -*-
"""Servidor local do MiMo-V2.6-Distill-Qwen-9B para o braco C da rodada local de 28/11/2026.

Por que fora do Ollama: a tag oficial `mimo-v2.6:9b` declara, no blob de config do registro,
`requires: 0.40.15` mais renderer `mimo-v2.6` e parser `qwen3.5`. O Ollama instalado e o 0.34.0 e
a especificacao desta tarefa proibe atualiza-lo (trocar de versao invalidaria as medicoes dos
titulares). Entao o candidato e medido pelos PESOS DO FABRICANTE:
XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B, MIT, repositorio nao restrito, arquitetura
Qwen3_5ForConditionalGeneration, suportada pelo transformers 5.22.2 deste ambiente.

Este ambiente (~/env_nemotron_vl) e USADO, nao alterado: nenhuma instalacao e feita aqui, o que a
proibicao da pagina de frente do CLAUDE.md exige.

9B em bf16 sao cerca de 19 GB e NAO cabem nos 16 GB da RTX 5060 Ti: carrega com device_map="auto"
e teto de VRAM, deixando o resto na RAM. A fracao em CPU e devolvida em cada resposta, porque sem
ela a latencia medida nao se interpreta. Ressalva ja registrada no pre-registro: contra o titular
`qwen2.5vl:7b` (Q4_K_M, inteiro na GPU) a comparacao de ACERTO vale e a de VELOCIDADE nao vale.

Escuta so em 127.0.0.1:8765, o endereco que o bench espera no prefixo hf:.
POST /gerar {"prompt", "max_tokens", "imagem_b64"?} -> {"texto", contagens, fracao de camadas}
"""
import base64
import io
import json
import os
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("HF_HOME", "/mnt/nvme_lexar/hf_cache_20261128")

import torch                                           # noqa: E402
from PIL import Image                                  # noqa: E402
from transformers import AutoModelForImageTextToText, AutoProcessor   # noqa: E402

M = "XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B"
REVISAO = "4ebd5043501b335f24e4968767f3995ab43e60a4"   # commit fixo: peso identificado, nao "o mais novo"

t0 = time.time()
proc = AutoProcessor.from_pretrained(M, revision=REVISAO)
mod = AutoModelForImageTextToText.from_pretrained(
    M, revision=REVISAO, dtype=torch.bfloat16, device_map="auto",
    max_memory={0: "13GiB", "cpu": "40GiB"}).eval()
carga_s = time.time() - t0

# Fracao de camadas em CPU: o equivalente, nesta via, da coluna PROCESSOR do `ollama ps`.
destinos = Counter(str(v) for v in (mod.hf_device_map or {}).values())
total = sum(destinos.values()) or 1
em_cpu = sum(n for d, n in destinos.items() if d in ("cpu", "disk"))
FRACAO_CPU = round(100 * em_cpu / total, 1)
print(f"carregado em {carga_s:.0f} s | mapa de dispositivos: {dict(destinos)} | "
      f"{FRACAO_CPU}% dos modulos fora da GPU | pico torch "
      f"{torch.cuda.max_memory_allocated() / 2**20:.0f} MB", flush=True)


def gerar(d):
    conteudo = []
    if d.get("imagem_b64"):
        conteudo.append({"type": "image",
                         "image": Image.open(io.BytesIO(base64.b64decode(d["imagem_b64"])))
                         .convert("RGB")})
    conteudo.append({"type": "text", "text": d["prompt"]})
    msgs = [{"role": "user", "content": conteudo}]
    try:
        x = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                     return_dict=True, return_tensors="pt",
                                     enable_thinking=False)
    except TypeError:
        x = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                     return_dict=True, return_tensors="pt")
    x = {k: (v.to(mod.device) if hasattr(v, "to") else v) for k, v in x.items()}
    n_entrada = x["input_ids"].shape[1]
    # Prefill e geracao medidos em separado: sem isso nao ha tokens/s de prefill nesta via.
    t1 = time.time()
    with torch.inference_mode():
        pre = mod(**x, use_cache=True)
    torch.cuda.synchronize()
    ns_prefill = int((time.time() - t1) * 1e9)
    del pre
    t2 = time.time()
    with torch.inference_mode():
        o = mod.generate(**x, max_new_tokens=int(d.get("max_tokens", 200)), do_sample=False)
    torch.cuda.synchronize()
    ns_geracao = int((time.time() - t2) * 1e9)
    n_saida = o.shape[1] - n_entrada
    texto = proc.decode(o[0][n_entrada:], skip_special_tokens=True)
    return {"texto": texto,
            "tokens_prefill": n_entrada, "ns_prefill": ns_prefill,
            "tps_prefill": round(n_entrada / (ns_prefill / 1e9), 1),
            "tokens_geracao": int(n_saida), "ns_geracao": ns_geracao,
            "tps_geracao": round(n_saida / (ns_geracao / 1e9), 1) if n_saida else 0.0,
            "pico_torch_MB": round(torch.cuda.max_memory_allocated() / 2**20),
            "fracao_modulos_fora_da_gpu_pct": FRACAO_CPU,
            "carga_s": round(carga_s, 1)}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            r = gerar(d)
        except Exception as e:
            r = {"texto": "", "erro": f"{type(e).__name__}: {str(e)[:300]}"}
        b = json.dumps(r, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


print("servidor em 127.0.0.1:8765", flush=True)
HTTPServer(("127.0.0.1", 8765), H).serve_forever()
