#!/bin/sh
# Sobe um servidor MCP do ecossistema para o Claude Code INSTALADO NA UBUNTU.
#
# POR QUE ESTE INVOLUCRO EXISTE. O `claude mcp add` aceita -e CHAVE=valor, mas isso
# gravaria a credencial em texto puro em ~/.claude.json, que nao tem permissao 600.
# Seria a quinta copia de cada chave e multiplicaria o trabalho de rotacao. Aqui a
# chave continua existindo em UM lugar na Ubuntu: ~/TransportMCP/.env, 600, fora do
# versionamento e fora do Syncthing.
#
# Este arquivo NAO contem credencial e por isso pode ser versionado.
#
# Uso: mcp_local.sh <nome_do_servidor.py>
set -a
[ -f "$HOME/TransportMCP/.env" ] && . "$HOME/TransportMCP/.env"
set +a
exec "$HOME/TransportMCP/.venv/bin/python" "$HOME/ecossistema/mcp/windows/$1"
