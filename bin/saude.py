#!/usr/bin/env python3
"""Checagem de saude do ecossistema. Exercita, compara com linha de base, reporta o delta.

POR QUE ESTE PROGRAMA EXISTE. Em 21/11/2026 um dia de trabalho foi gasto em manutencao
reativa, e o levantamento do que havia quebrado mostrou o padrao: NADA VIGIA. Quatro
ferramentas MCP estavam mortas por modelo descontinuado e ninguem sabia, porque ninguem as
chamava. O backup relia 600 GB por tres noites. Uma credencial dormia em texto puro no
.bashrc. Um notebook ficou 20 dias fora do Syncthing. Nenhuma dessas foi achada por
vigilancia; todas por tropeco.

TRES PRINCIPIOS, cada um de uma licao paga:
  1. EXERCITAR, NAO LISTAR. "Connected" nao e prova de credencial, e ferramenta declarada nao
     e ferramenta viva. Toda checagem de capacidade faz uma chamada real.
  2. REPORTAR O DELTA. Relatorio que lista tudo nao e lido. Guarda-se linha de base e mostra-se
     o que MUDOU, o que QUEBROU, e so o resumo do que esta ok.
  3. CLASSIFICAR O RETORNO. 403 e credencial; 410 e modelo descontinuado; 429 com limite zero e
     modelo nao liberado; 503 e sobrecarga; tempo esgotado COM outro provedor respondendo e o
     provedor fora; tempo esgotado com NENHUM respondendo e o enlace. Sao causas diferentes com
     o mesmo sintoma aparente.

NUNCA imprime valor de credencial: so impressao digital sha256 de 12 hex.
NUNCA varre montagem de rede: todo find usa -xdev.
NUNCA altera nada: este programa apenas OBSERVA e sugere o comando. Decisao e de Mateus.
"""
import datetime
import argparse, hashlib, json, os, re, socket, subprocess, sys, time
from pathlib import Path

H = Path.home()
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = H / "base_conhecimento" / "saude"
LINHA_BASE = SAIDA / "linha_base.json"

OK, MUDOU, QUEBRADO, AVISO = "ok", "mudou", "quebrado", "aviso"
ORDEM = {QUEBRADO: 0, MUDOU: 1, AVISO: 2, OK: 3}
REG = []


def anota(area, item, estado, detalhe="", comando="", valor=None):
    """valor: entra na linha de base e e comparado na proxima rodada."""
    REG.append({"area": area, "item": item, "estado": estado, "detalhe": str(detalhe)[:300],
                "comando": comando, "valor": valor})


def sh(cmd, t=25):
    """Executa e devolve (rc, saida). Nunca levanta."""
    try:
        p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=t)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "[tempo esgotado em %ds]" % t
    except Exception as e:
        return 1, "[falha: %s]" % str(e)[:80]


def dig(v):
    return hashlib.sha256(v.encode()).hexdigest()[:12]


