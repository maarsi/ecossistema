# Guarda de lancamento do Kimi Code.  Fonte: ~/ecossistema/bin/kimi_guarda.sh
# NAO e conselho: e recusa. Medido em 21/11/2026 na propria maquina:
#   - o projeto do Kimi Code nasce com raiz = diretorio de onde ele foi lancado;
#   - lancado da home, confiou /home/mateus inteira, com o .env de 9 credenciais,
#     a chave SSH sem senha dos notebooks e a montagem rclone do Google Drive;
#   - raiz de projeto NAO e barreira de leitura: ele leu arquivo modo 600 fora dela.
# Logo, o lugar de onde se lanca e a unica parte do escopo que se controla de fato.

kimi() {
    local bin="$HOME/.kimi-code/bin/kimi"
    [ -x "$bin" ] || { echo "kimi nao encontrado em $bin" >&2; return 127; }

    local aqui motivo=""
    aqui="$(pwd -P)"
    case "$aqui" in
        "$HOME")
            motivo="a raiz do projeto seria a sua HOME inteira, que contem ~/TransportMCP/.env com 9 credenciais, ~/.ssh/id_ed25519_lote (sem senha, abre geneve e Zurich) e ~/GoogleDrive" ;;
        "$HOME"/GoogleDrive|"$HOME"/GoogleDrive/*)
            motivo="e montagem fuse.rclone do Google Drive: acervo de cliente, e varredura ali nao termina" ;;
        /media/mateus/DADOS_01|/media/mateus/DADOS_01/*)
            motivo="e CIFS sobre Tailscale, nao disco local: lote aqui le pela rede, a 11 s por documento" ;;
        /|/home|/etc|/usr|/var)
            motivo="e diretorio de sistema" ;;
    esac

    if [ -n "$motivo" ] && [ "$KIMI_IGNORAR_GUARDA" != "1" ]; then
        echo "RECUSADO: nao lance o Kimi Code a partir de $aqui" >&2
        echo "  Motivo: $motivo." >&2
        echo "  Lance de dentro da pasta de trabalho. Raizes com CLAUDE.md de guarda:" >&2
        local d
        for d in ecossistema base_conhecimento r5_salvador ciencia; do
            [ -d "$HOME/$d" ] && echo "    cd ~/$d && kimi" >&2
        done
        echo "  Para forcar, conscientemente:  KIMI_IGNORAR_GUARDA=1 kimi" >&2
        return 1
    fi

    case " $* " in
        *" --auto "*)
            if [ "$KIMI_AUTO_OK" != "1" ]; then
                echo "RECUSADO: --auto desliga toda aprovacao." >&2
                echo "  A guarda de segredo da ferramenta Read e trava real, mas no Bash dele" >&2
                echo "  e apenas INSTRUCAO (medido em 21/11/2026: 3 de 3 recusas, amostra pequena)." >&2
                echo "  Sem ninguem para aprovar, a protecao do .env passa a depender de obediencia." >&2
                echo "  Se for mesmo o que voce quer:  KIMI_AUTO_OK=1 kimi --auto" >&2
                return 1
            fi ;;
    esac

    "$bin" "$@"
}
