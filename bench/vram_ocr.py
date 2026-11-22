"""Pendencia 5 de 22/11/2026: memoria de video de nemotron-ocr-v1 e PaddleOCR-VL, um processo por modelo.
Medida feita COM A GPU DISPUTADA pela indexacao do acervo: memoria do processo (NVML) e pico do torch valem;
latencia e TETO, nao numero de regime. Uso: python vram_ocr.py nemotron-ocr|paddleocr-vl <n_paginas>"""
import json, sys, time, glob, os, statistics as st
import torch, subprocess
from PIL import Image
nome, n = sys.argv[1], int(sys.argv[2])
def mem_proc():
    # nvidia-smi pelo PID, e nao pynvml: os ambientes de bateria (env_nemotron_*) nao recebem pacote novo.
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    for l in out.splitlines():
        pid, mb = [x.strip() for x in l.split(",")]
        if int(pid) == os.getpid(): return float(mb)
    return float("nan")
pags = sorted(glob.glob("/home/mateus/ecossistema/bench/derpr/paginas/p*.png"))[:n]
torch.cuda.reset_peak_memory_stats(); t0 = time.time()
if nome == "nemotron-ocr":
    from nemotron_ocr.inference.pipeline import NemotronOCR
    R = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--nvidia--nemotron-ocr-v1/snapshots/*/checkpoints"))[0]
    m = NemotronOCR(model_dir=R)
    rodar = lambda p: len(m(p, merge_level="paragraph", visualize=False))
else:
    from transformers import AutoModelForCausalLM, AutoProcessor
    M = "PaddlePaddle/PaddleOCR-VL"
    mod = AutoModelForCausalLM.from_pretrained(M, trust_remote_code=True, torch_dtype=torch.bfloat16).to("cuda").eval()
    pr = AutoProcessor.from_pretrained(M, trust_remote_code=True)
    def rodar(p):
        msg = [{"role": "user", "content": [{"type": "image", "image": Image.open(p).convert("RGB")}, {"type": "text", "text": "OCR:"}]}]
        x = pr.apply_chat_template(msg, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to("cuda")
        with torch.inference_mode(): o = mod.generate(**x, max_new_tokens=1024)
        return len(pr.batch_decode(o, skip_special_tokens=True)[0])
torch.cuda.synchronize(); carga = time.time() - t0
lat, saida = [], []
for p in pags:
    torch.cuda.synchronize(); t = time.time(); saida.append(rodar(p)); torch.cuda.synchronize(); lat.append(time.time() - t)
print(json.dumps({"modelo": nome, "paginas": len(pags), "carga_s": round(carga, 1), "lat_primeira_s": round(lat[0], 2),
      "lat_mediana_s_TETO": round(st.median(lat[1:] or lat), 2), "torch_pico_alocado_MB": round(torch.cuda.max_memory_allocated() / 2**20),
      "nvml_processo_MB": round(mem_proc()), "saida_por_pagina": saida, "gpu_disputada": True}, ensure_ascii=False))
