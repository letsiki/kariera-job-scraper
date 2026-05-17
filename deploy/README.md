# Deployment

Bootstrap and operations for running `kariera-job-scraper` on a remote VM.
Designed for Oracle Cloud Free Tier ARM (Ampere A1) running Ubuntu 22.04 LTS,
but everything is plain `apt` + `systemd` and works on any Debian-family
distro.

## One-time provisioning

### 1. Provision the VM

- Oracle Cloud → **Create instance** → shape **VM.Standard.A1.Flex** (always
  free). 2 OCPUs / 12 GB RAM is well above what we need but it costs nothing
  more.
- Image: **Canonical Ubuntu 22.04**.
- Networking: open egress (default). No inbound ports needed for the scraper
  itself — only SSH (22) for you to reach it.
- SSH in as `ubuntu`.

### 2. Clone the repo

```bash
sudo apt-get update && sudo apt-get install -y git
git clone -b v2-playwright https://github.com/letsiki/kariera-job-scraper.git
cd kariera-job-scraper
```

### 3. Run the installer

```bash
sudo bash deploy/install.sh
```

It will:
- apt-install Python, Postgres, and supporting packages.
- Create a system user `kariera` and sync the repo to `/opt/kariera-job-scraper`.
- Create a Python venv and install project deps + Chromium (with system
  libraries).
- Create a `kariera` Postgres role (with a generated password — **printed
  once, copy it**) and a `kariera_gr` database; apply the schema.
- Install the systemd service + timer (enabled but not started).

### 4. Configure secrets

```bash
sudo -u kariera tee /opt/kariera-job-scraper/.env >/dev/null <<'EOF'
POSTGRES_HOST=localhost
POSTGRES_USER=kariera
POSTGRES_PASSWORD=<paste the value the installer printed>
POSTGRES_DB=kariera_gr
EOF
sudo chmod 600 /opt/kariera-job-scraper/.env
```

### 5. Start the timer

```bash
sudo systemctl start kariera-scraper.timer
systemctl list-timers | grep kariera
```

### 6. Smoke-test a one-off run

```bash
sudo systemctl start kariera-scraper.service
sudo journalctl -u kariera-scraper.service -n 200 --no-pager
```

Artifacts (after a successful run) land in:
- `/opt/kariera-job-scraper/data/daily-urls/daily-urls.md`
- `/opt/kariera-job-scraper/data/exports/jobs.jsonl`
- `/opt/kariera-job-scraper/data/exports/skills.csv`

## Day-to-day operations

```bash
# Inspect the most recent run
sudo journalctl -u kariera-scraper.service --since today

# Tail the live timer schedule
systemctl list-timers | grep kariera

# Force an immediate run
sudo systemctl start kariera-scraper.service

# Disable temporarily (does not affect already-collected data)
sudo systemctl disable --now kariera-scraper.timer
```

## Updating the deployment

When `v2-playwright` advances:

```bash
cd ~/kariera-job-scraper && git pull
sudo bash deploy/install.sh   # rsyncs new code, re-applies schema, restarts unit
```

The installer is intentionally idempotent.

## Pulling exports to your local `career-copilot` repo

From your laptop:

```bash
rsync -av \
  ubuntu@<vm-ip>:/opt/kariera-job-scraper/data/exports/ \
  ~/career-copilot/data/
rsync -av \
  ubuntu@<vm-ip>:/opt/kariera-job-scraper/data/daily-urls/ \
  ~/career-copilot/data/
```

(The `career-copilot` repo wraps this in a `/sync` slash command — see Phase
3 of the system plan.)

## Troubleshooting

- **`systemctl start kariera-scraper.service` fails immediately**: check
  `journalctl -u kariera-scraper.service -n 100`. Most common cause is a
  missing or unreadable `.env`.
- **`POSTGRES_PASSWORD` missing**: the Python code requires it; falling back
  to a default was removed in v2 to prevent silent local/prod divergence.
- **Chromium crash on launch**: re-run `sudo /opt/kariera-job-scraper/.venv/bin/playwright install-deps chromium`.
- **Timer says "n/a" or `Inactive`**: ensure both `daemon-reload` and
  `systemctl enable --now kariera-scraper.timer` ran; the installer does both
  but a partial run can skip them.
