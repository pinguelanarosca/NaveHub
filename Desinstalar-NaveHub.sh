#!/usr/bin/env bash
# Desinstalador completo do NaveHub.
# Remove arquivos do aplicativo, dados do usuário, atalhos e temporários.
# Não remove Python, Chromium ou pacotes compartilhados do sistema.

set -Eeuo pipefail

APP_NAME="NaveHub"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/navehub"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
DESKTOP_DIR="${DESKTOP_DIR:-$HOME/Desktop}"
DESKTOP_FILE="navehub.desktop"

say() {
    printf '\n==> %s\n' "$*"
}

fail() {
    printf '\nERRO: %s\n' "$*" >&2
    exit 1
}

if [[ $EUID -eq 0 ]]; then
    fail "Não execute este desinstalador com sudo. Use: ./$0"
fi

printf '%s\n' "========================================"
printf '%s\n' "        DESINSTALADOR DO NAVEHUB"
printf '%s\n' "========================================"
printf '\n'
printf '%s\n' "Isso removerá permanentemente:"
printf '  - %s\n' "$INSTALL_DIR"
printf '  - %s\n' "$HOME/.navehub"
printf '  - %s\n' "$APPLICATIONS_DIR/$DESKTOP_FILE"
printf '  - %s\n' "$DESKTOP_DIR/$DESKTOP_FILE"
printf '  - temporários do NaveHub em /tmp'
printf '\n'
printf '%s\n' "Python, Chromium e dependências do sistema NÃO serão removidos."
printf '\n'

read -r -p "Digite SIM para continuar: " CONFIRM

if [[ "$CONFIRM" != "SIM" ]]; then
    say "Desinstalação cancelada."
    exit 0
fi

say "Removendo instalação principal..."
rm -rf -- "$INSTALL_DIR"

say "Removendo dados do usuário..."
rm -rf -- "$HOME/.navehub"

say "Removendo atalho do menu..."
rm -f -- "$APPLICATIONS_DIR/$DESKTOP_FILE"

say "Removendo atalho da área de trabalho..."
rm -f -- "$DESKTOP_DIR/$DESKTOP_FILE"

say "Limpando temporários do NaveHub..."
find "${TMPDIR:-/tmp}" \
    -maxdepth 1 \
    -type d \
    \( \
        -name 'navehub-installer.*' \
        -o -name 'navehub-restore-*' \
        -o -name 'navehub-rollback-*' \
    \) \
    -exec rm -rf -- {} + 2>/dev/null || true

if command -v update-desktop-database >/dev/null 2>&1; then
    say "Atualizando banco de atalhos..."
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

say "Verificando remoção..."

REMAINING=0

for path in \
    "$INSTALL_DIR" \
    "$HOME/.navehub" \
    "$APPLICATIONS_DIR/$DESKTOP_FILE" \
    "$DESKTOP_DIR/$DESKTOP_FILE"
do
    if [[ -e "$path" || -L "$path" ]]; then
        printf '  [ERRO] ainda existe: %s\n' "$path"
        REMAINING=1
    else
        printf '  [OK] removido: %s\n' "$path"
    fi
done

printf '\n'

if [[ "$REMAINING" -ne 0 ]]; then
    fail "A desinstalação terminou, mas alguns arquivos ainda existem."
fi

printf '%s\n' "========================================"
printf '%s\n' "     NAVEHUB DESINSTALADO COM SUCESSO"
printf '%s\n' "========================================"
