#!/bin/bash
# Cria o ícone "Contador de Pessoas" na área de trabalho e no menu.
# Rodar uma vez:   bash instalar_atalho.sh
# Para remover:    bash instalar_atalho.sh --remover

cd "$(dirname "$(readlink -f "$0")")" || exit 1
PASTA="$(pwd)"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null)"
[ -z "$DESK" ] && DESK="$HOME/Desktop"
ARQ="contador-de-pessoas.desktop"
MENU="$HOME/.local/share/applications"

if [ "$1" = "--remover" ]; then
    rm -f "$DESK/$ARQ" "$MENU/$ARQ"
    echo "Atalhos removidos."
    exit 0
fi

chmod +x iniciar.sh
mkdir -p "$DESK" "$MENU"

cat > "$DESK/$ARQ" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Contador de Pessoas
Comment=Contagem, reconhecimento e cadastro (15a Jornacitec)
Exec=$PASTA/iniciar.sh
Icon=$PASTA/icone.png
Terminal=false
Categories=Utility;
StartupNotify=false
DESKTOP

chmod +x "$DESK/$ARQ"
gio set "$DESK/$ARQ" metadata::trusted true 2>/dev/null || true
cp "$DESK/$ARQ" "$MENU/$ARQ"

echo "Ícone criado em: $DESK/$ARQ"
echo "Também está no menu (Acessórios). Se o ícone aparecer com um"
echo "cadeado ou pedir confirmação, clique com o botão direito e escolha"
echo "'Permitir execução'/'Executar'."
