# Развёртывание в Linux-среде (без контейнеров)

Две виртуальные машины в VMware Workstation, сеть NAT (VMnet8, `192.168.42.0/24`):

```
 Клиент (Windows-хост)                ms-app 192.168.42.10              ms-db 192.168.42.20
 браузер ── tcp/8000 ──────────────▶ ufw: 22, 8000                ┌─▶ ufw: 22, 5432 только от .10
                                      systemd: musicstore.service  │   PostgreSQL 16
 ssh (ключ) ── tcp/22 ─────────────▶ user musicstore (не root) ──┘   роли: musicstore_migrator (DDL),
                                      /etc/musicstore/app.env           musicstore_app (только DML)
```

| Файл | Назначение |
|---|---|
| `inventory.env` | адреса, имена, пользователи, версия (не секретно, в репозитории) |
| `secrets.env.example` → `secrets.env` | пароли БД, `SECRET_KEY`, пароль администратора приложения (**не в репозитории**) |
| `new-secrets.ps1` | генерирует `secrets.env` и копирует публичный SSH-ключ в `keys/admin.pub` |
| `common/prepare-host.sh` | оба сервера: имя хоста, статический IP, пользователь `sysadmin`, SSH только по ключу, запрет root, ufw |
| `db/setup-db.sh` | сервер БД: PostgreSQL, база, роли с минимальными правами, `pg_hba`, firewall |
| `app/setup-app.sh` | сервер приложения: Python, пользователь `musicstore`, каталоги и права, настройки, systemd, firewall, первый выпуск |
| `app/deploy-release.sh` | выпуск (или откат) версии по тегу: код → venv → миграции → переключение → перезапуск → `/health` |
| `app/musicstore.service` | шаблон systemd-службы |
| `check.sh` | диагностика: адреса, SSH, firewall, порты, служба, права, журналы, БД |

Все скрипты можно запускать повторно: они приводят систему к нужному состоянию и ничего не ломают.

## 1. Виртуальные машины

1. Скачать образ **Ubuntu Server 24.04 LTS** (ubuntu.com/download/server).
2. VMware Workstation → *Create a New Virtual Machine* → Typical → образ ISO → Linux / Ubuntu 64-bit.
   Имена `ms-app` и `ms-db`; 2 ГБ RAM, 2 CPU, диск 20 ГБ; *Network adapter: NAT*.
3. Установка Ubuntu (на обеих машинах):
   - *Network*: интерфейс `ens33` → *Edit IPv4* → **Manual**: subnet `192.168.42.0/24`,
     address `192.168.42.10` (для ms-db — `192.168.42.20`), gateway `192.168.42.2`,
     name servers `192.168.42.2`;
   - *Profile*: имя сервера `ms-app` / `ms-db`, пользователь `student` (временный, для первичной настройки);
   - **Install OpenSSH server** — отметить; остальное не ставить.
4. После перезагрузки проверить с Windows: `ping 192.168.42.10`, `ping 192.168.42.20`.

> Если адрес при установке не задан, его выставит `prepare-host.sh`. SSH-сессия при этом
> оборвётся, и подключаться нужно будет уже по новому адресу.

