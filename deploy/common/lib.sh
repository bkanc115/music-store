#!/usr/bin/env bash
# Общие функции для скриптов развёртывания.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "Запустите через sudo"
}

load_inventory() {
    # shellcheck source=../inventory.env
    source "$DEPLOY_DIR/inventory.env"
}

load_secrets() {
    local f="$DEPLOY_DIR/secrets.env"
    [[ -f $f ]] || die "Нет $f (создайте из secrets.env.example)"
    # shellcheck disable=SC1090
    source "$f"
    for v in "$@"; do
        [[ -n ${!v:-} ]] || die "В secrets.env не задан $v"
    done
}

# Записывает файл, только если содержимое изменилось (повторный запуск ничего не ломает).
write_file() {
    local path="$1" mode="$2" owner="$3" tmp
    tmp="$(mktemp)"
    cat >"$tmp"
    if [[ -f $path ]] && cmp -s "$tmp" "$path"; then
        rm -f "$tmp"
    else
        install -D -m "$mode" -o "${owner%%:*}" -g "${owner##*:}" "$tmp" "$path"
        rm -f "$tmp"
        log "записан $path"
    fi
}