def le_env(nome, arq=None):
    arq = arq or (H / "TransportMCP" / ".env")
    try:
        m = re.search(r'^\s*(?:export\s+)?%s\s*=\s*"?([^"\s]+)' % nome,
                      arq.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except Exception:
        return None


# ===========================================================================
# CHECAGENS LEVES: baratas, para rodar todo dia
# ===========================================================================

def c_sistema():
    rc, k = sh("uname -r")
    anota("sistema", "kernel", OK, k, valor=k)
    rc, up = sh("uptime -p")
    anota("sistema", "tempo ligado", OK, up)
    rc, c = sh("cut -d' ' -f1-3 /proc/loadavg")
    n = os.cpu_count() or 1
    try:
        carga = float(c.split()[0])
    except Exception:
        carga = 0.0
    anota("sistema", "carga", AVISO if carga > n * 1.5 else OK,
          "%s (em %d nucleos)" % (c, n),
          "ps -eo pcpu,args --sort=-pcpu | head" if carga > n * 1.5 else "")
    if Path("/var/run/reboot-required").exists():
        anota("sistema", "reinicio pendente", AVISO,
              "o sistema pede reinicio desde a ultima atualizacao", "sudo reboot")
    else:
        anota("sistema", "reinicio pendente", OK, "nao")


def c_disco():
    rc, out = sh("df -P -x tmpfs -x devtmpfs -x squashfs --output=target,pcent,avail 2>/dev/null | tail -n +2")
    for l in out.split("\n"):
        p = l.split()
        if len(p) < 3:
            continue
        alvo, pct, livre = p[0], p[1], p[2]
        if alvo.startswith(("/media", "/run", "/snap", "/boot/efi")):
            continue
        try:
            u = int(pct.rstrip("%"))
        except Exception:
            continue
        gb = int(livre) / 1048576.0
        est = QUEBRADO if u >= 95 else (AVISO if u >= 85 else OK)
        anota("disco", alvo, est, "%s usado, %.1f GB livres" % (pct, gb),
              "saude.py --higiene  (lista candidatos a remocao)" if est != OK else "",
              valor=u)


def c_gpu():
    rc, out = sh("nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total,"
                 "utilization.gpu,temperature.gpu --format=csv,noheader", 20)
    if rc != 0:
        anota("gpu", "nvidia-smi", QUEBRADO, out[:160], "nvidia-smi")
        return
    campos = [x.strip() for x in out.split(",")]
    if len(campos) >= 6:
        anota("gpu", "placa", OK, campos[0], valor=campos[0])
        anota("gpu", "driver", OK, campos[1], valor=campos[1])
        anota("gpu", "memoria", OK, "%s de %s" % (campos[2], campos[3]))
        try:
            t = int(re.sub(r"\D", "", campos[5]))
            anota("gpu", "temperatura", AVISO if t >= 88 else OK, "%d C" % t)
        except Exception:
            pass


def c_ollama():
    rc, a = sh("systemctl is-active ollama")
    if a != "active":
        anota("ollama", "servico", QUEBRADO, a, "sudo systemctl start ollama")
        return
    anota("ollama", "servico", OK, "ativo")
    rc, out = sh("curl -s --max-time 15 http://127.0.0.1:11434/api/tags", 20)
    try:
        mods = {m["name"]: (m.get("digest") or "")[:12] for m in json.loads(out).get("models", [])}
    except Exception:
        anota("ollama", "catalogo local", QUEBRADO, "nao consegui ler /api/tags", "")
        return
    anota("ollama", "modelos instalados", OK, "%d modelos" % len(mods), valor=len(mods))
    # PESO POR DIGEST, nao por data: re-pull troca o modelo e invalida medicao antiga
    for nome, d in sorted(mods.items()):
        anota("ollama", "peso " + nome, OK, "digest " + d, valor=d)
    # os modelos que os papeis pedem existem?
    try:
        cfg = json.loads((RAIZ / "config" / "papeis.json").read_text(encoding="utf-8"))
        papeis = cfg.get("papeis", cfg)
    except Exception:
        anota("ollama", "papeis.json", QUEBRADO, "nao consegui ler", "")
        return
    # CLASSIFICAR PELO CAMPO DECLARADO, nao pelo formato do nome. A primeira versao desta
    # checagem adivinhava "tem barra, logo e nuvem", e marcou gemini-4-argon, kimi-k3 e
    # deepseek-flash como modelos locais ausentes, sugerindo `ollama pull` deles. Sugestao
    # errada e pior que ausencia de sugestao. O papeis.json declara `onde`: local ou nuvem.
    for papel, v in papeis.items():
        if not isinstance(v, dict):
            continue
        m, onde = v.get("modelo"), (v.get("onde") or "").lower()
        if not isinstance(m, str):
            continue
        if onde == "local":
            if m in mods:
                anota("papeis", papel, OK, "local: " + m, valor=mods.get(m))
            else:
                anota("papeis", papel, QUEBRADO, "modelo local '%s' NAO esta instalado" % m,
                      "ollama pull " + m)
        elif onde == "nuvem":
            pass   # conferido em c_papeis_nuvem, contra o catalogo do provedor
        else:
            anota("papeis", papel, AVISO, "campo 'onde' ausente ou desconhecido: %r" % onde,
                  "editar config/papeis.json e declarar onde=local ou onde=nuvem")


def c_montagens():
    rc, out = sh("findmnt -n -o TARGET,FSTYPE,OPTIONS /media/mateus/DADOS_01 2>/dev/null")
    if not out:
        anota("montagens", "D: (CIFS)", AVISO, "nao montado agora (automount sob demanda)",
              "ls /media/mateus/DADOS_01 >/dev/null")
    else:
        fm = "file_mode=0700" in out
        anota("montagens", "D: (CIFS)", OK if fm else AVISO,
              "montado; permissao restrita: %s" % ("sim" if fm else "NAO, ainda 0755"),
              "" if fm else "sudo umount /media/mateus/DADOS_01   # remonta com 0700 do fstab",
              valor=fm)
    rc, out = sh("findmnt -n -o TARGET,FSTYPE %s/GoogleDrive 2>/dev/null" % H)
    anota("montagens", "Google Drive (rclone)", OK if out else AVISO,
          out or "nao montado", "" if out else "systemctl --user status rclone-gdrive")
    rc, m = sh("stat -c '%A %U:%G' /media/mateus")
    fechada = m.startswith("drwxr-x---")
    anota("montagens", "/media/mateus fechada", OK if fechada else QUEBRADO, m,
          "" if fechada else "sudo bash ~/ecossistema/bin/kimi_fecha_disco.sh", valor=m)


def c_credenciais():
    arq = H / "TransportMCP" / ".env"
    if not arq.exists():
        anota("credenciais", "arquivo", QUEBRADO, "%s ausente" % arq, "")
        return
    modo = oct(arq.stat().st_mode)[-3:]
    anota("credenciais", "permissao do .env", OK if modo == "600" else QUEBRADO, modo,
          "" if modo == "600" else "chmod 600 %s" % arq)
    try:
        linhas = [l for l in arq.read_text(encoding="utf-8").split("\n")
                  if re.match(r"^\s*(export\s+)?[A-Z0-9_]+\s*=", l)]
    except Exception:
        linhas = []
    anota("credenciais", "quantidade", OK, "%d credenciais" % len(linhas), valor=len(linhas))
    for l in linhas:
        nome = re.match(r"^\s*(?:export\s+)?([A-Z0-9_]+)", l).group(1)
        v = le_env(nome)
        if v:
            anota("credenciais", nome, OK, "digital %s, %d caracteres" % (dig(v), len(v)),
                  valor=dig(v))
    # credencial em lugar que NAO deve ter
    for suspeito in (H / ".bashrc", H / ".profile"):
        rc, n = sh("grep -cE '^[[:space:]]*export[[:space:]]+[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD)=' %s 2>/dev/null" % suspeito)
        n = int(n) if n.isdigit() else 0
        anota("credenciais", "credencial em %s" % suspeito.name, OK if n == 0 else QUEBRADO,
              "%d encontradas" % n,
              "" if n == 0 else "mover para ~/TransportMCP/.env; o nome .env dispara a guarda dos agentes")


def c_nuvem_leve():
    """Um POST por provedor, COM braco de controle. Sem controle, 'nao responde' nao se
    distingue de problema nosso: licao de 21/11, quando a inferencia da NVIDIA estava fora e
    a listagem dela respondia em 0,4 s."""
    alvos = [
        ("nvidia", "NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1/chat/completions",
         "nvidia/nemotron-3-ultra-550b-a55b"),  # 28/11: gemma-4-31b-it saiu do catalogo (410)
        ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1/chat/completions",
         "deepseek-chat"),
        ("moonshot", "MOONSHOT_API_KEY", "https://api.moonshot.ai/v1/chat/completions",
         "kimi-k3"),
    ]
    import urllib.request, urllib.error
    resultados = {}
    for prov, nome, url, modelo in alvos:
        k = le_env(nome)
        if not k:
            anota("nuvem", prov, AVISO, "chave %s ausente no .env" % nome, "")
            resultados[prov] = None
            continue
        corpo = json.dumps({"model": modelo, "messages": [{"role": "user", "content": "2+2?"}],
                            "max_tokens": 4}).encode()
        req = urllib.request.Request(url, data=corpo,
                                     headers={"Authorization": "Bearer " + k,
                                              "Content-Type": "application/json"})
        t0 = time.time()
        try:
            st = urllib.request.urlopen(req, timeout=30).status
            resultados[prov] = ("http", st, time.time() - t0)
        except urllib.error.HTTPError as e:
            resultados[prov] = ("http", e.code, time.time() - t0)
        except Exception as e:
            resultados[prov] = ("timeout", str(e)[:40], time.time() - t0)
    vivos = [p for p, v in resultados.items() if v and v[0] == "http" and v[1] == 200]
    for prov, v in resultados.items():
        if v is None:
            continue
        tipo, cod, seg = v
        if tipo == "http" and cod == 200:
            anota("nuvem", prov, OK, "inferencia HTTP 200 em %.1fs" % seg)
        elif tipo == "http" and cod == 403:
            anota("nuvem", prov, QUEBRADO, "HTTP 403: credencial, ou chave com organizacao errada",
                  "conferir a chave e a organizacao no portal do provedor")
        elif tipo == "http" and cod in (404, 410):
            anota("nuvem", prov, QUEBRADO, "HTTP %d: modelo '%s' descontinuado" % (cod, dict((x[0], x[3]) for x in alvos)[prov]),
                  "saude.py --completo  (confere o catalogo e sugere substituto)")
        elif tipo == "http" and cod == 429:
            anota("nuvem", prov, AVISO, "HTTP 429: cota ou modelo nao liberado para a chave",
                  "nao repetir: 429 com limite zero so queima cota")
        elif tipo == "http" and cod == 503:
            anota("nuvem", prov, AVISO, "HTTP 503: sobrecarga momentanea", "repetir mais tarde")
        else:
            # BRACO DE CONTROLE: a conclusao depende dos OUTROS provedores
            if vivos:
                anota("nuvem", prov, AVISO,
                      "sem resposta em %.0fs, e %s respondeu: o PROVEDOR esta fora"
                      % (seg, " e ".join(vivos)),
                      "nao mexer em chave nem em codigo; repetir depois")
            else:
                anota("nuvem", prov, QUEBRADO,
                      "sem resposta em %.0fs, e NENHUM provedor respondeu: suspeita de enlace"
                      % seg, "ping -c3 1.1.1.1 ; ip route")


