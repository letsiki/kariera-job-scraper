# Additional Job Sources — Design

**Date:** 2026-05-19
**Status:** Approved (pending user spec review)

## Problem

Current sources produce too few relevant ads for the user's situation (Athens-based, open to Europe-remote):

- **Kariera** (the only Greek-market source) updates slowly — ~1 new/day.
- **RemoteOK** and **WeWorkRemotely** are US-skewed; few realistic EU-remote roles surface.

## Goal

Add more API-based ingestors covering both axes (Greek market, Europe-remote) and loosen filtering so the downstream consumer (`career-copilot`) becomes the relevance gate.

## Scope

### New sources (all free, no-auth JSON APIs)

1. **arbeitnow** — `https://www.arbeitnow.com/api/job-board-api` — EU/Germany focused.
2. **remotive** — `https://remotive.com/api/remote-jobs` — mature remote board.
3. **jobicy** — `https://jobicy.com/api/v2/remote-jobs?count=50&geo=europe` — native EU geo filter.
4. **themuse** — `https://www.themuse.com/api/public/jobs?page=N` — broader market, paginated.
5. **workable** — per-company endpoints `https://apply.workable.com/api/v3/accounts/{slug}/jobs` for a hand-curated list of Greek companies known to post there.

### Filtering

- **Keep `has_tech_tag` gate** — cheap heuristic that keeps the DB focused on tech roles. New sources apply it the same way existing ingestors do.
- **Keep `is_us_only` gate** — US-only ads are zero-value for an Athens user.
- Anything beyond those two gates (seniority match, location preference, role match against profile) is the consumer's job.
- `infer_min_experience` and other normalization helpers stay as-is.

### Out of scope

- Skywalker.gr, jobfind.gr — no public API.
- LinkedIn, Indeed, Wellfound — no usable free API.
- Himalayas — API status uncertain; revisit if needed.
- Schema changes to `JobAd` or DB. New sources conform to the existing contract.

## Architecture

Existing pattern in `sources/`:

```
sources/
  __init__.py
  common.py        # shared helpers (filters, normalization)
  aggregator.py    # orchestrates fetch() across modules
  remoteok.py      # fetch() -> list[JobAd]
  weworkremotely.py
```

Each new source becomes one module exposing `fetch() -> list[JobAd]`, registered in `aggregator.py`. No new abstractions — the pattern is already right.

### Per-source modules

Each module follows the existing template (see `sources/remoteok.py`):

- Module-level constants: `API_URL`, `USER_AGENT`, `SOURCE_NAME`.
- `_http_get_json(url) -> ...` using `urllib.request` (consistent with current code; no new deps).
- `_parse_when(raw) -> datetime` returning a tz-aware UTC datetime.
- `_to_job_ad(raw) -> JobAd | None` doing field extraction, `is_us_only` filtering, and normalization.
- `fetch() -> list[JobAd]` driving the API call(s) and iterating items, catching per-item exceptions.
- `main(argv)` providing `--dry-run` for manual inspection, identical to `remoteok.py`.

### Workable (special case)

Unlike the other four, Workable requires a curated company-slug list. Structure:

- `sources/workable_gr.py` — module with a top-level `COMPANIES: tuple[str, ...]` of Workable account slugs for Greek companies (or companies with significant Athens engineering presence).
- **Endpoint:** `https://apply.workable.com/api/v1/widget/accounts/{slug}` — public, no auth. Returns `{name, description, jobs: [...]}` where each job has `title, shortcode, url, country, city, telecommuting, department, employment_type, published_on, created_at`. (The `/api/v3/accounts/{slug}/jobs` path commonly cited online returns 404; only `v1/widget` works.)
- **Per-job detail:** the widget listing omits `description`. For the full text, a second call to `https://apply.workable.com/api/v1/widget/accounts/{slug}/jobs/{shortcode}` is needed. Acceptable to fetch lazily per job (the list is short — only a handful of new jobs per company per run after across-run dedup).
- `fetch()` iterates `COMPANIES`, calls each endpoint, normalizes results, applies the same `has_tech_tag` + `is_us_only` filters.
- Per-company errors logged and skipped — one 404 doesn't kill the run.
- Slug list lives in code (not config) for now; trivially movable to a CSV later if it grows.

