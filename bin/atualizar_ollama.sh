#!/usr/bin/env bash
# Atualiza o Ollama pelo instalador oficial. As configuracoes moram em drop-ins
# (/etc/systemd/system/ollama.service.d/override.conf e 10-desempenho.conf), que o instalador NAO toca.
# Rodar no terminal da Ubuntu:  bash ~/ecossistema/bin/atualizar_ollama.sh
set -uo pipefail
LOG=/mnt/nvme_lexar/logs/ollama_atualizacao_$(date +%Y%m%d_%H%M).txt
exec > >(tee -a "$LOG") 2>&1
echo "antes: $(ollama --version)"
sudo -v || exit 1
sudo cp -a /usr/local/bin/ollama /usr/local/bin/ollama.0.34.0.bak && echo "copia do binario antigo: /usr/local/bin/ollama.0.34.0.bak"
curl -fsSL https://ollama.com/install.sh | sh || { echo "FALHOU o instalador"; exit 1; }
sudo systemctl daemon-reload; sudo systemctl restart ollama; sleep 5
echo "depois: $(ollama --version)"
systemctl show ollama -p Environment | tr ' ' '\n' | grep -E 'OLLAMA_(MODELS|HOST|FLASH|KV|KEEP)'
ollama list | awk 'NR>1{print $1, $2}' > /tmp/ollama_depois.txt
diff /mnt/nvme_lexar/logs/ollama_modelos_antes_0.40.19.txt /tmp/ollama_depois.txt && echo "MODELOS IGUAIS (nomes e digests)"
echo "Log: $LOG"