def c_backup():
    log = H / ".local/state/restic/backup.log"
    if not log.exists():
        anota("backup", "log", QUEBRADO, "ausente", "")
        return
    txt = log.read_text(encoding="utf-8", errors="replace")
    ev = re.findall(r"=== (.+?) — (início|SUCESSO \(rc=\d+\)|FALH\w+.*?) ===", txt)
    if ev:
        anota("backup", "ultima execucao", OK if "SUCESSO" in ev[-1][1] else QUEBRADO,
              "%s: %s" % (ev[-1][0].strip(), ev[-1][1]),
              "" if "SUCESSO" in ev[-1][1] else "tail -40 %s" % log)
    # O CONTADOR QUE DECIDE: 'unmodified' baixo significa releitura integral do disco
    res = re.findall(r"Files:\s+(\d+) new,\s+(\d+) changed,\s+(\d+) unmodified", txt)
    dur = re.findall(r"processed ([\d,]+) files?, ([\d.]+ \w+) in ([\d:]+)", txt)
    if res:
        novo, alt, inalt = (int(x) for x in res[-1])
        tot = novo + alt + inalt
        frac = (inalt / tot) if tot else 1.0
        est = OK if frac > 0.5 or tot <= 2 else QUEBRADO
        anota("backup", "reconhecimento incremental", est,
              "%d novos, %d alterados, %d inalterados (%.0f%% reconhecidos)"
              % (novo, alt, inalt, frac * 100),
              "" if est == OK else "conferir se --ignore-inode esta em ~/.local/bin/restic-backup.sh",
              valor=round(frac, 2))
    if dur:
        anota("backup", "duracao", OK, "%s arquivos em %s" % (dur[-1][0], dur[-1][2]),
              valor=dur[-1][2])
    rc, n = sh("grep -c 'ignore-inode' ~/.local/bin/restic-backup.sh 2>/dev/null")
    anota("backup", "--ignore-inode", OK if n.strip() not in ("0", "") else QUEBRADO,
          "presente" if n.strip() not in ("0", "") else "AUSENTE: o backup vai reler o disco todo",
          "" if n.strip() not in ("0", "") else "ver o registro de 21/11 no CLAUDE.md")