**Verified slug list** (all confirmed live via the widget API on 2026-05-19; "(N)" = open jobs at verification time, "(empty)" = valid but no current openings):

```python
COMPANIES: tuple[str, ...] = (
    # High activity
    "blueground",                # (33)
    "orfium",                    # (21)
    "learnworlds",               # (18)
    "skroutz",                   # (18)
    "upstream",                  # (15)
    "welcomepickups",            # (15) — note: "welcome-pickups" is also valid, empty
    "volton",                    # (10)
    "d-one",                     # (6)
    "careers",                   # (6) — this is Workable itself
    "epignosis",                 # (5)
    "schoox",                    # (5)
    "persado",                   # (4)
    "athens-technology-center-1",# (4)
    # Valid slug, currently no open jobs
    "beat", "taxibeat", "viva-wallet", "pollfish", "causaly",
    "intelligencia", "softomotive", "efood", "plum", "doctoranytime",
    "kaizen-gaming", "netcompany", "instashop", "bryq", "eworx",
    "profile-software", "softone", "hellas-direct", "regate", "moosend",
    "pendo", "agroknow", "atosgr", "deepsea-technologies", "cosmote",
    "kpler", "augmenta",
    # Greek office / Athens hiring but non-GR HQ — keep, downstream consumer can filter
    "wolt", "accenture-greece", "metlen", "elinoil", "mango", "freshdesk",
)
```

Slugs that 404'd during research and were **excluded**: `beat-app`, `workable`, `helvia`, `helvia-ai`. (The correct slug for Workable's own jobs is `careers`; for Beat it's `beat` or `taxibeat`.)

### Aggregator wiring

`sources/aggregator.py` adds the five new modules to whatever registration mechanism it currently uses. Each contributes its `fetch()` output to the merged list; downstream dedup + DB write logic is untouched.

### Filtering — concrete

All five new modules apply `has_tech_tag(title, tags)` and `is_us_only(location)` exactly as `remoteok.py` does today. No changes to existing ingestors or to `common.py`.

## Output contract

Every new module produces `JobAd` records identical in shape to existing ones:

- `source` field set to the source name (`"arbeitnow"`, `"remotive"`, `"jobicy"`, `"themuse"`, `"workable"`).
- `category="IT"` for arbeitnow/remotive/jobicy (these are tech-focused boards). For themuse and workable, use the API's category if available, otherwise `"IT"`.
- `remote="Remote"` for the four remote boards. For workable, derive from each job's `location` / `remote` flag if the API exposes one, else `"On-site"`.
- `report=True` (matches existing behavior).
- `details` flattened via `html_to_details` from common.py.
- `tags` normalized via `normalize_tags`.

The consumer remains source-agnostic.

## Error handling

- API timeout / non-200 → log and return `[]` for that source. One bad source doesn't break the aggregator.
- Per-item parse failure → log with `logger.exception`, skip the item (consistent with `remoteok.py`).
- Workable per-company failure → log warning, continue with remaining companies.

## Testing

- Each module has a `--dry-run` mode printing candidate count + first 5 ads (matches `remoteok.py`).
- Manual validation: run each module's `--dry-run` once during implementation; eyeball output for shape correctness and a reasonable count (>0 unless the API is down).
- No automated tests in scope (none exist for the current ingestors either).

## Risks

- **Workable slug list rot.** Companies change names / stop using Workable. Mitigation: per-company error tolerance + occasional manual review.
- **API surface changes.** Free JSON APIs can disappear / rate-limit. Mitigation: per-source error isolation; loss of one source degrades gracefully.
- **`has_tech_tag` over-filtering on themuse / workable.** themuse and workable both span non-tech roles; the tag set in `common.py` may need topping up if relevant tech roles slip through. Treat as tunable after first run.
