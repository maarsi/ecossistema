"""Item 3 da fila de 21/11/2026: VRAM e latencia dos modelos de extracao baixaveis, UM POR VEZ,
cada um num processo proprio (memoria de um nao contamina a medida do outro).
Mede: pico do torch (alocado e reservado), memoria do PROCESSO pelo NVML (inclui o contexto
CUDA, que o torch nao ve), tempo de carga e latencia por pagina em paginas reais do DER-PR.
Uso: python vram_extracao.py <modelo> <n_paginas>"""
import json, sys, time, glob, os, statistics as st
import numpy as np, torch, pynvml
from PIL import Image
nome, n = sys.argv[1], int(sys.argv[2])
pynvml.nvmlInit(); h = pynvml.nvmlDeviceGetHandleByIndex(0)
def mem_proc():
    for p in pynvml.nvmlDeviceGetComputeRunningProcesses(h):
        if p.pid == os.getpid(): return (p.usedGpuMemory or 0) / 2**20
    return float("nan")
MOD = {"page_elements": ("nemotron_page_elements_v3.model", "page_element_v3"),
       "table_structure": ("nemotron_table_structure_v1", "table_structure_v1"),
       "graphic_elements": ("nemotron_graphic_elements_v1.model", "graphic_element_v1")}
modulo, cfg = MOD[nome]
import importlib; define_model = importlib.import_module(modulo).define_model
pags = sorted(glob.glob("/home/mateus/ecossistema/bench/derpr/paginas/p*.png"))[:n]
torch.cuda.reset_peak_memory_stats(); t0 = time.time()
model = define_model(cfg, verbose=False) if "verbose" in define_model.__code__.co_varnames else define_model(cfg)
torch.cuda.synchronize(); carga = time.time() - t0
disp = str(next(model.parameters()).device)
params = sum(p.numel() for p in model.parameters()) / 1e6
lat = []; ndet = []
for p in pags:
    img = np.array(Image.open(p).convert("RGB"))
    torch.cuda.synchronize(); t = time.time()
    with torch.inference_mode():
        x = model.preprocess(img); pr = model(x, img.shape)[0]
    torch.cuda.synchronize(); lat.append(time.time() - t)
    try: ndet.append(int(len(pr["boxes"])) if isinstance(pr, dict) and "boxes" in pr else -1)
    except Exception: ndet.append(-1)
r = {"modelo": nome, "dispositivo": disp, "parametros_M": round(params, 1), "carga_s": round(carga, 2),
     "paginas": len(pags), "lat_media_s": round(st.mean(lat), 3), "lat_primeira_s": round(lat[0], 3),
     "lat_mediana_regime_s": round(st.median(lat[1:]) if len(lat) > 1 else lat[0], 3),
     "torch_pico_alocado_MB": round(torch.cuda.max_memory_allocated() / 2**20),
     "torch_pico_reservado_MB": round(torch.cuda.max_memory_reserved() / 2**20),
     "nvml_processo_MB": round(mem_proc()), "deteccoes_por_pagina": ndet[:6],
     "imagem_px": list(np.array(Image.open(pags[0])).shape[:2])}
print(json.dumps(r, ensure_ascii=False))