def c_syncthing():
    rc, out = sh("curl -s --max-time 10 -H \"X-API-Key: $(grep -oP '(?<=<apikey>)[^<]+' "
                 "~/.local/state/syncthing/config.xml 2>/dev/null | head -1)\" "
                 "http://127.0.0.1:8384/rest/system/connections", 15)
    if not out or out.startswith("[falha") or "error" in out[:40].lower():
        anota("syncthing", "api", AVISO, "nao consegui consultar", "systemctl --user status syncthing")
        return
    try:
        d = json.loads(out).get("connections", {})
        con = sum(1 for v in d.values() if v.get("connected"))
        # ANTES: "OK se >= 1 conectado". Deixou a Duebendorf 9 dias fora (13 a 22/11) com tudo verde, e a
        # copia sincronizada que o argon-auditor do Windows le ficou parada. Agora CADA par conta, pelo nome.
        chave = "$(grep -oP '(?<=<apikey>)[^<]+' ~/.local/state/syncthing/config.xml 2>/dev/null | head -1)"
        _, cfgd = sh('curl -s --max-time 10 -H "X-API-Key: %s" http://127.0.0.1:8384/rest/config/devices' % chave, 15)
        _, std = sh('curl -s --max-time 10 -H "X-API-Key: %s" http://127.0.0.1:8384/rest/stats/device' % chave, 15)
        nomes = {x["deviceID"]: x.get("name", x["deviceID"][:7]) for x in json.loads(cfgd)}
        visto = {k: v.get("lastSeen", "") for k, v in json.loads(std).items()}
        fora = []
        agora = time.time()
        for dev, v in d.items():
            if v.get("connected"):
                continue
            ls = visto.get(dev, "")
            try:
                t = datetime.datetime.fromisoformat(ls.replace("Z", "+00:00")).timestamp()
                dias = (agora - t) / 86400
            except Exception:
                dias = 999
            if dias > 1:
                fora.append("%s (%s)" % (nomes.get(dev, dev[:7]), "nunca" if dias > 900 else "%.0f dias" % dias))
        anota("syncthing", "pares conectados", OK if not fora else AVISO,
              "%d de %d" % (con, len(d)) + ("" if not fora else "; FORA HA MAIS DE 1 DIA: " + ", ".join(fora)),
              "" if not fora else "ligar o Syncthing na(s) maquina(s) listada(s)", valor=len(fora))
    except Exception as e:
        anota("syncthing", "api", AVISO, "resposta inesperada: %s" % type(e).__name__, "")
    rc, n = sh("find %s/ecossistema -xdev -name '*.sync-conflict-*' 2>/dev/null | wc -l" % H)
    n = int(n) if n.strip().isdigit() else 0
    anota("syncthing", "conflitos no ecossistema", OK if n == 0 else AVISO, "%d" % n,
          "" if n == 0 else "find ~/ecossistema -xdev -name '*.sync-conflict-*'", valor=n)


