# Atalho do Kimi Code contido.  Fonte: ~/ecossistema/bin/kimi_guarda.sh
#
# Voce digita "kimi" e o agente abre como o usuario kimi, dentro de
# /srv/kimi/base_conhecimento, sem alcance na sua pasta pessoal, no D: nem no
# Google Drive. Medido em 21/11/2026: 0 itens da sua casa alcancaveis.
#
# Historico que justifica cada linha:
#   - o projeto do Kimi Code nasce com raiz no diretorio de onde foi lancado;
#   - lancado da sua casa, confiou /home/mateus inteira;
#   - raiz de projeto NAO e barreira: ele leu arquivo modo 600 fora dela;
#   - dar travessia na casa para ele chegar na pasta de trabalho abriu 97 itens,
#     inclusive material de cliente. Por isso o acesso e por /srv/kimi.

kimi() {
    local agente=kimi pasta="${KIMI_PASTA:-base_conhecimento}"
    local raiz="/srv/$agente/$pasta"

    if ! sudo -n -u "$agente" true 2>/dev/null; then
        echo "RECUSADO: nao consigo agir como o usuario $agente." >&2
        echo "  Rode:  sudo bash ~/ecossistema/bin/kimi_usuario_separado.sh" >&2
        return 1
    fi
    if ! mountpoint -q "$raiz" 2>/dev/null; then
        echo "RECUSADO: $raiz nao esta montado." >&2
        echo "  Rode:  sudo bash ~/ecossistema/bin/kimi_corrige_escopo.sh" >&2
        echo "  Pastas disponiveis:" >&2
        ls -1 "/srv/$agente" 2>/dev/null | sed 's/^/    KIMI_PASTA=/' >&2
        return 1
    fi

    case " $* " in
        *" --auto "*)
            if [ "$KIMI_AUTO_OK" != "1" ]; then
                echo "RECUSADO: --auto desliga toda aprovacao." >&2
                echo "  A guarda de segredo da ferramenta Read e trava real; no Bash dele e" >&2
                echo "  apenas instrucao (3 de 3 recusas em 21/11/2026, amostra pequena)." >&2
                echo "  Hoje o agente nao alcanca credencial nenhuma, entao o risco e menor," >&2
                echo "  e segue sendo decisao consciente:  KIMI_AUTO_OK=1 kimi --auto" >&2
                return 1
            fi ;;
    esac

    echo "Kimi Code como usuario '$agente', em $raiz"
    sudo -n -u "$agente" -H bash -c \
        'cd "$1" || exit 1; shift; exec "$HOME/.kimi-code/bin/kimi" "$@"' \
        "$agente" "$raiz" "$@"
}

# Atalho para abrir um shell como o agente, util para conferir o que ele ve.
kimi-shell() { sudo -n -u kimi -H bash -c 'cd /srv/kimi 2>/dev/null; exec bash -i'; }
