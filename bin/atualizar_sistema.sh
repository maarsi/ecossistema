#!/usr/bin/env bash
# Atualizacao do sistema da workstation (apt, snap, flatpak), com snapshot antes.
# NAO mexe em: Docker (politica: manual, um por vez), Ollama e modelos, NVIDIA/CUDA,
# ambientes Python. Rodar no terminal da Ubuntu:  bash ~/ecossistema/bin/atualizar_sistema.sh
set -uo pipefail
LOG=/mnt/nvme_lexar/logs/atualizacao_$(date +%Y%m%d_%H%M).txt
exec > >(tee -a "$LOG") 2>&1
etapa(){ echo; echo "=== $(date +%T) $*"; }

etapa "0. Conferencia previa"
lsb_release -ds; uname -r
OCUP=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null)
[ -n "$OCUP" ] && { echo "AVISO: processos usando a GPU:"; echo "$OCUP"; }
read -rp "Continuar? [s/N] " r; [[ "$r" =~ ^[sS]$ ]] || { echo "Cancelado."; exit 1; }
sudo -v || exit 1

etapa "1. Snapshot Timeshift (ponto de retorno)"
sudo timeshift --create --comments "antes da atualizacao $(date +%d/%m/%Y)" --tags O \
  || { echo "FALHOU o snapshot. Parando sem atualizar."; exit 1; }

etapa "2. Pacotes do sistema (apt)"
sudo apt-get update
sudo apt-get -y full-upgrade
sudo apt-get -y autoremove --purge

etapa "3. Snaps"
sudo snap refresh

etapa "4. Flatpak (e remocao de runtimes sem uso, como drivers NVIDIA antigos)"
flatpak update -y
flatpak uninstall --unused -y

etapa "5. Conferencia depois"
apt list --upgradable 2>/dev/null | tail -n +2 | wc -l | xargs echo "apt ainda pendentes:"
nvidia-smi --query-gpu=driver_version --format=csv,noheader
python3 ~/ecossistema/bin/inventario.py >/dev/null 2>&1 && echo "inventario regravado"
[ -f /var/run/reboot-required ] && echo "REINICIO NECESSARIO: $(tr '\n' ' ' < /var/run/reboot-required.pkgs)"
echo "Log: $LOG"

read -rp "Reiniciar agora? [s/N] " r
[[ "$r" =~ ^[sS]$ ]] && sudo systemctl reboot