def c_git():
    rc, out = sh("cd %s && git status --porcelain" % (RAIZ,))
    linhas = [l for l in out.splitlines() if l.strip()]
    # split e nao l[3:]: sh() apara a saida e come o espaco inicial da 1a linha (" M .gitignore")
    rastreados = [l.split(None, 1)[1] for l in linhas if not l.startswith("??")]
    novos = [l.split(None, 1)[1] for l in linhas if l.startswith("??")]
    # Codigo rastreado alterado e nao commitado: ou e trabalho em curso desta sessao, ou e edicao de OUTRO
    # agente, o que a regra de 22/11/2026 proibe (propostas vao para /mnt/nvme_lexar/propostas_ecossistema).
    anota("git", "codigo alterado fora de commit", OK if not rastreados else AVISO,
          "nenhum" if not rastreados else ", ".join(rastreados[:6]),
          "" if not rastreados else "conferir AUTORIA antes de commitar; nunca git commit -a")
    anota("git", "arquivos novos nao versionados", OK if len(novos) < 40 else AVISO, "%d" % len(novos),
          "" if len(novos) < 40 else "cd ~/ecossistema && git status --short | grep '^??'")
    rc, out = sh("ls -A /mnt/nvme_lexar/propostas_ecossistema 2>/dev/null | grep -v LEIA_ME | wc -l")
    np_ = int(out) if out.strip().isdigit() else 0
    anota("git", "propostas de outros agentes", OK if np_ == 0 else AVISO, "%d aguardando revisao" % np_,
          "" if np_ == 0 else "ls /mnt/nvme_lexar/propostas_ecossistema")
    rc, out = sh("cd %s && git rev-list --count @{u}..HEAD 2>/dev/null" % (RAIZ,))
    n = int(out) if out.strip().isdigit() else 0
    anota("git", "empurrado", OK if n == 0 else AVISO, "%d commits locais a enviar" % n,
          "" if n == 0 else "cd ~/ecossistema && git push origin master")


def c_contencao_kimi():
    rc, out = sh("id kimi 2>/dev/null")
    if rc != 0:
        anota("contencao", "usuario kimi", AVISO, "nao existe", "")
        return
    anota("contencao", "usuario kimi", OK, out.split()[0] if out else "existe")
    alvos = ["%s/TransportMCP/.env" % H, "%s/.ssh/id_ed25519_lote" % H,
             "%s/auditoria_tpc_rms" % H, "/media/mateus/DADOS_01", "%s/GoogleDrive" % H]
    vazou = []
    for a in alvos:
        rc, _ = sh("sudo -n -u kimi test -r '%s'" % a, 12)
        if rc == 0:
            vazou.append(a)
    anota("contencao", "alvos inalcancaveis", OK if not vazou else QUEBRADO,
          "todos bloqueados" if not vazou else "ALCANCA: " + ", ".join(vazou),
          "" if not vazou else "sudo bash ~/ecossistema/bin/kimi_corrige_escopo.sh",
          valor=len(vazou))


