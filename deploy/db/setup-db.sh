#!/usr/bin/env bash
# Сервер базы данных: PostgreSQL, база, роли с минимальными правами,
# доступ по сети только с сервера приложения.
#
# Использование: sudo ./db/setup-db.sh
source "$(dirname "$0")/../common/lib.sh"
require_root
load_inventory
load_secrets DB_MIGRATOR_PASSWORD DB_APP_PASSWORD

log "Установка PostgreSQL"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q postgresql
systemctl enable --now postgresql

PG_VERSION="$(ls /etc/postgresql | sort -V | tail -n1)"
PG_CONF_DIR="/etc/postgresql/$PG_VERSION/main"

log "PostgreSQL $PG_VERSION слушает localhost и $DB_IP"
write_file "$PG_CONF_DIR/conf.d/90-musicstore.conf" 644 postgres:postgres <<EOF
listen_addresses = 'localhost,$DB_IP'
password_encryption = 'scram-sha-256'
log_connections = on
log_disconnections = on
EOF

log "pg_hba: подключения к $DB_NAME только с $APP_IP"
HBA="$PG_CONF_DIR/pg_hba.conf"
sed -i '/# musicstore-begin/,/# musicstore-end/d' "$HBA"
cat >>"$HBA" <<EOF
# musicstore-begin
host    $DB_NAME    $DB_APP_ROLE,$DB_MIGRATOR_ROLE    $APP_IP/32    scram-sha-256
# musicstore-end
EOF

systemctl restart postgresql

log "Роли и база данных"
# Пароли передаются через переменные psql (stdin), а не аргументами командной строки.
runuser -u postgres -- psql -v ON_ERROR_STOP=1 -q \
    -v db="$DB_NAME" -v migrator="$DB_MIGRATOR_ROLE" -v app="$DB_APP_ROLE" \
    -v migrator_pw="$DB_MIGRATOR_PASSWORD" -v app_pw="$DB_APP_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'migrator')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'migrator') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'app')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app') \gexec

-- никаких суперправ: не суперпользователь, не создаёт БД и роли
ALTER ROLE :"migrator" NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'migrator_pw';
ALTER ROLE :"app" NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_pw' CONNECTION LIMIT 20;

SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'migrator')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec

REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db" TO :"app";
SQL

runuser -u postgres -- psql -v ON_ERROR_STOP=1 -q -d "$DB_NAME" \
    -v migrator="$DB_MIGRATOR_ROLE" -v app="$DB_APP_ROLE" <<'SQL'
-- схема public принадлежит владельцу БД (migrator); приложение не может менять структуру
ALTER SCHEMA public OWNER TO :"migrator";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app";

-- приложение: только чтение и изменение данных (DML), без DDL
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migrator" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migrator" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO :"app";
SQL

log "Firewall: 5432 только с $APP_IP"
ufw allow from "$APP_IP" to any port 5432 proto tcp comment 'PostgreSQL from app server'

log "Готово"
ss -ltnp | grep 5432 || true
ufw status numbered
