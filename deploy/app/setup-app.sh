#!/usr/bin/env bash
# Сервер приложения: среда выполнения, пользователь службы, каталоги и права,
# настройки в /etc/musicstore, первый выпуск приложения, systemd-служба, firewall.
#
# Использование: sudo ./app/setup-app.sh
source "$(dirname "$0")/../common/lib.sh"
require_root
load_inventory
load_secrets DB_MIGRATOR_PASSWORD DB_APP_PASSWORD SECRET_KEY ADMIN_USERNAME ADMIN_PASSWORD

log "Среда выполнения"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q python3 python3-venv git postgresql-client

log "Пользователь службы $APP_USER (системный, без shell)"
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --home-dir "$APP_ROOT" --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

log "Каталоги и права"
# код: владелец root, служба может только читать
install -d -m 755 -o root -g root "$APP_ROOT" "$APP_ROOT/releases"
# настройки: читает только root и группа службы
install -d -m 750 -o root -g "$APP_USER" "$APP_CONFIG_DIR"
# журналы: пишет только служба
install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$APP_LOG_DIR"

log "Настройки приложения $APP_CONFIG_DIR/app.env"
write_file "$APP_CONFIG_DIR/app.env" 640 "root:$APP_USER" <<EOF
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=$APP_PORT
DATABASE_URL=postgresql+psycopg://$DB_APP_ROLE:$DB_APP_PASSWORD@$DB_HOSTNAME:5432/$DB_NAME
SECRET_KEY=$SECRET_KEY
SESSION_HTTPS_ONLY=false
LOG_LEVEL=INFO
LOG_FILE=$APP_LOG_DIR/app.log
EOF

log "Настройки миграций $APP_CONFIG_DIR/migrate.env (только root)"
write_file "$APP_CONFIG_DIR/migrate.env" 600 root:root <<EOF
DATABASE_URL=postgresql+psycopg://$DB_MIGRATOR_ROLE:$DB_MIGRATOR_PASSWORD@$DB_HOSTNAME:5432/$DB_NAME
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD
LOG_FILE=
EOF

log "systemd-служба"
sed -e "s|@APP_USER@|$APP_USER|g" -e "s|@APP_ROOT@|$APP_ROOT|g" \
    -e "s|@APP_CONFIG_DIR@|$APP_CONFIG_DIR|g" -e "s|@APP_LOG_DIR@|$APP_LOG_DIR|g" \
    "$DEPLOY_DIR/app/musicstore.service" |
    write_file /etc/systemd/system/musicstore.service 644 root:root
systemctl daemon-reload
systemctl enable musicstore

log "Firewall: порт приложения $APP_PORT"
ufw allow "$APP_PORT/tcp" comment 'Music Store app'

log "Проверка доступа к БД"
pg_isready -h "$DB_HOSTNAME" -p 5432 || die "БД $DB_HOSTNAME:5432 недоступна — сначала выполните db/setup-db.sh"

"$DEPLOY_DIR/app/deploy-release.sh" "$APP_VERSION" --seed