def c_notebooks():
    for nome, host in (("geneve", "geneve"), ("zurich", "fedora")):
        rc, out = sh("timeout 30 tailscale ssh -- mateusaraujoesilva@%s "
                     "'df -P --output=pcent / | tail -1; nproc; "
                     "~/venv_lote/bin/python -c \"import numpy,pandas,geopandas;"
                     "print(numpy.__version__,pandas.__version__,geopandas.__version__)\" 2>&1 | tail -1'"
                     % host, 40)
        if rc != 0 or not out:
            anota("notebooks", nome, QUEBRADO, "inalcancavel: %s" % out[:90],
                  "timeout 25 tailscale ssh -- mateusaraujoesilva@%s 'echo ok'" % host)
            continue
        l = out.split("\n")
        anota("notebooks", nome, OK, "disco %s, %s nucleos, libs %s"
              % (l[0].strip() if l else "?", l[1].strip() if len(l) > 1 else "?",
                 l[2].strip() if len(l) > 2 else "?"),
              valor=l[2].strip() if len(l) > 2 else None)



CATALOGO_PROVEDOR = {
    "nvidia":   "https://integrate.api.nvidia.com/v1/models",
    "deepseek": "https://api.deepseek.com/v1/models",
    "moonshot": "https://api.moonshot.ai/v1/models",
}
CHAVE_PROVEDOR = {"nvidia": "NVIDIA_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
                  "moonshot": "MOONSHOT_API_KEY", "google": "GEMINI_API_KEY"}


def c_papeis_nuvem():
    """O modelo de cada papel de nuvem ainda existe no catalogo do provedor?

    Esta e a checagem que faltava. Em 21/11/2026 QUATRO ferramentas MCP estavam mortas porque
    os modelos `meta/llama-3.3-70b-instruct`, `moonshotai/kimi-k3` e `google/deplot` sairam do
    catalogo, e ninguem soube porque ninguem as chamava. Um GET de listagem por provedor custa
    menos de um segundo e pega isso no dia seguinte."""
    import urllib.request, urllib.error
    try:
        cfg = json.loads((RAIZ / "config" / "papeis.json").read_text(encoding="utf-8"))
        papeis = cfg.get("papeis", cfg)
    except Exception as e:
        anota("papeis-nuvem", "papeis.json", QUEBRADO, str(e)[:90], "")
        return
    alvo = {}
    for papel, v in papeis.items():
        if not isinstance(v, dict) or (v.get("onde") or "").lower() != "nuvem":
            continue
        prov = (v.get("provedor") or "nvidia").lower()
        alvo.setdefault(prov, []).append((papel, v.get("modelo")))
    catalogos = {}
    for prov in alvo:
        if prov not in CATALOGO_PROVEDOR:
            continue
        k = le_env(CHAVE_PROVEDOR.get(prov, ""))
        if not k:
            anota("papeis-nuvem", prov, AVISO, "chave ausente, nao da para conferir catalogo", "")
            continue
        req = urllib.request.Request(CATALOGO_PROVEDOR[prov],
                                     headers={"Authorization": "Bearer " + k})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
            catalogos[prov] = {m.get("id") for m in d.get("data", [])}
            anota("papeis-nuvem", "catalogo " + prov, OK,
                  "%d modelos visiveis" % len(catalogos[prov]), valor=len(catalogos[prov]))
        except urllib.error.HTTPError as e:
            anota("papeis-nuvem", "catalogo " + prov, QUEBRADO, "HTTP %d na listagem" % e.code, "")
        except Exception as e:
            anota("papeis-nuvem", "catalogo " + prov, AVISO,
                  "sem resposta: %s" % str(e)[:50], "ver a area 'nuvem' desta mesma rodada")
    for prov, itens in alvo.items():
        for papel, modelo in itens:
            if prov == "google":
                anota("papeis-nuvem", papel, OK,
                      "%s em %s (catalogo do Google nao e conferido neste modo)" % (modelo, prov))
                continue
            cat = catalogos.get(prov)
            if cat is None:
                continue
            if modelo in cat:
                anota("papeis-nuvem", papel, OK, "%s existe em %s" % (modelo, prov))
            else:
                anota("papeis-nuvem", papel, QUEBRADO,
                      "modelo '%s' NAO esta mais no catalogo de %s: a ferramenta devolve 410"
                      % (modelo, prov),
                      "escolher substituto e MEDIR na bateria antes de adotar: "
                      "bench/bench.py --autoteste && bench/bench.py --suite raciocinio --modelos nuvem:<candidato>")


