#!/usr/bin/env bash
# Базовая подготовка сервера (выполняется на ОБОИХ серверах):
#   - имя хоста и /etc/hosts;
#   - постоянный (статический) IP-адрес через netplan;
#   - пользователь-администратор с входом только по SSH-ключу и sudo;
#   - запрет входа под root и по паролю;
#   - firewall ufw: по умолчанию всё входящее запрещено, разрешён только SSH.
#
# Использование: sudo ./common/prepare-host.sh app|db
source "$(dirname "$0")/lib.sh"
require_root
load_inventory

ROLE="${1:-}"
case "$ROLE" in
    app) HOST="$APP_HOSTNAME"; IP="$APP_IP" ;;
    db)  HOST="$DB_HOSTNAME";  IP="$DB_IP" ;;
    *)   die "Укажите роль: app или db" ;;
esac

PUBKEY_FILE="$DEPLOY_DIR/keys/admin.pub"
[[ -s $PUBKEY_FILE ]] || die "Нет публичного ключа $PUBKEY_FILE"

log "Пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ufw openssh-server curl ca-certificates
timedatectl set-timezone Europe/Moscow

log "Имя хоста: $HOST"
hostnamectl set-hostname "$HOST"
sed -i '/# musicstore-begin/,/# musicstore-end/d' /etc/hosts
cat >>/etc/hosts <<EOF
# musicstore-begin
$APP_IP $APP_HOSTNAME
$DB_IP $DB_HOSTNAME
# musicstore-end
EOF

log "Статический адрес $IP/$NET_PREFIX"
IFACE="$(ip -o -4 route show to default | awk '{print $5; exit}')"
[[ -n $IFACE ]] || die "Не найден сетевой интерфейс с маршрутом по умолчанию"
write_file /etc/netplan/60-musicstore-static.yaml 600 root:root <<EOF
network:
  version: 2
  ethernets:
    $IFACE:
      dhcp4: false
      addresses: [$IP/$NET_PREFIX]
      routes:
        - to: default
          via: $GATEWAY
      nameservers:
        addresses: [$DNS]
EOF
# cloud-init не должен перезаписывать сетевые настройки, его DHCP-конфиг убираем
write_file /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg 644 root:root <<'EOF'
network: {config: disabled}
EOF
for f in /etc/netplan/*.yaml; do
    [[ $f == /etc/netplan/60-musicstore-static.yaml ]] && continue
    grep -q 'dhcp4: *true' "$f" 2>/dev/null && mv "$f" "$f.disabled" && log "отключён $f"
done

log "Пользователь-администратор $ADMIN_USER"
if ! id "$ADMIN_USER" &>/dev/null; then
    useradd --create-home --shell /bin/bash --groups sudo "$ADMIN_USER"
fi
passwd -l "$ADMIN_USER" >/dev/null   # пароля нет — вход только по ключу
install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "/home/$ADMIN_USER/.ssh"
install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" "$PUBKEY_FILE" "/home/$ADMIN_USER/.ssh/authorized_keys"
write_file "/etc/sudoers.d/90-$ADMIN_USER" 440 root:root <<EOF
$ADMIN_USER ALL=(ALL) NOPASSWD:ALL
EOF
visudo -cf "/etc/sudoers.d/90-$ADMIN_USER" >/dev/null

log "SSH: только ключи, root запрещён"
write_file /etc/ssh/sshd_config.d/10-musicstore-hardening.conf 644 root:root <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers $ADMIN_USER
MaxAuthTries 3
X11Forwarding no
EOF
install -d -m 755 /run/sshd
sshd -t
systemctl try-reload-or-restart ssh

log "Firewall"
ufw default deny incoming
ufw default allow outgoing
ufw limit OpenSSH
ufw --force enable

log "Применение сетевых настроек (при подключении по старому адресу SSH-сессия оборвётся)"
netplan generate
netplan apply

log "Готово. Подключение: ssh $ADMIN_USER@$IP"