## 2. Секреты и ключ (на Windows, в корне репозитория)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\new-secrets.ps1
```
Создаются `deploy\secrets.env` (случайные пароли) и `deploy\keys\admin.pub`. Оба файла в
`.gitignore`. Пароль администратора приложения — `ADMIN_PASSWORD` в `secrets.env`.

## 3. Копирование скриптов на серверы

```powershell
scp -r deploy student@192.168.42.20:~/
scp -r deploy student@192.168.42.10:~/
```

## 4. Сервер БД (ms-db)

```bash
ssh student@192.168.42.20
sudo bash ~/deploy/common/prepare-host.sh db     # после этого вход только: ssh sysadmin@192.168.42.20
exit
ssh sysadmin@192.168.42.20
sudo cp -r /home/student/deploy ~ && sudo chown -R sysadmin: ~/deploy
sudo bash ~/deploy/db/setup-db.sh
```

## 5. Сервер приложения (ms-app)

```bash
ssh student@192.168.42.10
sudo bash ~/deploy/common/prepare-host.sh app
exit
ssh sysadmin@192.168.42.10
sudo cp -r /home/student/deploy ~ && sudo chown -R sysadmin: ~/deploy
sudo bash ~/deploy/app/setup-app.sh                # в конце печатает {"status":"ok",...}
```

Приложение: **http://192.168.42.10:8000** (вход: `admin` / `ADMIN_PASSWORD` из `secrets.env`).

После настройки временного пользователя можно удалить: `sudo deluser --remove-home student`.
Файл `secrets.env` на серверах больше не нужен: `rm ~/deploy/secrets.env`. Рабочие настройки
лежат в `/etc/musicstore/*.env`.

## 6. Обновление и откат

```bash
sudo bash ~/deploy/app/deploy-release.sh v0.2.1   # новая версия (тег в GitHub)
sudo bash ~/deploy/app/deploy-release.sh v0.2.0   # вернуть предыдущую (код уже лежит в releases/)
```

## Где что лежит (ms-app)

| Путь | Владелец / права | Содержимое |
|---|---|---|
| `/opt/musicstore/releases/<версия>/` | `root:root`, `755`/`644` | код и `.venv`; служба только читает |
| `/opt/musicstore/current` | ссылка | текущий выпуск |
| `/etc/musicstore/app.env` | `root:musicstore`, `640` | настройки приложения (роль `musicstore_app`) |
| `/etc/musicstore/migrate.env` | `root:root`, `600` | доступ роли-владельца схемы для миграций |
| `/var/log/musicstore/app.log` | `musicstore:musicstore`, `750` | журнал приложения (+ `journalctl -u musicstore`) |
| `/etc/systemd/system/musicstore.service` | `root`, `644` | служба |

## Эксплуатационные требования

1. **Приложение не запускается от root.** Служба работает от системного пользователя
   `musicstore` без shell и без пароля (`User=` в unit-файле). Для неё включены `NoNewPrivileges`,
   `ProtectSystem=strict` и пустой `CapabilityBoundingSet`. Писать служба может только в `/var/log/musicstore`.
2. **Лишние порты не открываются.** ufw по умолчанию запрещает весь входящий трафик. На ms-app
   открыты только 22 и 8000, на ms-db — 22 и 5432, причём 5432 только с `192.168.42.10`.
   PostgreSQL дополнительно ограничен `pg_hba.conf`: доступ только к базе `musicstore`, только
   нашим ролям и только с адреса сервера приложения.
3. **Пароли не хранятся в репозитории.** Секреты есть только в `secrets.env` (в `.gitignore`)
   и в `/etc/musicstore/*.env` на сервере, с правами `640`/`600`. В репозитории лежат только шаблоны.
4. **Удалённый вход под root запрещён, вход по паролю запрещён.** Входить можно только
   пользователю `sysadmin` и только по ключу (`PermitRootLogin no`, `PasswordAuthentication no`,
   `AllowUsers`).
5. **Минимальные права в БД.** Приложение подключается ролью `musicstore_app`: только
   `SELECT/INSERT/UPDATE/DELETE`, без права менять схему. Схемой владеет `musicstore_migrator`,
   и эта роль используется только при миграциях.
6. **Настройки отдельно от кода.** Код берётся из Git по тегу, а настройки лежат в `/etc/musicstore`.
   Переустановка кода настройки не затрагивает.

## Проверки на защите

```bash
sudo bash ~/deploy/check.sh                    # общее состояние сервера
```

**Перезагрузка и автозапуск**
```bash
sudo reboot                                    # на обеих машинах
systemctl is-enabled musicstore postgresql     # enabled
curl -s http://192.168.42.10:8000/health
```

**Остановка БД и диагностика приложения**
```bash
# ms-db
sudo systemctl stop postgresql
# ms-app
curl -i http://127.0.0.1:8000/health           # 503 {"status":"error","database":"unavailable"}
systemctl status musicstore                    # служба жива, active (running)
journalctl -u musicstore -n 20                 # health_check_failed ... connection refused
pg_isready -h ms-db                            # no response
# ms-db
sudo systemctl start postgresql                # /health снова 200
```

**Процесс, порт, журналы**
```bash
systemctl status musicstore
pgrep -a -u musicstore                         # процесс uvicorn от пользователя musicstore
ps -o user,pid,etime,cmd -p $(systemctl show -p MainPID --value musicstore)
sudo ss -ltnp | grep 8000                      # кто слушает порт
journalctl -u musicstore -f                    # журнал службы
sudo tail -f /var/log/musicstore/app.log       # журнал приложения
```

**Перезапуск после сбоя**
```bash
sudo kill -9 $(systemctl show -p MainPID --value musicstore)
sleep 4; systemctl status musicstore           # снова active, NRestarts увеличился
systemctl show musicstore -p NRestarts
```

**Изменение параметра службы и восстановление**
```bash
sudo systemctl edit musicstore                 # в редакторе добавить (override.conf):
#   [Service]
#   ExecStart=
#   ExecStart=/opt/musicstore/current/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8081
sudo systemctl restart musicstore
systemctl cat musicstore                       # видно исходный unit и override
sudo ss -ltnp | grep 8081                      # теперь 8081 (снаружи закрыт ufw — это ожидаемо)
sudo systemctl revert musicstore               # убрать override
sudo systemctl restart musicstore              # снова 8000
```

**Недоступность БД с постороннего узла** (с Windows-хоста)
```powershell
Test-NetConnection 192.168.42.20 -Port 5432    # TcpTestSucceeded : False (ufw)
Test-NetConnection 192.168.42.10 -Port 8000    # True
```
С самого ms-app подключение есть: `pg_isready -h ms-db` → `accepting connections`.

**SSH под root и по паролю запрещены**
```powershell
ssh root@192.168.42.10                         # Permission denied (publickey)
ssh -o PubkeyAuthentication=no sysadmin@192.168.42.10   # Permission denied (publickey)
```