def c_ferramentas_mcp():
    """Exercita os modelos que as ferramentas MCP pedem, sem passar pelo servidor do Windows.
    Ferramenta que nao e chamada nao avisa que morreu."""
    import urllib.request, urllib.error
    srv = RAIZ / "mcp" / "windows" / "ollama_remote_server.py"
    if not srv.exists():
        anota("ferramentas", "fonte do servidor", AVISO, "nao encontrada", "")
        return
    txt = srv.read_text(encoding="utf-8", errors="replace")
    # 28/11: so conta funcao EXPOSTA (@mcp.tool). Funcao aposentada fica no arquivo como
    # historico e gerava falso QUEBRADO (deplot e llama-3.3-70b).
    import ast
    arv = ast.parse(txt)
    vivos_txt = "\n".join(ast.get_source_segment(txt, f) or "" for f in ast.walk(arv)
                          if isinstance(f, ast.FunctionDef)
                          and any("tool" in ast.unparse(d) for d in f.decorator_list))
    pedidos = sorted(set(re.findall(r'"model"\s*:\s*"([^"]+/[^"]+)"', vivos_txt)))
    if not pedidos:
        anota("ferramentas", "modelos citados", AVISO, "nenhum modelo de nuvem citado", "")
        return
    k = le_env("NVIDIA_API_KEY")
    if not k:
        anota("ferramentas", "chave", AVISO, "NVIDIA_API_KEY ausente", "")
        return
    try:
        req = urllib.request.Request("https://integrate.api.nvidia.com/v1/models",
                                     headers={"Authorization": "Bearer " + k})
        cat = {m.get("id") for m in json.loads(urllib.request.urlopen(req, timeout=25).read()).get("data", [])}
    except Exception as e:
        anota("ferramentas", "catalogo", AVISO, "sem resposta: %s" % str(e)[:50], "")
        return
    for m in pedidos:
        if m in cat:
            anota("ferramentas", m, OK, "no catalogo")
        else:
            anota("ferramentas", m, QUEBRADO,
                  "fora do catalogo: a ferramenta que usa este modelo devolve 410",
                  "trocar o modelo em mcp/windows/ollama_remote_server.py e copiar para "
                  "C:\\TransportMCP e D:\\TransportMCP com o aplicativo FECHADO")


LEVES = [c_sistema, c_disco, c_gpu, c_ollama, c_montagens, c_credenciais,
         c_nuvem_leve, c_backup, c_syncthing, c_git, c_contencao_kimi, c_notebooks,
         c_papeis_nuvem, c_ferramentas_mcp]


# ===========================================================================
# RELATORIO
# ===========================================================================

def comparar(reg, base):
    """Marca MUDOU onde o valor difere da linha de base."""
    mapa = {(x["area"], x["item"]): x.get("valor") for x in base.get("registros", [])}
    for x in reg:
        ch = (x["area"], x["item"])
        if x["estado"] == OK and ch in mapa and x.get("valor") is not None:
            if mapa[ch] != x["valor"]:
                x["estado"] = MUDOU
                x["detalhe"] = "%s   (era: %s)" % (x["detalhe"], mapa[ch])
    novos = [x for x in reg if (x["area"], x["item"]) not in mapa]
    sumidos = [k for k in mapa if k not in {(x["area"], x["item"]) for x in reg}]
    return novos, sumidos


