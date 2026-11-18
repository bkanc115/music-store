#!/usr/bin/env bash
# Диагностика стенда. Запуск на сервере приложения или БД: sudo ./check.sh
source "$(dirname "$0")/common/lib.sh"
load_inventory

section() { printf '\n\033[1;34m### %s\033[0m\n' "$*"; }

section "Хост"
hostnamectl --static; ip -4 -brief addr show scope global

section "SSH"
sshd -T 2>/dev/null | grep -Ei '^(permitrootlogin|passwordauthentication|allowusers) ' || true

section "Firewall"
ufw status verbose

section "Слушающие порты"
ss -ltnp

if systemctl list-unit-files musicstore.service &>/dev/null; then
    section "Служба musicstore"
    systemctl is-enabled musicstore; systemctl is-active musicstore || true
    systemctl show musicstore -p MainPID -p User -p NRestarts -p ActiveEnterTimestamp
    PID="$(systemctl show musicstore -p MainPID --value)"
    [[ $PID != 0 ]] && ps -o user,pid,etime,cmd -p "$PID"

    section "Проверка /health"
    curl -sS -w '\nHTTP %{http_code}\n' "http://127.0.0.1:$APP_PORT/health" || true

    section "Доступность БД $DB_HOSTNAME:5432"
    pg_isready -h "$DB_HOSTNAME" -p 5432 || true

    section "Права"
    ls -ld "$APP_ROOT" "$APP_ROOT/current" "$APP_CONFIG_DIR" "$APP_LOG_DIR"
    ls -l "$APP_CONFIG_DIR"

    section "Последние записи журнала"
    journalctl -u musicstore -n 15 --no-pager
    tail -n 5 "$APP_LOG_DIR/app.log" 2>/dev/null || true
fi

if systemctl list-unit-files postgresql.service &>/dev/null; then
    section "PostgreSQL"
    systemctl is-active postgresql || true
    runuser -u postgres -- psql -Atc "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname LIKE 'musicstore%'" 2>/dev/null || true
    grep -A3 'musicstore-begin' /etc/postgresql/*/main/pg_hba.conf || true
fi
