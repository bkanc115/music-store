#!/usr/bin/env bash
# Выпуск версии приложения (первый или обновление, а также возврат к предыдущей):
#   1. код тега из Git -> /opt/musicstore/releases/<версия>
#   2. виртуальное окружение и зависимости
#   3. миграции БД (от роли-владельца схемы)
#   4. переключение ссылки current и перезапуск службы
#   5. проверка /health
#
# Использование: sudo ./app/deploy-release.sh v0.2.0 [--seed]
source "$(dirname "$0")/../common/lib.sh"
require_root
load_inventory

VERSION="${1:-$APP_VERSION}"
SEED="${2:-}"
RELEASE="$APP_ROOT/releases/$VERSION"

if [[ ! -d $RELEASE ]]; then
    log "Получение $VERSION из $REPO_URL"
    git clone --quiet --depth 1 --branch "$VERSION" "$REPO_URL" "$RELEASE.tmp"
    rm -rf "$RELEASE.tmp/.git"
    log "Зависимости"
    python3 -m venv "$RELEASE.tmp/.venv"
    "$RELEASE.tmp/.venv/bin/pip" install --quiet --upgrade pip
    "$RELEASE.tmp/.venv/bin/pip" install --quiet -r "$RELEASE.tmp/requirements.txt"
    chown -R root:root "$RELEASE.tmp"
    chmod -R go-w "$RELEASE.tmp"
    mv "$RELEASE.tmp" "$RELEASE"
else
    log "Выпуск $VERSION уже загружен"
fi

log "Миграции БД"
(
    cd "$RELEASE"
    set -a; source "$APP_CONFIG_DIR/migrate.env"; set +a
    export PYTHONDONTWRITEBYTECODE=1
    runuser -u "$APP_USER" -- .venv/bin/python -m alembic upgrade head
    if [[ $SEED == --seed ]]; then
        runuser -u "$APP_USER" -- .venv/bin/python -m app.seed --demo
    fi
)

log "Переключение на $VERSION и перезапуск"
ln -sfn "$RELEASE" "$APP_ROOT/current.new"
mv -T "$APP_ROOT/current.new" "$APP_ROOT/current"
systemctl restart musicstore

for _ in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:$APP_PORT/health"; then
        echo
        log "Выпуск $VERSION работает"
        exit 0
    fi
    sleep 1
done
systemctl status musicstore --no-pager || true
die "Служба не ответила на /health"
