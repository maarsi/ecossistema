#!/bin/bash
# ===========================================================================
# Fecha a ultima brecha: o disco D:, montado pela rede.
#
# POR QUE NAO BASTOU O QUE JA FIZEMOS: a opcao que restringe o D: foi escrita
# no /etc/fstab, mas opcao de montagem so passa a valer na PROXIMA vez que o
# disco e montado. A montagem de agora continua com a permissao antiga.
#
# POR QUE NAO VAMOS DESMONTAR AGORA: o backup restic esta rodando e usando o
# disco. Desmontar interromperia o backup no meio.
#
# O QUE ESTE ROTEIRO FAZ: em vez de mexer no disco, fecha a PASTA QUE DA
# ACESSO a ele. Hoje /media/mateus e aberta a qualquer usuario; passa a ser
# sua. Vale na hora, sem desmontar nada, e sobrevive ao reinicio.
#
# COMO RODAR:  sudo bash kimi_fecha_disco.sh
# ===========================================================================
set -u
ok(){ echo "  [ok]   $*"; }; erro(){ echo "  [ERRO] $*"; }
[ "$(id -u)" -eq 0 ] || { erro "rode com sudo"; exit 1; }

echo
echo "=== 1. estado antes"
echo "  /media/mateus      $(stat -c '%A %U:%G' /media/mateus)"
echo "  montagem ativa:    $(findmnt -n -o OPTIONS /media/mateus/DADOS_01 2>/dev/null | tr ',' '\n' | grep -E 'file_mode' || echo 'sem file_mode')"

echo
echo "=== 2. fechar a pasta de acesso"
# root continua dono; o grupo passa a ser mateus, para que VOCE continue
# entrando normalmente. Quem nao e voce nem root nao atravessa mais.
chown root:mateus /media/mateus && chmod 750 /media/mateus \
    && ok "/media/mateus agora e $(stat -c '%A %U:%G' /media/mateus)" \
    || { erro "falhou"; exit 1; }

echo
echo "=== 3. tornar permanente (senao o sistema recria aberta no reinicio)"
T=/etc/tmpfiles.d/media-mateus.conf
printf '# mantem /media/mateus fechada a outros usuarios entre reinicios\n# motivo: o D: e montado por rede e seu conteudo e material de cliente\nd /media/mateus 0750 root mateus -\n' > "$T"
systemd-tmpfiles --create "$T" >/dev/null 2>&1 && ok "regra permanente gravada em $T" \
    || ok "regra gravada em $T (aplicada no proximo arranque)"

echo
echo "=== 4. CONFERENCIA"
falhas=0
for f in /media/mateus/DADOS_01 /media/mateus/DADOS; do
    if sudo -u kimi test -r "$f" 2>/dev/null; then erro "kimi ALCANCA: $f"; falhas=$((falhas+1))
    else ok "kimi bloqueado: $f"; fi
done
if sudo -u mateus test -r /media/mateus/DADOS_01 2>/dev/null; then ok "VOCE continua lendo o D:"
else erro "VOCE perdeu acesso ao D:, desfaca com: chmod 755 /media/mateus"; falhas=$((falhas+1)); fi
if pgrep -f 'restic backup' >/dev/null; then ok "restic segue rodando, nao foi interrompido"
else ok "restic nao esta rodando"; fi

echo
if [ "$falhas" -eq 0 ]; then echo "  RESULTADO: contencao completa."
else echo "  RESULTADO: $falhas falha(s). Me mande esta tela."; fi
echo
echo "NOTA: a opcao file_mode=0700 do /etc/fstab continua la e passa a valer"
echo "      sozinha na proxima montagem do D:, somando-se a esta protecao."
echo
# DESFAZER:  sudo chmod 755 /media/mateus
#            sudo rm -f /etc/tmpfiles.d/media-mateus.conf
