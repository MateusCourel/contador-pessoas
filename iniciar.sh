#!/bin/bash
# Inicia o Contador de Pessoas (TV + monitor touch).
# Usado pelo ícone da área de trabalho; também funciona no terminal:
#     ./iniciar.sh              (aceita as mesmas opções do principal.py)
# A saída do programa fica em dados/principal.log (útil se algo der errado).

cd "$(dirname "$(readlink -f "$0")")" || exit 1
mkdir -p dados

# só uma cópia por vez (toque duplo no ícone não abre dois programas)
exec 9>/tmp/contador-pessoas.lock
flock -n 9 || { echo "Já está rodando."; exit 0; }

source "$HOME/contador/bin/activate"
export DISPLAY="${DISPLAY:-:0}"

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') iniciando ==="
    if [ ! -w /dev/uinput ]; then
        echo "AVISO: sem permissão em /dev/uinput; as janelas podem abrir na mesma tela."
        echo "       (veja o README: regra udev + grupo input, depois reiniciar)"
    fi
} > dados/principal.log

python principal.py "$@" >> dados/principal.log 2>&1
