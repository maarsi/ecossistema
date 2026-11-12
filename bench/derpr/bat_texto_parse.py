"""Fase 2: braco G, Nemotron-3.5-Parse sobre imagem de pagina."""
import sys, json, pathlib, time, torch
from PIL import Image
from transformers import AutoModel, AutoProcessor, GenerationConfig
B = pathlib.Path.home()/"ecossistema/bench"
T = B/"derpr/textos"; P = B/"derpr/paginas"
passada = sys.argv[1]
alvo = T/f"G_p{passada}.json"
if alvo.exists(): print(f"  braco G passada {passada}: ja existe"); raise SystemExit
M = "nvidia/Nemotron-3.5-Parse"
TASK = "</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>"
t0 = time.time()
mod = AutoModel.from_pretrained(M, trust_remote_code=True, dtype=torch.bfloat16).to("cuda").eval()
proc = AutoProcessor.from_pretrained(M, trust_remote_code=True)
gen = GenerationConfig.from_pretrained(M); gen.max_new_tokens = 8744
carga = time.time()-t0
out = {}
for i in range(1, 59):
    img = Image.open(P/f"p{i:02d}.png").convert("RGB")
    inp = proc(images=[img], text=TASK, return_tensors="pt", add_special_tokens=False).to("cuda")
    with torch.inference_mode(): o = mod.generate(**inp, generation_config=gen)
    out[str(i)] = proc.batch_decode(o, skip_special_tokens=False)[0]
alvo.write_text(json.dumps(out, ensure_ascii=False))
print(f"  braco G passada {passada}: carga {carga:.0f}s, extracao {time.time()-t0-carga:.0f}s")
