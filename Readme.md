# kariera-job-scraper (v2)

Daily scraper for [kariera.gr](https://www.kariera.gr) job ads. Runs unattended
on a remote VM, writes to Postgres, and produces structured exports that a
separate local repo (`career-copilot`) consumes for job-match and upskilling
analysis.

> The `main` branch contains v1 of this project: a Selenium-based local scraper
> used during a job hunt. `v2-playwright` (this branch) is a full tech-stack
> rework intended to run as a service. The product goal has expanded; see the
> _career-copilot system_ note below.

## What's new in v2

- **Playwright** instead of Selenium. Listing pages are walked by URL; each ad
  is parsed from its embedded JSON-LD `JobPosting` block, which avoids
  brittle CSS-module selectors.
- **Devcontainer**-first development. Local work happens inside a
  `python-playwright` container.
- **Structured exports** alongside the existing markdown daily report:
  - `data/daily-urls/daily-urls.md` — human-readable daily digest (unchanged
    from v1).
  - `data/exports/jobs.jsonl` — rolling 30-day window of full ad records, one
    JSON object per line.
  - `data/exports/skills.csv` — flat `(ad_link, tag)` pairs over the same
    window.
- **Explicit dependencies** in `pyproject.toml` (was an implicit conda env).
- **Configurable Postgres credentials** via env (`.env.example` documents
  them); `POSTGRES_PASSWORD` is now required.

## Architecture

The scraper is one component of a two-repo career-copilot system:

```
┌─────────────────────────────────────┐       ┌──────────────────────────────────────┐
│  REMOTE: Oracle Cloud Free Tier VM  │       │  LOCAL: career-copilot repo          │
│                                     │       │                                      │
│  kariera-job-scraper (this repo)    │       │  - profile/ (CV, skills, learning)   │
│  - daily systemd timer              │  SSH  │  - data/ (synced snapshots)          │
│  - Postgres                         │ ◄───► │  - claude commands & skills          │
│  - exports: daily-urls.md +         │ pull  │  - learning workspaces               │
│             jobs.jsonl + skills.csv │       │  - Anki integration via /anki        │
└─────────────────────────────────────┘       └──────────────────────────────────────┘
```

## Local development

### Prerequisites

- Docker + the `python-playwright` base image built from
  `~/.claude/images/python-playwright/` (`docker build -t python-playwright …`).
- VS Code with the Dev Containers extension.

### Open in container

`Ctrl+Shift+P` → **Dev Containers: Reopen in Container**. The container mounts
the workspace at `/kjs`, installs project dependencies in editable mode, and
inherits the host's `~/.claude` so Claude Code is available with shared
credentials.

### Configure

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD (and any of HOST/USER/DB you need to override)
```

### Initialise the database

```bash
psql -U postgres -d kariera_gr -f sql/kariera_gr_table_creation.sql
```

### Run

```bash
python -m main             # full run
python -m main --debug     # ~5 ads per search term, for fast iteration
```

Outputs:

- `data/daily-urls/daily-urls.md`
- `data/exports/jobs.jsonl`
- `data/exports/skills.csv`

## Deployment

The intended deployment target is an Oracle Cloud Free Tier ARM VM running
Postgres + the scraper on a daily systemd timer. See `deploy/` (added in
Phase 2 of the plan) for setup scripts.

## Layout

```
.
├── main.py             # orchestrator
├── scraper.py          # Playwright + JSON-LD parser
├── write_to_db.py      # Postgres upsert + markdown + exports
├── job_ad.py           # Pydantic JobAd model (the in-memory + on-wire shape)
├── filtering.py        # regex/category filters for the markdown report
├── logger.py
├── logging_setup.py
├── utility.py
├── sql/                # schema
├── .devcontainer/      # local-dev container
├── .env.example
└── pyproject.toml
```
