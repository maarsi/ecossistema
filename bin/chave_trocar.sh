#!/bin/bash
# ===========================================================================
# Troca UMA credencial em ~/TransportMCP/.env, sem que ela apareça em lugar
# nenhum: nem na tela, nem no histórico do terminal, nem nesta conversa.
#
# USO:   bash ~/ecossistema/bin/chave_trocar.sh NVIDIA_API_KEY
#        bash ~/ecossistema/bin/chave_trocar.sh NGC_API_KEY
#
# COMO FUNCIONA: você cola o valor quando ele pedir. O terminal NÃO mostra o
# que você colou (eco desligado), e por ser entrada e não comando, nada vai
# para o histórico. A saída mostra apenas a IMPRESSÃO DIGITAL, que são 12
# caracteres derivados da chave e dos quais não se volta ao valor. Pode mandar
# a saída pelo chat sem risco.
# ===========================================================================
set -u
ENV_ARQ="$HOME/TransportMCP/.env"
NOME="${1:-}"
ok(){ echo "  [ok]   $*"; }; erro(){ echo "  [ERRO] $*"; }

[ -n "$NOME" ] || { erro "informe o nome da variavel. Ex.: $0 NVIDIA_API_KEY"; exit 1; }
[ -f "$ENV_ARQ" ] || { erro "nao achei $ENV_ARQ"; exit 1; }

digital(){ printf '%s' "$1" | sha256sum | cut -c1-12; }

ANTIGA=$(grep -E "^[[:space:]]*(export[[:space:]]+)?$NOME[[:space:]]*=" "$ENV_ARQ" 2>/dev/null \
         | head -1 | sed -E 's/^[^=]*=[[:space:]]*"?//; s/"?[[:space:]]*$//')
echo
if [ -n "$ANTIGA" ]; then ok "valor atual de $NOME: digital $(digital "$ANTIGA"), $(printf '%s' "$ANTIGA" | wc -c) caracteres"
else ok "$NOME ainda nao existe no arquivo; vai ser acrescentada"; fi

echo
echo "  Cole o NOVO valor e aperte Enter. Nada vai aparecer na tela."
printf "  %s: " "$NOME"
read -rs NOVA
echo
[ -n "$NOVA" ] || { erro "vazio, nada foi alterado"; exit 1; }
case "$NOVA" in *[[:space:]]*) erro "tem espaco, parece colagem errada; nada alterado"; exit 1;; esac
[ "${#NOVA}" -ge 20 ] || { erro "curto demais (${#NOVA} caracteres); nada alterado"; exit 1; }
if [ -n "$ANTIGA" ] && [ "$NOVA" = "$ANTIGA" ]; then erro "igual a atual; nada alterado"; exit 1; fi
ok "recebida: digital $(digital "$NOVA"), ${#NOVA} caracteres"

BKP="$ENV_ARQ.antes_$(date +%Y%m%d_%H%M%S)"
cp -a "$ENV_ARQ" "$BKP" && chmod 600 "$BKP" && ok "copia de seguranca temporaria feita"

T=$(mktemp); chmod 600 "$T"
if [ -n "$ANTIGA" ]; then
    NOVA_ESC=$(printf '%s' "$NOVA" | sed -e 's/[\/&|]/\\&/g')
    sed -E "s|^([[:space:]]*(export[[:space:]]+)?$NOME[[:space:]]*=).*|\1$NOVA_ESC|" "$ENV_ARQ" > "$T"
else
    cat "$ENV_ARQ" > "$T"; printf '%s=%s\n' "$NOME" "$NOVA" >> "$T"
fi
cat "$T" > "$ENV_ARQ"; rm -f "$T"; chmod 600 "$ENV_ARQ"

CONF=$(grep -E "^[[:space:]]*(export[[:space:]]+)?$NOME[[:space:]]*=" "$ENV_ARQ" | head -1 \
       | sed -E 's/^[^=]*=[[:space:]]*"?//; s/"?[[:space:]]*$//')
if [ "$(digital "$CONF")" = "$(digital "$NOVA")" ]; then ok "gravada e conferida no arquivo, permissao 600"
else erro "gravacao NAO conferiu; restaurando"; cp -a "$BKP" "$ENV_ARQ"; exit 1; fi

echo
echo "=== teste por INFERENCIA (listagem responder nao prova que a chave serve)"
case "$NOME" in
  NVIDIA_API_KEY|NGC_API_KEY)
    NOME_VAR="$NOME" "$HOME/env_transporte/bin/python" - <<'PY'
import json, os, re, hashlib, urllib.request, urllib.error, pathlib
nome = os.environ["NOME_VAR"]
t = (pathlib.Path.home()/"TransportMCP/.env").read_text(encoding="utf-8")
k = re.search(r'^\s*(?:export\s+)?%s\s*=\s*"?([^"\s]+)' % nome, t, re.M).group(1)
d = hashlib.sha256(k.encode()).hexdigest()[:12]
req = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions",
    data=json.dumps({"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"ok"}],
                     "max_tokens":1}).encode(),
    headers={"Authorization":"Bearer "+k,"Content-Type":"application/json"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print("  [ok]   digital %s: HTTP %d, chave VALIDA para inferencia" % (d, r.status))
except urllib.error.HTTPError as e:
    print("  [ERRO] digital %s: HTTP %d. 403 pode ser chave valida com ORGANIZACAO errada" % (d, e.code))
except Exception as e:
    print("  [!]    digital %s: sem resposta (%s). Isso e rede, nao autorizacao." % (d, str(e)[:40]))
PY
    ;;
  *) echo "  (sem teste automatico para $NOME; conferir pela ferramenta que a usa)";;
esac

echo
if grep -q . "$BKP" 2>/dev/null; then
    read -rp "  Apagar a copia de seguranca (ela contem a chave ANTIGA)? [S/n] " R
    case "${R:-S}" in [Nn]*) echo "  mantida em $BKP (permissao 600). Apague quando puder.";;
                      *) shred -u "$BKP" 2>/dev/null || rm -f "$BKP"; ok "copia apagada";; esac
fi
unset NOVA ANTIGA CONF
echo
echo "  LEMBRETE: se esta chave tambem estiver no Claude Desktop do Windows, ela"
echo "  precisa ser trocada LA tambem, com o aplicativo FECHADO, inclusive a bandeja."
echo
