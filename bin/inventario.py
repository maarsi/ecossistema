#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""inventario.py - levanta o estado real da workstation e grava config/registro.json.
  inventario.py            atualiza o registro e imprime o resumo
  inventario.py --resumo   so imprime o resumo do ultimo registro (rapido, para inicio de tarefa)
Rodar sempre depois de instalar ou remover modelo, pacote ou servico, e fazer commit.
"""
import json, shlex, shutil, subprocess, sys, time
from pathlib import Path
import requests

RAIZ = Path(__file__).resolve().parent.parent
REG = RAIZ / "config" / "registro.json"
HOME = Path.home()
PACOTES = ["duckdb", "geopandas", "pyogrio", "shapely", "pyproj", "osmnx", "networkx", "biogeme", "ortools",
           "scipy", "statsmodels", "pymc", "docling", "torch", "openai", "pandas", "polars", "r5py", "gtfs-kit",
           "partridge", "aequilibrae", "xlogit", "fastmcp", "cudf", "cuml", "cuopt",
           "cudf-cu12", "cudf-cu13", "cuml-cu12", "cuml-cu13", "cugraph-cu12", "cugraph-cu13",
           "cuopt-cu12", "cuopt-cu13", "cuopt-server-cu12", "cuopt-server-cu13"]
SERVICOS = ["ollama", "docker", "postgresql@18-main", "tailscaled"]


def sh(c, t=30):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=t).stdout.strip()
    except Exception:
        return ""


def pacotes(py):
    code = ("import importlib.metadata as m,json,sys\no={}\nfor p in sys.argv[1:]:\n"
            "    try: o[p]=m.version(p)\n    except Exception: pass\nprint(json.dumps(o))")
    try:
        return json.loads(sh(f"{py} -c {shlex.quote(code)} {' '.join(PACOTES)}", 90) or "{}")
    except Exception:
        return {}


def coletar():
    reg = {"gerado_em": time.strftime("%Y-%m-%d %H:%M")}
    g = sh("nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits").split(", ")
    reg["gpu"] = {"nome": g[0], "vram_mib": int(g[1]), "usada_mib": int(g[2])} if len(g) == 3 else {}
    vram_gb = reg["gpu"].get("vram_mib", 16000) / 1024
    modelos = []
    try:
        for m in requests.get("http://localhost:11434/api/tags", timeout=10).json().get("models", []):
            gb = m["size"] / 1024**3
            params = requests.post("http://localhost:11434/api/show", json={"model": m["name"]}, timeout=10).json().get("parameters", "")
            ctx = next((l.split()[-1] for l in params.splitlines() if l.startswith("num_ctx")), None)
            modelos.append({"nome": m["name"], "gb": round(gb, 1), "cabe_vram": gb < vram_gb * 0.92, "num_ctx": ctx})
    except Exception as e:
        modelos = [{"erro": f"Ollama inacessivel: {type(e).__name__}"}]
    reg["ollama"] = modelos
    amb = {}
    # /mnt/nvme_lexar/envs guarda o ambiente do cuOpt 26.10, que nao cabia com
    # folga na particao do /home. Sem esta linha o inventario nao enxergava o
    # ambiente usado pela bateria CVRP nem o servidor MCP que o chama
    # (pendencia registrada em 20/10/2026, fechada em 21/10/2026).
    _ambientes = (list(HOME.glob("env_*")) + [HOME / "venv", HOME / "TransportMCP" / ".venv"]
                  + list(Path("/mnt/nvme_lexar/envs").glob("*")))
    for d in sorted(_ambientes):
        py = d / "bin" / "python"
        if py.exists():
            amb[str(d).replace(str(HOME), "~")] = {"python": sh(f"{py} -V").replace("Python ", ""), "pacotes": pacotes(py)}
    reg["ambientes"] = amb
    reg["servicos"] = {s: sh(f"systemctl is-active {s}") for s in SERVICOS}
    reg["docker"] = [l for l in sh("docker ps --format '{{.Names}}'").splitlines() if l]
    reg["discos_livres_gb"] = {p: round(shutil.disk_usage(p).free / 1024**3) for p in
                               ["/mnt/nvme_lexar", "/media/mateus/DADOS_01", "/"] if Path(p).exists()}
    reg["papeis"] = json.loads((RAIZ / "config" / "papeis.json").read_text(encoding="utf-8"))
    return reg


def resumo(reg):
    L = [f"=== REGISTRO DO ECOSSISTEMA ({reg['gerado_em']}) ==="]
    g = reg.get("gpu", {})
    L.append(f"GPU: {g.get('nome')} | VRAM {g.get('vram_mib')} MiB, em uso {g.get('usada_mib')} MiB")
    L.append("PAPEIS (usar via bin/llm.py --papel <nome>):")
    for n, c in reg["papeis"].items():
        L.append(f"  {n:20} {c['onde']:6} {c['modelo']}")
    ms = reg["ollama"]
    L.append(f"OLLAMA ({len(ms)} modelos): " + ", ".join(
        m.get("nome", "?") + ("" if m.get("cabe_vram", True) else " [NAO CABE NA VRAM]") for m in ms))
    for a, v in reg["ambientes"].items():
        p = v["pacotes"]
        L.append(f"AMBIENTE {a} (py {v['python']}): " + (", ".join(f"{k} {x}" for k, x in p.items()) or "nenhum pacote-chave"))
    L.append("SERVICOS: " + " | ".join(f"{k} {v}" for k, v in reg["servicos"].items()))
    L.append("DOCKER: " + (", ".join(reg["docker"]) or "nenhum"))
    L.append("DISCO LIVRE (GB): " + " | ".join(f"{k} {v}" for k, v in reg["discos_livres_gb"].items()))
    return "\n".join(L)


if __name__ == "__main__":
    if "--resumo" in sys.argv and REG.exists():
        print(resumo(json.loads(REG.read_text(encoding="utf-8"))))
    else:
        reg = coletar()
        REG.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(resumo(reg))
