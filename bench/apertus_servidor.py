#!/mnt/nvme_lexar/envs/apertus/bin/python
"""Servidor local minimo para o Apertus 1.5 8B (teste de 26/11/2026), para o bench.py chamar como "hf:apertus".
O modelo NAO cabe em bf16 nos 16 GB da RTX 5060 Ti (cerca de 8,9 bilhoes de parametros = cerca de 18 GB); carrega
em 8 bits (bitsandbytes). Os tokenizadores de imagem e audio ficam em float32, como pede o cartao do modelo.
Escuta so em 127.0.0.1. POST /gerar {"prompt", "max_tokens", "imagem_b64"?, "audio_path"?, "pensar"?} -> {"texto"}"""
import base64, io, json, os, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
import torch
from PIL import Image
from transformers import AutoModelForMultimodalLM, AutoProcessor, BitsAndBytesConfig
M = "swiss-ai/Apertus-v1.5-8B"
t0 = time.time()
proc = AutoProcessor.from_pretrained(M)
mod = AutoModelForMultimodalLM.from_pretrained(
    M, quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map="cuda:0", torch_dtype=torch.bfloat16).eval()
print(f"carregado em {time.time()-t0:.0f} s; pico torch {torch.cuda.max_memory_allocated()/2**20:.0f} MB", flush=True)

def gerar(d):
    conteudo = []
    if d.get("imagem_b64"):
        conteudo.append({"type": "image", "image": Image.open(io.BytesIO(base64.b64decode(d["imagem_b64"]))).convert("RGB")})
    if d.get("audio_path"):
        conteudo.append({"type": "audio", "path": d["audio_path"]})
    conteudo.append({"type": "text", "text": d["prompt"]})
    msgs = [{"role": "user", "content": conteudo}]
    kw = {} if d.get("pensar") else {"enable_thinking": False}
    try:
        x = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt", **kw)
    except TypeError:
        x = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt")
    x = x.to(mod.device)
    with torch.inference_mode():
        o = mod.generate(**x, max_new_tokens=int(d.get("max_tokens", 300)), do_sample=False)
    return proc.decode(o[0][x["input_ids"].shape[1]:], skip_special_tokens=True)

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            r = {"texto": gerar(d), "pico_MB": round(torch.cuda.max_memory_allocated() / 2**20)}
        except Exception as e:
            r = {"texto": f"[erro apertus: {type(e).__name__}: {str(e)[:200]}]"}
        b = json.dumps(r).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 8765), H).serve_forever()
