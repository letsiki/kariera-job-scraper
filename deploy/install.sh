#!/usr/bin/env bash
# Bootstrap the kariera-job-scraper on a fresh Ubuntu/Debian VM (designed for
# Oracle Cloud Free Tier ARM, but works on any apt-based distro). Idempotent
# enough to re-run after upstream changes — each step is conditional.
#
# Run from inside a cloned repo as a sudo-capable user:
#   sudo bash deploy/install.sh
#
# This script does NOT create the .env file. After it finishes, populate
# /opt/kariera-job-scraper/.env with POSTGRES_PASSWORD before enabling the
# timer (see deploy/README.md).

set -euo pipefail

APP_USER="kariera"
APP_HOME="/opt/kariera-job-scraper"
PG_DB="kariera_gr"
PG_USER="kariera"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "must be run with sudo / as root" >&2
    exit 1
fi

# --- Low-memory hardening (E2.1.Micro / any <2GB VM) -----------------------
# On 1GB hosts, Chromium launch can spike past available RAM. Add a 2GB swap
# file and lower vm.swappiness so we only dip into it under real pressure.
echo "==> ensuring 2GB swapfile"
if ! swapon --show | grep -q '^/swapfile'; then
    if [[ ! -f /swapfile ]]; then
        fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
        chmod 600 /swapfile
        mkswap /swapfile >/dev/null
    fi
    swapon /swapfile
fi
if ! grep -q '^/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -w vm.swappiness=10 >/dev/null
grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf

echo "==> installing apt packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    git rsync ca-certificates \
    >/dev/null

echo "==> ensuring app user '$APP_USER' exists"
if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "==> syncing repo to $APP_HOME"
mkdir -p "$APP_HOME"
rsync -a --delete \
    --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    --exclude='data' --exclude='log' --exclude='.env' \
    "$REPO_DIR/" "$APP_HOME/"
mkdir -p "$APP_HOME/data" "$APP_HOME/log" "$APP_HOME/data/filtering"
# filtering.py reads this at import time. Empty file = no location exclusions.
[ -f "$APP_HOME/data/filtering/locations.csv" ] || echo "location" > "$APP_HOME/data/filtering/locations.csv"
chown -R "$APP_USER:$APP_USER" "$APP_HOME"

echo "==> creating venv and installing python deps"
sudo -u "$APP_USER" -- bash -c "
set -e
cd '$APP_HOME'
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .
"

echo "==> installing playwright chromium (with system deps)"
sudo -u "$APP_USER" -- bash -c "
cd '$APP_HOME'
.venv/bin/playwright install chromium >/dev/null
"
# install OS-level deps for chromium (needs root)
"$APP_HOME/.venv/bin/playwright" install-deps chromium >/dev/null

echo "==> configuring postgres"
systemctl enable --now postgresql >/dev/null
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" | grep -q 1; then
    PG_PASSWORD="$(openssl rand -base64 24 | tr -d '+/=' | head -c 24)"
    sudo -u postgres psql -c "CREATE ROLE $PG_USER LOGIN PASSWORD '$PG_PASSWORD';" >/dev/null
    echo "    created postgres role '$PG_USER' with a generated password"
    echo "    >>> POSTGRES_PASSWORD=$PG_PASSWORD"
    echo "    (copy this into $APP_HOME/.env — it will not be shown again)"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1; then
    sudo -u postgres createdb --owner="$PG_USER" "$PG_DB"
fi

echo "==> tuning postgres for low-memory host"
sudo -u postgres psql -q <<'SQL'
ALTER SYSTEM SET shared_buffers = '32MB';
ALTER SYSTEM SET work_mem = '2MB';
ALTER SYSTEM SET maintenance_work_mem = '32MB';
ALTER SYSTEM SET effective_cache_size = '256MB';
ALTER SYSTEM SET max_connections = '20';
SQL
systemctl restart postgresql
# Wait for postgres to come back up before applying schema.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    sudo -u postgres pg_isready >/dev/null 2>&1 && break
    sleep 1
done

echo "==> applying schema (idempotent)"
sudo -u postgres psql -d "$PG_DB" -f "$APP_HOME/sql/kariera_gr_table_creation.sql" >/dev/null

echo "==> installing systemd unit + timer"
install -m 0644 "$APP_HOME/deploy/scraper.service" /etc/systemd/system/kariera-scraper.service
install -m 0644 "$APP_HOME/deploy/scraper.timer"   /etc/systemd/system/kariera-scraper.timer
systemctl daemon-reload
systemctl enable kariera-scraper.timer >/dev/null

echo ""
echo "===================================================================="
echo "install complete. next steps:"
echo "  1) create $APP_HOME/.env (see deploy/README.md). At minimum:"
echo "       POSTGRES_HOST=localhost"
echo "       POSTGRES_USER=$PG_USER"
echo "       POSTGRES_PASSWORD=...  # use the value printed above"
echo "       POSTGRES_DB=$PG_DB"
echo "     chown $APP_USER:$APP_USER \$_/.env && chmod 600 \$_/.env"
echo "  2) sudo systemctl start kariera-scraper.timer"
echo "  3) verify with: systemctl list-timers | grep kariera"
echo "  4) optional one-off run: sudo systemctl start kariera-scraper.service"
echo "===================================================================="
