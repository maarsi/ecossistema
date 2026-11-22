"""Item 3, parte 2: VRAM e latencia dos modelos GRANDES com a GPU livre, um processo por modelo,
carregados com o MESMO codigo da bateria do DER-PR. Uso: python vram_grandes.py <modelo> (no venv certo)."""
import json, os, subprocess, sys, time, statistics as st, torch
from PIL import Image
from pathlib import Path
P = Path("/home/mateus/ecossistema/bench/derpr/paginas"); pags = [P/f"p{i:02d}.png" for i in (10, 13, 21, 30)]
def proc_mb():   # nvidia-smi pelo PID: os ambientes da bateria nao tem pynvml, e neles nao se instala nada
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    for l in out.splitlines():
        pid, mb = [x.strip() for x in l.split(",")]
        if int(pid) == os.getpid(): return int(mb)
nome = sys.argv[1]; t0 = time.time(); lat = []
if nome == "embed-vl":
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("nvidia/llama-nemotron-embed-vl-1b-v2", trust_remote_code=True, model_kwargs={"dtype": torch.bfloat16}, device="cuda")
    carga = time.time()-t0
    for p in pags: t = time.time(); m.encode_document([Image.open(p).convert("RGB")], batch_size=1); torch.cuda.synchronize(); lat.append(time.time()-t)
elif nome == "rerank-vl":
    from sentence_transformers import CrossEncoder
    m = CrossEncoder("nvidia/llama-nemotron-rerank-vl-1b-v2", trust_remote_code=True, model_kwargs={"dtype": torch.bfloat16}, device="cuda")
    carga = time.time()-t0
    for p in pags: t = time.time(); m.predict([("quantos sinistros por rodovia", Image.open(p).convert("RGB"))]); torch.cuda.synchronize(); lat.append(time.time()-t)
elif nome == "parse":
    from transformers import AutoModel, AutoProcessor, GenerationConfig
    M = "nvidia/Nemotron-3.5-Parse"; mod = AutoModel.from_pretrained(M, trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval()
    pr = AutoProcessor.from_pretrained(M, trust_remote_code=True); g = GenerationConfig.from_pretrained(M); g.max_new_tokens = 8744
    carga = time.time()-t0; TASK = "</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>"
    for p in pags:
        inp = pr(images=[Image.open(p).convert("RGB")], text=TASK, return_tensors="pt", add_special_tokens=False).to("cuda")
        t = time.time()
        with torch.inference_mode(): mod.generate(**inp, generation_config=g)
        torch.cuda.synchronize(); lat.append(time.time()-t)
print(json.dumps({"modelo": nome, "carga_s": round(carga, 1), "lat_primeira_s": round(lat[0], 2),
                  "lat_mediana_regime_s": round(st.median(lat[1:]), 2), "torch_pico_alocado_MB": round(torch.cuda.max_memory_allocated()/2**20),
                  "nvml_processo_MB": proc_mb()}, ensure_ascii=False))
