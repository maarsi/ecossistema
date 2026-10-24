#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""manus_export.py - exporta conversas e anexos do Manus (API v1) para pastas locais, uma por projeto.

  manus_export.py inventario
  manus_export.py exportar --destino "D:\\92 - MANUS" [--projeto ID] [--sem-projeto] [--sem-anexos] [--limite N] [--forcar]

Por que v1 e nao v2: a v2 ignora o filtro por projeto e nao associa tarefa a projeto; a v1 filtra corretamente
e ja devolve o conteudo das mensagens em 'output'. Chave: MANUS_API_KEY em ~/ecossistema/.env (nunca impressa).
Estrutura: <projeto>/conversas/<data>_<titulo>_<id>.md, <projeto>/anexos/<id>/<arquivo>, INVENTARIO.md e .json.
Incremental: tarefa inalterada (updated_at) e anexo ja baixado nao sao refeitos.
"""
import argparse, json, os, re, sys, time
from pathlib import Path
import requests

BASE = "https://api.manus.ai/v1"
# ~/TransportMCP/.env PRIMEIRO, porque nao e sincronizado. Ate 24/10 esta rotina lia
# SOMENTE ~/ecossistema/.env, que o Syncthing envia para quatro dispositivos, e nao tinha
# queda nenhuma: era o unico consumidor que travava a remocao daquele arquivo.
ENVS = [Path.home() / "TransportMCP" / ".env", Path.home() / "ecossistema" / ".env"]
PAUSA = 0.3


def chave():
    if os.environ.get("MANUS_API_KEY"): return os.environ["MANUS_API_KEY"]
    for ENV in ENVS:
        if ENV.exists():
            for l in ENV.read_text(encoding="utf-8").splitlines():
                if l.startswith("MANUS_API_KEY="):
                    v = l.split("=", 1)[1].strip().strip('"').strip("'")
                    if v: return v
    sys.exit("ERRO: MANUS_API_KEY nao encontrada no ambiente nem em "
             + ", ".join(str(e) for e in ENVS))


CAB = {"x-manus-api-key": chave()}


def pedir(rota, **p):
    for tent in range(4):
        try:
            r = requests.get(f"{BASE}/{rota}", headers=CAB, params=p, timeout=120)
            if r.status_code == 429:
                time.sleep(2 ** tent * 2); continue
            time.sleep(PAUSA)
            if r.status_code != 200:
                return {"_erro": f"HTTP {r.status_code}"}
            return r.json()
        except Exception as e:
            if tent == 3: return {"_erro": type(e).__name__}
            time.sleep(2 ** tent)
    return {"_erro": "falhou"}


def tarefas(project_id=None, limite=None):
    out, cur = [], None
    while True:
        p = {"limit": 20}
        if project_id: p["project_id"] = project_id
        if cur: p["after"] = cur
        d = pedir("tasks", **p)
        if d.get("_erro"):
            print(f"  aviso: {d['_erro']}", file=sys.stderr); break
        itens = d.get("data", [])
        out += itens
        cur = d.get("last_id")
        if len(itens) < 20 or not cur or (limite and len(out) >= limite): break
    return out[:limite] if limite else out


def projetos():
    return pedir("projects").get("data", [])


def slug(t, n=60):
    t = re.sub(r"[^\w\s.\-]", "", str(t), flags=re.U).strip()
    return re.sub(r"\s+", "_", t)[:n] or "sem_titulo"


def local(c):
    c = c.replace("\\", "/")
    return Path("/media/mateus/DADOS_01/" + c[3:]) if c[1:3] == ":/" else Path(c)


def data_de(t):
    v = t.get("created_at") or ""
    try: return time.strftime("%Y-%m-%d", time.localtime(int(v)))
    except Exception: return str(v)[:10] or "sem_data"


def markdown(t, nome_projeto, anexos_salvos):
    md = t.get("metadata") or {}
    cab = [f"# {md.get('task_title') or '(sem titulo)'}", "",
           f"- Projeto: {nome_projeto}", f"- ID: {t.get('id')}", f"- Situacao: {t.get('status')}",
           f"- Modelo: {t.get('model','')}", f"- Criada em: {data_de(t)}",
           f"- URL: {md.get('task_url','')}", f"- Anexos: {len(anexos_salvos)}", "", "---", ""]
    corpo = []
    for o in t.get("output", []):
        rotulo = {"user": "Mateus", "assistant": "Manus"}.get(o.get("role"), o.get("role", "?"))
        partes = []
        for c in (o.get("content") or []):
            if c.get("type") == "output_text" and (c.get("text") or "").strip():
                partes.append(c["text"].strip())
            elif c.get("type") == "output_file":
                nome = c.get("fileName") or "(sem nome)"
                destino = anexos_salvos.get(nome)
                partes.append(f"> anexo: {'`anexos/' + destino + '`' if destino else nome} ({c.get('mimeType','?')})")
        if partes:
            corpo.append(f"### {rotulo}\n\n" + "\n\n".join(partes) + "\n")
    return "\n".join(cab) + "\n".join(corpo)


def motivo_cdn(r):
    """Motivo real da recusa, lido do <Code> que o CloudFront devolve no corpo.

    Nao presumir expiracao: 403 pode ser InvalidKey (Key-Pair-Id fora dos signatarios confiaveis
    da distribuicao, problema do lado do Manus), MissingKey (URL sem parametros de assinatura) ou
    AccessDenied (ai sim, policy vencida). Em 20/10/2026 as 419 falhas eram InvalidKey e estavam
    rotuladas como "link expirado", o que mandou a investigacao para o lado errado.
    """
    cod = re.search(r"<Code>([^<]+)</Code>", r.text or "")
    return f"HTTP {r.status_code} ({cod.group(1) if cod else 'sem codigo no corpo'})"


def baixar(url, destino):
    if destino.exists() and destino.stat().st_size > 0: return "cache"
    for tent in range(3):
        try:
            r = requests.get(url, timeout=300)
            if r.status_code == 200:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(r.content); return None
            if r.status_code in (403, 404): return motivo_cdn(r)
        except Exception as e:
            if tent == 2: return type(e).__name__
            time.sleep(2 ** tent)
    return "falhou"


def sondar_anexos(grupos, limite=None):
    """Baixa UMA url de anexo antes de comecar. Devolve None se o CDN esta servindo, ou a mensagem
    de aborto. Sem isso, uma panne do lado do Manus vira milhares de falhas gravadas no inventario."""
    for nome, pid in grupos:
        for t in tarefas(pid, limite or 1):
            for o in t.get("output", []):
                for c in (o.get("content") or []):
                    if c.get("type") != "output_file" or not c.get("fileUrl"):
                        continue
                    try:
                        # Range limita o corpo a 1 KiB; sem stream para o corpo do erro
                        # continuar legivel (o <Code> do CloudFront vem nele).
                        r = requests.get(c["fileUrl"], timeout=60,
                                         headers={"Range": "bytes=0-1023"})
                    except Exception as e:
                        return f"sonda de anexo falhou ({type(e).__name__}): rede indisponivel"
                    if r.status_code in (200, 206):
                        return None
                    return (f"sonda de anexo recusada: {motivo_cdn(r)}.\n"
                            f"  O CDN do Manus nao esta servindo anexo nenhum agora; seguir marcaria\n"
                            f"  todo o acervo como falha. Repetir quando a sonda voltar 200.\n"
                            f"  Para exportar so as conversas: --sem-anexos")
    return None


def exportar(destino, so_projeto=None, sem_projeto=False, sem_anexos=False, limite=None, forcar=False):
    raiz = local(destino); raiz.mkdir(parents=True, exist_ok=True)
    est_arq = raiz / ".estado_export.json"
    estado = json.loads(est_arq.read_text(encoding="utf-8")) if est_arq.exists() and not forcar else {}
    grupos = []
    if not sem_projeto:
        for p in projetos():
            if so_projeto and p["id"] != so_projeto: continue
            grupos.append((p["name"], p["id"]))
    else:
        grupos.append(("_sem_projeto", None))
    if not sem_anexos:
        aborto = sondar_anexos(grupos, limite)
        if aborto:
            sys.exit(f"ABORTADO: {aborto}")
        print("sonda de anexo: CDN servindo (200), seguindo", flush=True)
    t0, inv_geral = time.time(), []
    for nome, pid in grupos:
        pasta = raiz / slug(nome, 70)
        ts = tarefas(pid, limite)
        if sem_projeto:
            ja = set(estado.get("_ids_em_projetos", []))
            ts = [t for t in ts if t["id"] not in ja]
        print(f"\n### {nome}: {len(ts)} tarefas", flush=True)
        inv, n_anexos, falhas = [], 0, []
        for i, t in enumerate(ts, 1):
            tid = t["id"]; md = t.get("metadata") or {}
            titulo = md.get("task_title") or "(sem titulo)"
            arq = pasta / "conversas" / f"{data_de(t)}_{slug(titulo, 50)}_{tid[:8]}.md"
            marca = str(t.get("updated_at"))
            arquivos = [c for o in t.get("output", []) for c in (o.get("content") or []) if c.get("type") == "output_file"]
            if estado.get(tid) == marca and arq.exists() and sem_anexos:
                inv.append({"id": tid, "titulo": titulo, "data": data_de(t), "status": t.get("status"),
                            "anexos": 0, "arquivo": arq.name, "reaproveitado": True}); continue
            salvos = {}
            if not sem_anexos:
                for c in arquivos:
                    nome_a = c.get("fileName") or f"anexo_{len(salvos)+1}"
                    rel = f"{tid[:8]}/{slug(nome_a, 90)}"
                    erro = baixar(c.get("fileUrl", ""), pasta / "anexos" / rel)
                    if erro and erro != "cache": falhas.append(f"{nome_a}: {erro}")
                    else: salvos[nome_a] = rel; n_anexos += 1
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(markdown(t, nome, salvos), encoding="utf-8")
            estado[tid] = marca
            inv.append({"id": tid, "titulo": titulo, "data": data_de(t), "status": t.get("status"),
                        "mensagens": len(t.get("output", [])), "anexos": len(salvos),
                        "anexos_previstos": len(arquivos), "arquivo": arq.name})
            print(f"  [{i}/{len(ts)}] {titulo[:58]} ({len(t.get('output', []))} msgs, {len(salvos)}/{len(arquivos)} anexos)", flush=True)
        if not inv: continue
        pasta.mkdir(parents=True, exist_ok=True)
        linhas = [f"# Inventario: {nome}", "", f"Exportado em {time.strftime('%d/%m/%Y %H:%M')} de manus.im", "",
                  "| Data | Tarefa | Situacao | Msgs | Anexos | Arquivo |", "|---|---|---|---:|---:|---|"]
        for it in sorted(inv, key=lambda x: x["data"]):
            linhas.append(f"| {it['data']} | {it['titulo'][:70]} | {it.get('status','')} | {it.get('mensagens','-')} "
                          f"| {it.get('anexos','-')}/{it.get('anexos_previstos','-')} | conversas/{it['arquivo']} |")
        if falhas: linhas += ["", "## Anexos nao baixados", ""] + [f"- {f}" for f in falhas[:50]]
        (pasta / "INVENTARIO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        (pasta / "inventario.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
        inv_geral.append((nome, len(inv), sum(i.get("mensagens", 0) or 0 for i in inv), n_anexos, len(falhas)))
        estado.setdefault("_ids_em_projetos", [])
        estado["_ids_em_projetos"] = list(set(estado["_ids_em_projetos"]) | {i["id"] for i in inv})
        est_arq.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    if inv_geral:
        g = ["# Inventario geral do acervo Manus", "", f"Atualizado em {time.strftime('%d/%m/%Y %H:%M')}", "",
             "| Pasta (projeto) | Tarefas | Mensagens | Anexos | Falhas |", "|---|---:|---:|---:|---:|"]
        g += [f"| {n} | {a} | {b} | {c} | {d} |" for n, a, b, c, d in inv_geral]
        p = raiz / "INVENTARIO_GERAL.md"
        antigo = p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text("\n".join(g) + "\n" + ("\n<!-- anterior -->\n" + antigo if antigo else ""), encoding="utf-8")
    print(f"\nCONCLUIDO em {time.time()-t0:.0f}s: {sum(x[1] for x in inv_geral)} tarefas, "
          f"{sum(x[3] for x in inv_geral)} anexos, {sum(x[4] for x in inv_geral)} falhas -> {raiz}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventario")
    e = sub.add_parser("exportar")
    e.add_argument("--destino", required=True); e.add_argument("--projeto")
    e.add_argument("--sem-projeto", action="store_true"); e.add_argument("--sem-anexos", action="store_true")
    e.add_argument("--limite", type=int); e.add_argument("--forcar", action="store_true")
    a = ap.parse_args()
    if a.cmd == "inventario":
        ps = projetos(); print(f"projetos: {len(ps)}")
        tot = 0
        for p in ps:
            ts = tarefas(p["id"]); n = sum(1 for t in ts for o in t.get("output", []) for c in (o.get("content") or []) if c.get("type") == "output_file")
            tot += len(ts); print(f"  {len(ts):5} tarefas {n:6} anexos  {p['name']}")
        print(f"  total em projetos: {tot}")
    else:
        exportar(a.destino, a.projeto, a.sem_projeto, a.sem_anexos, a.limite, a.forcar)
