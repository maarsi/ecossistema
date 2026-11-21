#!/bin/bash
# ===========================================================================
# Põe o Kimi Code para rodar com usuário próprio, sem acesso às credenciais.
#
# POR QUE: hoje o Kimi Code roda COMO VOCÊ, e por isso alcança tudo o que você
# alcança, inclusive ~/TransportMCP/.env (9 chaves) e ~/.ssh. A proteção atual
# dele é instrução ("não leia arquivos de segredo"), não permissão de sistema.
# Com um usuário próprio, a proteção passa a ser do sistema operacional.
#
# COMO RODAR:   sudo bash kimi_usuario_separado.sh
# PARA DESFAZER: ver o bloco DESFAZER no fim deste arquivo.
# ===========================================================================
set -u

DONO=mateus
AGENTE=kimi
UID_AGENTE=1001

# Pastas que o agente PODE escrever. Comece pelo mínimo; acrescentar depois é
# uma linha de comando, tirar acesso já concedido é mais trabalhoso.
PASTAS_RW=( "/home/$DONO/base_conhecimento" )
# Pastas que o agente PODE ler e NÃO pode escrever. O ecossistema entra aqui de
# propósito: é pasta do Syncthing e repositório git, e arquivo criado por outro
# usuário dentro dela geraria confusão de dono.
PASTAS_RO=( "/home/$DONO/ecossistema" )

ok()   { echo "  [ok]   $*"; }
aviso(){ echo "  [!]    $*"; }
erro() { echo "  [ERRO] $*"; }

[ "$(id -u)" -eq 0 ] || { erro "rode com sudo"; exit 1; }
echo
echo "=== 1. usuário $AGENTE"
if id "$AGENTE" &>/dev/null; then
    ok "já existe (uid $(id -u $AGENTE))"
else
    useradd -m -u "$UID_AGENTE" -s /bin/bash -c "Agente Kimi Code, sem privilegio" "$AGENTE" \
        && ok "criado com uid $UID_AGENTE" || { erro "falhou ao criar"; exit 1; }
fi
passwd -l "$AGENTE" >/dev/null 2>&1 && ok "senha travada: não entra por login direto"
if id -nG "$AGENTE" | grep -qw sudo; then erro "está no grupo sudo, REMOVA"; else ok "fora do grupo sudo"; fi

echo
echo "=== 2. permissões: travessia na sua pasta pessoal, sem poder listar"
# --x deixa ATRAVESSAR para chegar às subpastas liberadas, e NÃO deixa listar o
# conteúdo da pasta pessoal. Quem não sabe o caminho exato não acha nada.
setfacl -m "u:$AGENTE:--x" "/home/$DONO" && ok "travessia concedida em /home/$DONO"

for p in "${PASTAS_RW[@]}"; do
    [ -d "$p" ] || { aviso "não existe, pulei: $p"; continue; }
    setfacl -R -m "u:$AGENTE:rwX" -m "d:u:$AGENTE:rwX" -m "d:u:$DONO:rwX" "$p" \
        && ok "leitura e escrita: $p"
done
for p in "${PASTAS_RO[@]}"; do
    [ -d "$p" ] || { aviso "não existe, pulei: $p"; continue; }
    setfacl -R -m "u:$AGENTE:rX"  -m "d:u:$AGENTE:rX"  "$p" \
        && ok "somente leitura: $p"
done

echo
echo "=== 3. fechar o disco D: para outros usuários"
# O D: é montado por rede e hoje chega com permissão 0755, ou seja, qualquer
# usuário da máquina lê o acervo de cliente. Vamos para 0700.
F=/etc/fstab
if grep -q 'DADOS_01.*file_mode=0700' "$F"; then
    ok "fstab já está com file_mode=0700"
else
    cp -a "$F" "$F.antes_kimi_$(date +%Y%m%d_%H%M%S)" && ok "backup do fstab feito"
    sed -i 's|\(//100.119.22.38/DADOS_01[^\n]*uid=1000,gid=1000\)|\1,file_mode=0700,dir_mode=0700|' "$F"
    grep -q 'DADOS_01.*file_mode=0700' "$F" && ok "fstab ajustado" || erro "fstab NÃO mudou, confira à mão"
    systemctl daemon-reload && ok "systemd recarregado (vale na próxima montagem)"
fi

echo
echo "=== 4. deixar você abrir o agente sem digitar senha toda vez"
D=/etc/sudoers.d/kimi-agente
echo "$DONO ALL=($AGENTE) NOPASSWD: ALL" > "$D"
chmod 440 "$D"
visudo -c -f "$D" >/dev/null 2>&1 && ok "regra de sudo válida: $DONO pode rodar como $AGENTE" \
                                  || { erro "regra inválida, removendo"; rm -f "$D"; }

echo
echo "=== 5. instalar o Kimi Code para o agente"
O="/home/$DONO/.kimi-code"; N="/home/$AGENTE/.kimi-code"
if [ -x "$N/bin/kimi" ]; then
    ok "já instalado em $N"
else
    install -d -o "$AGENTE" -g "$AGENTE" -m 700 "$N" "$N/bin"
    cp "$O/bin/kimi" "$N/bin/kimi" && chown "$AGENTE:$AGENTE" "$N/bin/kimi" && chmod 755 "$N/bin/kimi"
    [ -f "$O/config.toml" ] && cp "$O/config.toml" "$N/" && chown "$AGENTE:$AGENTE" "$N/config.toml"
    ok "binário copiado. As CREDENCIAIS não foram copiadas de propósito:"
    echo "         o agente faz o próprio /login na primeira vez."
fi

echo
echo "=== 6. CONFERÊNCIA: o que o agente NÃO consegue ler"
testa() {
    if sudo -u "$AGENTE" test -r "$1" 2>/dev/null; then erro "ALCANÇA: $1"; else ok "bloqueado: $1"; fi
}
testa "/home/$DONO/TransportMCP/.env"
testa "/home/$DONO/.ssh/id_ed25519_lote"
testa "/home/$DONO/.ssh/id_ed25519_github"
testa "/home/$DONO/.smbcredentials"
testa "/home/$DONO/.bashrc"
testa "/home/$DONO/GoogleDrive"
echo "  --- e o que ele PRECISA alcançar:"
for p in "${PASTAS_RW[@]}" "${PASTAS_RO[@]}"; do
    if sudo -u "$AGENTE" test -r "$p" 2>/dev/null; then ok "lê: $p"; else erro "NÃO lê: $p"; fi
done
echo
echo "FIM. Para usar:   sudo -u $AGENTE -H bash -c 'cd <pasta> && ~/.kimi-code/bin/kimi'"
echo

# ===========================================================================
# DESFAZER, se algo der errado:
#   sudo setfacl -R -x u:kimi /home/mateus/base_conhecimento
#   sudo setfacl -R -x u:kimi /home/mateus/ecossistema
#   sudo setfacl -x u:kimi /home/mateus
#   sudo rm -f /etc/sudoers.d/kimi-agente
#   sudo userdel -r kimi
#   sudo cp /etc/fstab.antes_kimi_<data> /etc/fstab && sudo systemctl daemon-reload
# ===========================================================================
