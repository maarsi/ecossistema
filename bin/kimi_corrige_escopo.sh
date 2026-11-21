#!/bin/bash
# ===========================================================================
# CORREÇÃO do roteiro anterior.
#
# O QUE DEU ERRADO: eu dei ao usuário kimi permissão de ATRAVESSAR a sua pasta
# pessoal, para que ele chegasse em ~/base_conhecimento. Mas quase toda pasta
# dentro da sua casa é legível por qualquer usuário, então a travessia abriu
# 97 itens de uma vez, incluindo auditoria_tpc_rms, sistema_rio_pd,
# pd_campo_analise, acervo_divorcio_index, ocr_partilha e JuridicoMCP. Material
# de cliente, parte dele jurídico. A conferência do próprio roteiro foi o que
# pegou isso, por um arquivo só (.bashrc), e a investigação mostrou os outros 96.
#
# JÁ CORRIGIDO, sem senha: a travessia foi revogada. Hoje o kimi não alcança
# NADA na sua pasta pessoal, nem o que ele precisa.
#
# O QUE ESTE ROTEIRO FAZ: dá acesso à pasta de trabalho por um caminho PRÓPRIO,
# fora da sua casa, em vez de abrir a porta da casa. É a diferença entre
# entregar a chave de um armário e entregar a chave da portaria.
#
# COMO RODAR:  sudo bash kimi_corrige_escopo.sh
# ===========================================================================
set -u
DONO=mateus; AGENTE=kimi; BASE=/srv/kimi
ok(){ echo "  [ok]   $*"; }; erro(){ echo "  [ERRO] $*"; }
[ "$(id -u)" -eq 0 ] || { erro "rode com sudo"; exit 1; }

echo
echo "=== 1. garantir que a travessia na pasta pessoal esta REVOGADA"
if getfacl -c "/home/$DONO" 2>/dev/null | grep -q "user:$AGENTE:"; then
    setfacl -x "u:$AGENTE" "/home/$DONO" && ok "revogada agora"
else
    ok "ja estava revogada"
fi

echo
echo "=== 2. criar o caminho proprio do agente, fora da sua casa"
install -d -o root -g root -m 755 "$BASE"           && ok "$BASE criado"
install -d -o root -g root -m 755 "$BASE/base_conhecimento" && ok "ponto de montagem pronto"

echo
echo "=== 3. ligar a pasta de trabalho ao caminho proprio"
# "bind" faz a MESMA pasta aparecer em dois lugares. Nao e copia: e o mesmo
# conteudo, sem duplicar espaco. O que decide o acesso e a permissao da pasta
# em si, e nao o caminho usado para chegar nela. Por isso o agente passa a
# alcancar base_conhecimento sem precisar atravessar /home/mateus.
if mountpoint -q "$BASE/base_conhecimento"; then
    ok "ja montado"
else
    mount --bind "/home/$DONO/base_conhecimento" "$BASE/base_conhecimento" \
        && ok "montado" || { erro "falhou a montagem"; exit 1; }
fi
F=/etc/fstab
if grep -q "$BASE/base_conhecimento" "$F"; then
    ok "fstab ja tem a entrada (sobrevive ao reinicio)"
else
    cp -a "$F" "$F.antes_bind_$(date +%Y%m%d_%H%M%S)" && ok "backup do fstab"
    printf '\n# pasta de trabalho do agente kimi, sem travessia na home do mateus\n%s %s none bind,nosuid,nodev 0 0\n' \
        "/home/$DONO/base_conhecimento" "$BASE/base_conhecimento" >> "$F"
    ok "entrada acrescentada ao fstab"
    systemctl daemon-reload && ok "systemd recarregado"
fi

echo
echo "=== 4. CONFERENCIA, que e a parte que vale"
echo "  --- NAO pode alcancar (sua casa inteira):"
falhas=0
for f in "/home/$DONO/TransportMCP/.env" "/home/$DONO/.ssh/id_ed25519_lote" \
         "/home/$DONO/.bashrc" "/home/$DONO/auditoria_tpc_rms" \
         "/home/$DONO/sistema_rio_pd" "/home/$DONO/acervo_divorcio_index" \
         "/home/$DONO/ecossistema" "/home/$DONO/GoogleDrive" \
         "/home/$DONO/base_conhecimento" "/media/$DONO/DADOS_01" \
         "/mnt/nvme_lexar/acervo"; do
    if sudo -u "$AGENTE" test -r "$f" 2>/dev/null; then erro "ALCANCA: $f"; falhas=$((falhas+1))
    else ok "bloqueado: $f"; fi
done
echo "  --- PRECISA alcancar (pelo caminho proprio):"
sudo -u "$AGENTE" test -r "$BASE/base_conhecimento" 2>/dev/null \
    && ok "le:    $BASE/base_conhecimento" || { erro "NAO le"; falhas=$((falhas+1)); }
T="$BASE/base_conhecimento/.escrita_$$"
if sudo -u "$AGENTE" touch "$T" 2>/dev/null; then ok "escreve: $BASE/base_conhecimento"; rm -f "$T"
else erro "NAO escreve"; falhas=$((falhas+1)); fi
sudo -u "$AGENTE" test -r "$BASE/base_conhecimento/CLAUDE.md" 2>/dev/null \
    && ok "le as regras: CLAUDE.md" || erro "NAO le o CLAUDE.md"

echo
if [ "$falhas" -eq 0 ]; then echo "  RESULTADO: contencao completa, nenhuma falha."
else echo "  RESULTADO: $falhas falha(s). Me mande esta tela."; fi
echo
echo "COMO USAR daqui em diante:"
echo "  sudo -u $AGENTE -H bash -c 'cd $BASE/base_conhecimento && ~/.kimi-code/bin/kimi'"
echo "  (vou montar um atalho para isso depois que voce confirmar)"
echo
# ===========================================================================
# DESFAZER:
#   sudo umount /srv/kimi/base_conhecimento
#   sudo sed -i '\|/srv/kimi/base_conhecimento|d' /etc/fstab
#   sudo rmdir /srv/kimi/base_conhecimento /srv/kimi
#   sudo systemctl daemon-reload
# ===========================================================================