def relatorio(reg, novos, sumidos, modo, segundos):
    por = lambda e: [x for x in reg if x["estado"] == e]
    L = []
    L.append("# Saude do ecossistema, modo %s" % modo)
    L.append("")
    L.append("%s  |  %d checagens em %.0f s  |  maquina %s"
             % (time.strftime("%d/%m/%Y %H:%M"), len(reg), segundos, socket.gethostname()))
    L.append("")
    q, m, a = por(QUEBRADO), por(MUDOU), por(AVISO)
    if not (q or m or a):
        L.append("## Nada a tratar")
        L.append("")
        L.append("As %d checagens passaram e nenhum valor mudou desde a ultima rodada." % len(reg))
    for titulo, grupo in (("QUEBRADO, exige acao", q), ("MUDOU desde a ultima rodada", m),
                          ("AVISO, vale olhar", a)):
        if not grupo:
            continue
        L.append("## %s  (%d)" % (titulo, len(grupo)))
        L.append("")
        for x in grupo:
            L.append("- **%s / %s**: %s" % (x["area"], x["item"], x["detalhe"]))
            if x["comando"]:
                L.append("  ```")
                L.append("  " + x["comando"])
                L.append("  ```")
        L.append("")
    if novos:
        L.append("## Itens novos nesta rodada  (%d)" % len(novos))
        L.append("")
        for x in novos[:20]:
            L.append("- %s / %s: %s" % (x["area"], x["item"], x["detalhe"]))
        L.append("")
    if sumidos:
        L.append("## Itens que existiam e nao apareceram  (%d)" % len(sumidos))
        L.append("")
        for a_, i_ in sumidos[:20]:
            L.append("- %s / %s" % (a_, i_))
        L.append("")
    L.append("## Resumo por area")
    L.append("")
    L.append("| area | ok | mudou | aviso | quebrado |")
    L.append("|---|---|---|---|---|")
    for area in sorted({x["area"] for x in reg}):
        g = [x for x in reg if x["area"] == area]
        L.append("| %s | %d | %d | %d | %d |" % (area,
                 sum(1 for x in g if x["estado"] == OK), sum(1 for x in g if x["estado"] == MUDOU),
                 sum(1 for x in g if x["estado"] == AVISO), sum(1 for x in g if x["estado"] == QUEBRADO)))
    L.append("")
    L.append("Nenhuma alteracao foi feita por este programa: ele apenas observa e sugere o comando.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Checagem de saude do ecossistema")
    ap.add_argument("--modo", choices=["leve", "completo"], default="leve")
    ap.add_argument("--gravar-linha-base", action="store_true",
                    help="adota os valores desta rodada como referencia")
    ap.add_argument("--so", default="", help="roda so as areas listadas, separadas por virgula")
    a = ap.parse_args()

    SAIDA.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    checagens = list(LEVES)
    if a.modo == "completo":
        try:
            import saude_completo
            # ARMADILHA DO PYTHON, fechada aqui: este arquivo roda como "__main__", entao um
            # `import saude` dentro do modulo completo criaria uma SEGUNDA copia dele, com
            # outra lista REG, e tudo que o completo anotasse se perderia em silencio. Injetar
            # o modulo EM EXECUCAO resolve e deixa a dependencia explicita.
            saude_completo.S = sys.modules["__main__"]
            checagens += saude_completo.CHECAGENS
        except Exception as e:
            anota("saude", "modo completo", AVISO,
                  "saude_completo.py nao carregou: %s" % str(e)[:80], "")
    for f in checagens:
        try:
            f()
        except Exception as e:
            anota("saude", f.__name__, QUEBRADO, "a propria checagem falhou: %s" % str(e)[:120], "")
    if a.so:
        areas = {x.strip() for x in a.so.split(",")}
        REG[:] = [x for x in REG if x["area"] in areas]

    base = {}
    if LINHA_BASE.exists():
        try:
            base = json.loads(LINHA_BASE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    novos, sumidos = comparar(REG, base)
    REG.sort(key=lambda x: (ORDEM.get(x["estado"], 9), x["area"], x["item"]))
    seg = time.time() - t0
    txt = relatorio(REG, novos, sumidos, a.modo, seg)

    sel = time.strftime("%Y%m%d_%H%M")
    (SAIDA / ("saude_%s.md" % sel)).write_text(txt, encoding="utf-8")
    (SAIDA / ("saude_%s.json" % sel)).write_text(
        json.dumps({"quando": sel, "modo": a.modo, "segundos": round(seg, 1), "registros": REG},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    ult = SAIDA / "ultimo.md"
    ult.write_text(txt, encoding="utf-8")
    if a.gravar_linha_base or not LINHA_BASE.exists():
        LINHA_BASE.write_text(json.dumps({"quando": sel, "registros": REG},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
        print("[linha de base gravada]")
    print(txt)
    nq = sum(1 for x in REG if x["estado"] == QUEBRADO)
    return 2 if nq else 0


if __name__ == "__main__":
    sys.exit(main())
