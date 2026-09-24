#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""manus_export.py - exporta conversas e anexos do Manus para pastas locais, uma por projeto.

  manus_export.py inventario
  manus_export.py exportar --destino "D:\\92 - MANUS" [--forcar] [--limite N]

Chave: variavel de ambiente MANUS_API_KEY ou linha MANUS_API_KEY=... em ~/ecossistema/.env.
Nunca imprime a chave. Exportacao incremental: so refaz tarefas alteradas desde a ultima execucao.
Estrutura criada em cada pasta de projeto:
    conversas/<data>_<titulo>_<id>.md     historico completo da tarefa
    anexos/<id>/<arquivo>                 anexos baixados
    INVENTARIO.md / inventario.json       inventario completo da pasta
"""
import argparse, json, os, re, sys, time
from pathlib import Path
import requests

BASE = "https://api.manus.ai/v2"
ENV = Path.home() / "ecossistema" / ".env"
PAUSA = 0.35          # respeita limites de taxa da API
TENTATIVAS = 4


def chave():
    if os.environ.get("MANUS_API_KEY"):
        return os.environ["MANUS_API_KEY"]
    if ENV.exists():
        for l in ENV.read_text(encoding="utf-8").splitlines():
            if l.startswith("MANUS_API_KEY="):
                v = l.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    sys.exit(f"ERRO: MANUS_API_KEY nao encontrada. Gravar a chave em {ENV} na linha MANUS_API_KEY=...")


CAB = {"x-manus-api-key": chave(), "Content-Type": "application/json"}


def chamar(metodo, params=None):
    """GET com parametros; se o endpoint nao aceitar GET, refaz como POST com o mesmo corpo."""
    params = params or {}
    for tent in range(TENTATIVAS):
        try:
            r = requests.get(f"{BASE}/{metodo}", headers=CAB, params=params, timeout=90)
            if r.status_code in (404, 405):
                r = requests.post(f"{BASE}/{metodo}", headers=CAB, json=params, timeout=90)
            if r.status_code == 429:
                time.sleep(2 ** tent * 2); continue
            time.sleep(PAUSA)
            d = r.json()
            if r.status_code != 200 or d.get("ok") is False:
                erro = d.get("error", {})
                return {"_erro": f"HTTP {r.status_code} {erro.get('code', '')} {erro.get('message', '')}".strip()}
            return d
        except Exception as e:
            if tent == TENTATIVAS - 1:
                return {"_erro": f"{type(e).__name__}: {e}"}
            time.sleep(2 ** tent)
    return {"_erro": "falhou apos varias tentativas"}


def lista(d, *nomes):
    """Extrai a lista de itens da resposta, tolerante ao nome do campo."""
    for n in nomes:
        v = d.get(n)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for n2 in ("data", "items", "list"):
                if isinstance(v.get(n2), list):
                    return v[n2]
    for v in d.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


def cursor(d):
    for n in ("next_cursor", "cursor", "next_page_token"):
        if d.get(n):
            return d[n]
    p = d.get("pagination") or d.get("page") or {}
    return p.get("next_cursor") if isinstance(p, dict) else None


def paginar(metodo, params, campo_lista, limite=None):
    itens, c = [], None
    while True:
        p = dict(params)
        if c:
            p["cursor"] = c
        d = chamar(metodo, p)
        if d.get("_erro"):
            print(f"  aviso em {metodo}: {d['_erro']}", file=sys.stderr)
            break
        novos = lista(d, campo_lista)
        itens += novos
        c = cursor(d)
        if not c or not novos or (limite and len(itens) >= limite):
            break
    return itens[:limite] if limite else itens


def campo(o, *nomes, padrao=""):
    for n in nomes:
        if o.get(n) not in (None, ""):
            return o[n]
    return padrao


def slug(t, n=60):
    t = re.sub(r"[^\w\s.-]", "", str(t), flags=re.U).strip()
    t = re.sub(r"\s+", "_", t)
    return (t[:n] or "sem_titulo")


def caminho_local(c):
    c = c.replace("\\", "/")
    return Path("/media/mateus/DADOS_01/" + c[3:]) if c[1:3] == ":/" else Path(c)


def data_de(o):
    v = campo(o, "created_at", "createdAt", "create_time", padrao="")
    if isinstance(v, (int, float)):
        return time.strftime("%Y-%m-%d", time.localtime(v / (1000 if v > 1e11 else 1)))
    return str(v)[:10] or "sem_data"


def texto_mensagem(m):
    """Converte um evento da API em bloco de markdown e devolve a lista de anexos."""
    tipo = campo(m, "type", padrao="evento")
    corpo = m.get(tipo) if isinstance(m.get(tipo), dict) else {}
    conteudo = campo(corpo, "content", "text", padrao="")
    if isinstance(conteudo, list):
        conteudo = "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in conteudo)
    anexos = corpo.get("attachments") or []
    quando = campo(m, "timestamp", "created_at", padrao="")
    if isinstance(quando, (int, float)):
        quando = time.strftime("%d/%m/%Y %H:%M", time.localtime(quando / (1000 if quando > 1e11 else 1)))
    rotulo = {"user_message": "Mateus", "assistant_message": "Manus"}.get(tipo, tipo)
    if not conteudo and not anexos:
        return "", []
    bloco = [f"### {rotulo} ({quando})" if quando else f"### {rotulo}", "", str(conteudo).strip()]
    for a in anexos:
        bloco.append(f"\n> anexo: {campo(a, 'filename', padrao='(sem nome)')} ({campo(a, 'content_type', padrao='?')})")
    return "\n".join(bloco) + "\n", anexos


def baixar(url, destino):
    try:
        r = requests.get(url, headers={"x-manus-api-key": CAB["x-manus-api-key"]}, timeout=180)
        if r.status_code in (401, 403):
            r = requests.get(url, timeout=180)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return None
    except Exception as e:
        return f"{type(e).__name__}"


def coletar_tarefas(limite=None):
    ts = paginar("task.list", {"page_size": 50, "limit": 50}, "tasks", limite)
    for t in ts:
        t["_id"] = campo(t, "task_id", "id")
        t["_titulo"] = campo(t, "task_title", "title", padrao="sem titulo")
        t["_projeto"] = campo(t, "project_id", "projectId", padrao="")
    return ts


def inventario():
    u = chamar("user.me")
    print("conta:", json.dumps({k: v for k, v in u.items() if k != "request_id"}, ensure_ascii=False)[:200])
    projs = paginar("project.list", {"page_size": 50}, "projects")
    print(f"projetos: {len(projs)}")
    for p in projs:
        print(f"  {campo(p, 'project_id', 'id'):>28}  {campo(p, 'name', 'title', padrao='(sem nome)')}")
    ts = coletar_tarefas()
    print(f"tarefas: {len(ts)}")
    nomes = {campo(p, "project_id", "id"): campo(p, "name", "title", padrao="(sem nome)") for p in projs}
    por = {}
    for t in ts:
        k = t["_projeto"] or "(sem projeto)"
        por[k] = por.get(k, 0) + 1
    for pid, n in sorted(por.items(), key=lambda x: -x[1]):
        print(f"  {n:4} tarefas  {nomes.get(pid, pid)}")


def exportar(destino, forcar=False, limite=None):
    raiz = caminho_local(destino)
    raiz.mkdir(parents=True, exist_ok=True)
    estado_arq = raiz / ".estado_export.json"
    estado = json.loads(estado_arq.read_text(encoding="utf-8")) if estado_arq.exists() and not forcar else {}
    projs = paginar("project.list", {"page_size": 50}, "projects")
    nomes = {campo(p, "project_id", "id"): campo(p, "name", "title", padrao="sem_nome") for p in projs}
    tarefas = coletar_tarefas(limite)
    print(f"{len(projs)} projetos, {len(tarefas)} tarefas")
    inv = {}
    for i, t in enumerate(tarefas, 1):
        tid, titulo = t["_id"], t["_titulo"]
        pasta = raiz / slug(nomes.get(t["_projeto"], "_sem_projeto"), 70)
        marca = str(campo(t, "updated_at", "updatedAt", "created_at", padrao=""))
        arquivo = pasta / "conversas" / f"{data_de(t)}_{slug(titulo, 50)}_{str(tid)[-8:]}.md"
        if estado.get(tid) == marca and arquivo.exists():
            inv.setdefault(pasta, []).append({**{k: v for k, v in t.items() if not k.startswith("_")},
                                              "titulo": titulo, "arquivo": arquivo.name, "reaproveitado": True})
            continue
        msgs = paginar("task.listMessages", {"task_id": tid, "order": "asc", "limit": 50}, "messages")
        blocos, n_anexos, falhas = [], 0, []
        for m in msgs:
            bloco, anexos = texto_mensagem(m)
            if bloco:
                blocos.append(bloco)
            for a in anexos:
                url, nome = campo(a, "url"), campo(a, "filename", padrao=f"anexo_{n_anexos + 1}")
                if url:
                    erro = baixar(url, pasta / "anexos" / str(tid)[-8:] / slug(nome, 80))
                    n_anexos += not erro
                    if erro:
                        falhas.append(f"{nome}: {erro}")
        cab = [f"# {titulo}", "",
               f"- Projeto: {nomes.get(t['_projeto'], '(sem projeto)')}",
               f"- ID da tarefa: {tid}",
               f"- Situacao: {campo(t, 'status', padrao='?')}",
               f"- Criada em: {data_de(t)}",
               f"- URL: {campo(t, 'task_url', 'url', padrao='')}",
               f"- Mensagens: {len(msgs)} | anexos baixados: {n_anexos}", ""]
        if falhas:
            cab += ["- Anexos NAO baixados: " + "; ".join(falhas[:5]), ""]
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("\n".join(cab) + "\n".join(blocos), encoding="utf-8")
        estado[tid] = marca
        inv.setdefault(pasta, []).append({**{k: v for k, v in t.items() if not k.startswith("_")},
                                          "titulo": titulo, "arquivo": arquivo.name,
                                          "mensagens": len(msgs), "anexos": n_anexos, "falhas_anexo": falhas})
        print(f"  [{i}/{len(tarefas)}] {str(titulo)[:60]} ({len(msgs)} msgs, {n_anexos} anexos)", flush=True)
    geral = ["# Inventario geral do acervo Manus", "",
             f"Exportado em {time.strftime('%d/%m/%Y %H:%M')} de https://manus.im", "",
             "| Pasta (projeto) | Tarefas | Mensagens | Anexos |", "|---|---:|---:|---:|"]
    for pasta, itens in sorted(inv.items()):
        pasta.mkdir(parents=True, exist_ok=True)
        linhas = ["# Inventario: " + pasta.name, "",
                  "| Data | Tarefa | Situacao | Msgs | Anexos | Arquivo |", "|---|---|---|---:|---:|---|"]
        for it in sorted(itens, key=lambda x: str(x.get("created_at", ""))):
            linhas.append(f"| {str(it.get('created_at', ''))[:10]} | {str(it['titulo'])[:70]} | {it.get('status', '')} | "
                          f"{it.get('mensagens', '-')} | {it.get('anexos', '-')} | conversas/{it['arquivo']} |")
        (pasta / "INVENTARIO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        (pasta / "inventario.json").write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
        geral.append(f"| {pasta.name} | {len(itens)} | {sum(i.get('mensagens', 0) or 0 for i in itens)} | "
                     f"{sum(i.get('anexos', 0) or 0 for i in itens)} |")
    (raiz / "INVENTARIO_GERAL.md").write_text("\n".join(geral) + "\n", encoding="utf-8")
    estado_arq.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    print(f"EXPORTACAO CONCLUIDA em {raiz}: {len(inv)} pastas, {sum(len(v) for v in inv.values())} tarefas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Exportador do acervo Manus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventario")
    e = sub.add_parser("exportar")
    e.add_argument("--destino", required=True)
    e.add_argument("--forcar", action="store_true")
    e.add_argument("--limite", type=int)
    a = ap.parse_args()
    if a.cmd == "inventario":
        inventario()
    else:
        exportar(a.destino, a.forcar, a.limite)
