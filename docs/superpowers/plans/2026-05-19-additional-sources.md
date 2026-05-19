# Additional Job Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five new ingestors (arbeitnow, remotive, jobicy, themuse, workable_gr) that conform to the existing `sources/` plugin contract — `fetch() -> list[JobAd]` — and wire them into `sources/aggregator.py`.

**Architecture:** Each source is a single module under `sources/` exposing `fetch()` + a `main()` with `--dry-run`. All five reuse the existing `sources/common.py` helpers (`has_tech_tag`, `is_us_only`, `infer_min_experience`, `html_to_details`, `normalize_tags`). HTTP via `urllib.request` (no new deps). The aggregator's dedup-by-ad_link logic is untouched; new sources just become extra entries in the fetch tuple.

**Tech Stack:** Python 3.11+, urllib.request, pydantic (JobAd), BeautifulSoup (already vendored via common.py), feedparser (only for WWR — not used here).

**Spec:** `docs/superpowers/specs/2026-05-19-additional-sources-design.md`

**Testing approach:** The project has no automated test suite. Each ingestor's `--dry-run` mode is the validation path (matches `sources/remoteok.py`'s style). Each task ends with a dry-run check that prints `>0 candidates` and a sample.

---

## File Structure

- **Create** `sources/arbeitnow.py` — arbeitnow.com ingestor
- **Create** `sources/remotive.py` — remotive.com ingestor
- **Create** `sources/jobicy.py` — jobicy.com (Europe geo) ingestor
- **Create** `sources/themuse.py` — themuse.com ingestor (paginated)
- **Create** `sources/workable_gr.py` — Workable per-company widget ingestor with curated GR slug list
- **Modify** `sources/aggregator.py:17,28` — import and include the five new modules in `gather()`

Each new module is self-contained: ~80-130 lines, mirrors `sources/remoteok.py` line-for-line in structure.

---

## Task 1: arbeitnow ingestor

**API:** `GET https://www.arbeitnow.com/api/job-board-api` returns `{ "data": [ {slug, company_name, title, description, remote, url, tags, job_types, location, created_at}, ... ], "links": {...}, "meta": {...} }`. `created_at` is a Unix epoch (integer, seconds). EU-focused board, no auth.

**Files:**
- Create: `sources/arbeitnow.py`

- [ ] **Step 1: Verify API shape with curl**

Run:
```bash
curl -s 'https://www.arbeitnow.com/api/job-board-api' | python3 -c "import json,sys; d=json.load(sys.stdin); print('top:', list(d.keys())); print('count:', len(d.get('data',[]))); print('sample:', {k:d['data'][0].get(k) for k in ['slug','company_name','title','remote','url','tags','location','created_at']})"
```

Expected: prints `top: ['data', 'links', 'meta']`, a count > 0, and a sample dict.

- [ ] **Step 2: Create `sources/arbeitnow.py`**

```python
"""arbeitnow ingestor.

API: GET https://www.arbeitnow.com/api/job-board-api -> {"data":[...], ...}.
EU/Germany-focused remote board, no auth.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Iterable

from job_ad import JobAd
from sources.common import (
    has_tech_tag,
    html_to_details,
    infer_min_experience,
    is_us_only,
    normalize_tags,
)

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
USER_AGENT = "career-copilot/1.0 (letsiki@gmail.com)"


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_when(raw: dict) -> datetime:
    ts = raw.get("created_at")
    if isinstance(ts, (int, float)) and ts > 0:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


def _to_job_ad(raw: dict) -> JobAd | None:
    title = (raw.get("title") or "").strip()
    company = (raw.get("company_name") or "").strip()
    url = (raw.get("url") or "").strip()
    if not (title and company and url):
        return None

    tags = normalize_tags(raw.get("tags") or [])
    location = (raw.get("location") or "").strip() or "Remote"
    if is_us_only(location):
        return None
    if not has_tech_tag(title, tags):
        return None

    is_remote = bool(raw.get("remote"))

    return JobAd(
        role=title[:255],
        company=company[:255],
        location=location[:255],
        min_experience=infer_min_experience(title),
        employment_type="FULL_TIME",
        category="IT",
        remote="Remote" if is_remote else "On-site",
        details=html_to_details(raw.get("description")),
        tags=tags,
        ad_link=url[:255],
        date_posted=_parse_when(raw),
        report=True,
        source="arbeitnow",
    )


def fetch() -> list[JobAd]:
    try:
        payload = _http_get_json(API_URL)
    except Exception:
        logger.exception("arbeitnow: fetch failed")
        return []
    out: list[JobAd] = []
    for raw in payload.get("data") or []:
        try:
            ad = _to_job_ad(raw)
        except Exception:
            logger.exception("arbeitnow: failed to normalize an item")
            continue
        if ad is not None:
            out.append(ad)
    return out


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidate count + a sample, do not write to DB")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ads = fetch()
    print(f"arbeitnow: {len(ads)} candidates after filtering")
    if args.dry_run:
        for ad in ads[:5]:
            print(f"  - {ad.date_posted.date()} {ad.role} @ {ad.company} [{ad.location}] {ad.ad_link}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test the module**

Run: `cd /home/a_andriopoulos/kariera-job-scraper && python -m sources.arbeitnow --dry-run`
Expected: prints `arbeitnow: N candidates after filtering` with N > 0 and up to 5 sample lines. If N=0, inspect the API output (Step 1 command) and adjust field names — but the shape was verified at design time.

- [ ] **Step 4: Commit**

```bash
git add sources/arbeitnow.py
git commit -m "sources: add arbeitnow ingestor"
```

---

## Task 2: remotive ingestor

**API:** `GET https://remotive.com/api/remote-jobs` returns `{"0-legal-notice": "...", "job-count": N, "jobs": [...]}`. Each job has `id, url, title, company_name, category, tags, job_type, publication_date, candidate_required_location, salary, description`. Dates are ISO-8601 strings.

**Files:**
- Create: `sources/remotive.py`

- [ ] **Step 1: Verify API shape**

Run:
```bash
curl -s 'https://remotive.com/api/remote-jobs' | python3 -c "import json,sys; d=json.load(sys.stdin); print('keys:', list(d.keys())); j=d['jobs'][0]; print('sample:', {k:j.get(k) for k in ['id','title','company_name','category','tags','candidate_required_location','publication_date','url']})"
```

Expected: keys include `jobs`, count > 0, sample shows the listed fields populated.

- [ ] **Step 2: Create `sources/remotive.py`**

```python
"""remotive ingestor.

API: GET https://remotive.com/api/remote-jobs -> {"jobs":[...], ...}.
General remote board, no auth.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Iterable

from job_ad import JobAd
from sources.common import (
    has_tech_tag,
    html_to_details,
    infer_min_experience,
    is_us_only,
    normalize_tags,
)

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"
USER_AGENT = "career-copilot/1.0 (letsiki@gmail.com)"


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_when(raw: dict) -> datetime:
    s = raw.get("publication_date")
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def _to_job_ad(raw: dict) -> JobAd | None:
    title = (raw.get("title") or "").strip()
    company = (raw.get("company_name") or "").strip()
    url = (raw.get("url") or "").strip()
    if not (title and company and url):
        return None

    tags = normalize_tags(raw.get("tags") or [])
    category = (raw.get("category") or "").strip()
    if category:
        tags = normalize_tags([*tags, category])

    location = (raw.get("candidate_required_location") or "").strip() or "Remote"
    if is_us_only(location):
        return None
    if not has_tech_tag(title, tags):
        return None

    return JobAd(
        role=title[:255],
        company=company[:255],
        location=location[:255],
        min_experience=infer_min_experience(title),
        employment_type="FULL_TIME",
        category="IT",
        remote="Remote",
        details=html_to_details(raw.get("description")),
        tags=tags,
        ad_link=url[:255],
        date_posted=_parse_when(raw),
        report=True,
        source="remotive",
    )


def fetch() -> list[JobAd]:
    try:
        payload = _http_get_json(API_URL)
    except Exception:
        logger.exception("remotive: fetch failed")
        return []
    out: list[JobAd] = []
    for raw in payload.get("jobs") or []:
        try:
            ad = _to_job_ad(raw)
        except Exception:
            logger.exception("remotive: failed to normalize an item")
            continue
        if ad is not None:
            out.append(ad)
    return out


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidate count + a sample, do not write to DB")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ads = fetch()
    print(f"remotive: {len(ads)} candidates after filtering")
    if args.dry_run:
        for ad in ads[:5]:
            print(f"  - {ad.date_posted.date()} {ad.role} @ {ad.company} [{ad.location}] {ad.ad_link}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test**

Run: `cd /home/a_andriopoulos/kariera-job-scraper && python -m sources.remotive --dry-run`
Expected: `remotive: N candidates after filtering` with N > 0.

- [ ] **Step 4: Commit**

```bash
git add sources/remotive.py
git commit -m "sources: add remotive ingestor"
```

---

## Task 3: jobicy ingestor

**API:** `GET https://jobicy.com/api/v2/remote-jobs?count=50&geo=europe` returns `{"apiVersion":..., "documentation":..., "jobCount": N, "jobs": [...]}`. Each job has `id, url, jobSlug, jobTitle, companyName, companyLogo, jobIndustry (list), jobType (list), jobGeo, jobLevel, jobExcerpt, jobDescription, pubDate (ISO string), annualSalaryMin, annualSalaryMax, salaryCurrency`.

**Files:**
- Create: `sources/jobicy.py`

- [ ] **Step 1: Verify API shape**

Run:
```bash
curl -s 'https://jobicy.com/api/v2/remote-jobs?count=50&geo=europe' | python3 -c "import json,sys; d=json.load(sys.stdin); print('keys:', list(d.keys())); j=d['jobs'][0]; print('sample:', {k:j.get(k) for k in ['id','jobTitle','companyName','jobIndustry','jobType','jobGeo','jobLevel','pubDate','url']})"
```

Expected: `keys` includes `jobs`, count > 0, sample populated.

- [ ] **Step 2: Create `sources/jobicy.py`**

```python
"""jobicy ingestor.

API: GET https://jobicy.com/api/v2/remote-jobs?count=50&geo=europe
-> {"jobs":[...], ...}. Europe-filtered remote board, no auth.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Iterable

from job_ad import JobAd
from sources.common import (
    has_tech_tag,
    html_to_details,
    infer_min_experience,
    is_us_only,
    normalize_tags,
)

logger = logging.getLogger(__name__)

API_URL = "https://jobicy.com/api/v2/remote-jobs?count=50&geo=europe"
USER_AGENT = "career-copilot/1.0 (letsiki@gmail.com)"


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_when(raw: dict) -> datetime:
    s = raw.get("pubDate")
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def _to_job_ad(raw: dict) -> JobAd | None:
    title = (raw.get("jobTitle") or "").strip()
    company = (raw.get("companyName") or "").strip()
    url = (raw.get("url") or "").strip()
    if not (title and company and url):
        return None

    industries = raw.get("jobIndustry") or []
    types = raw.get("jobType") or []
    tags = normalize_tags([*industries, *types])

    location = (raw.get("jobGeo") or "").strip() or "Remote"
    if is_us_only(location):
        return None
    if not has_tech_tag(title, tags):
        return None

    level_map = {"junior": "Junior", "senior": "Senior", "lead": "Lead",
                 "principal": "Principal", "staff": "Staff"}
    level = (raw.get("jobLevel") or "").strip().lower()
    min_exp = level_map.get(level, infer_min_experience(title))

    return JobAd(
        role=title[:255],
        company=company[:255],
        location=location[:255],
        min_experience=min_exp,
        employment_type="FULL_TIME",
        category="IT",
        remote="Remote",
        details=html_to_details(raw.get("jobDescription") or raw.get("jobExcerpt")),
        tags=tags,
        ad_link=url[:255],
        date_posted=_parse_when(raw),
        report=True,
        source="jobicy",
    )


def fetch() -> list[JobAd]:
    try:
        payload = _http_get_json(API_URL)
    except Exception:
        logger.exception("jobicy: fetch failed")
        return []
    out: list[JobAd] = []
    for raw in payload.get("jobs") or []:
        try:
            ad = _to_job_ad(raw)
        except Exception:
            logger.exception("jobicy: failed to normalize an item")
            continue
        if ad is not None:
            out.append(ad)
    return out


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidate count + a sample, do not write to DB")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ads = fetch()
    print(f"jobicy: {len(ads)} candidates after filtering")
    if args.dry_run:
        for ad in ads[:5]:
            print(f"  - {ad.date_posted.date()} {ad.role} @ {ad.company} [{ad.location}] {ad.ad_link}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test**

Run: `cd /home/a_andriopoulos/kariera-job-scraper && python -m sources.jobicy --dry-run`
Expected: `jobicy: N candidates after filtering` with N > 0.

- [ ] **Step 4: Commit**

```bash
git add sources/jobicy.py
git commit -m "sources: add jobicy (Europe-geo) ingestor"
```

---

## Task 4: themuse ingestor

**API:** `GET https://www.themuse.com/api/public/jobs?page=N&category=Engineering&category=Data%20Science` returns `{"page": N, "page_count": M, "results": [...]}`. Each result has `id, name (role title), company: {name}, categories: [{name}], levels: [{name}], locations: [{name}], publication_date (ISO), refs: {landing_page}, contents (HTML), tags`. Paginated — fetch up to 5 pages (`page=0..4`) to stay polite. The API uses `page=0` as the first page.

**Files:**
- Create: `sources/themuse.py`

- [ ] **Step 1: Verify API shape**

Run:
```bash
curl -s 'https://www.themuse.com/api/public/jobs?page=0&category=Engineering' | python3 -c "import json,sys; d=json.load(sys.stdin); print('keys:', list(d.keys())); print('page_count:', d.get('page_count')); j=d['results'][0]; print('sample:', {'name':j.get('name'),'company':j.get('company',{}).get('name'),'levels':[l['name'] for l in j.get('levels',[])],'locations':[l['name'] for l in j.get('locations',[])],'landing_page':j.get('refs',{}).get('landing_page'),'publication_date':j.get('publication_date')})"
```

Expected: `keys` includes `results`, sample populated. If `page_count` is reported, note it.

- [ ] **Step 2: Create `sources/themuse.py`**

```python
"""themuse ingestor.

API: GET https://www.themuse.com/api/public/jobs?page=N&category=...
Paginated; fetch up to MAX_PAGES tech-relevant pages, no auth.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Iterable

from job_ad import JobAd
from sources.common import (
    has_tech_tag,
    html_to_details,
    infer_min_experience,
    is_us_only,
    normalize_tags,
)

logger = logging.getLogger(__name__)

BASE = "https://www.themuse.com/api/public/jobs"
CATEGORIES = ("Engineering", "Data Science", "Software Engineer", "IT")
MAX_PAGES = 5
USER_AGENT = "career-copilot/1.0 (letsiki@gmail.com)"


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_when(raw: dict) -> datetime:
    s = raw.get("publication_date")
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def _to_job_ad(raw: dict) -> JobAd | None:
    title = (raw.get("name") or "").strip()
    company = ((raw.get("company") or {}).get("name") or "").strip()
    url = ((raw.get("refs") or {}).get("landing_page") or "").strip()
    if not (title and company and url):
        return None

    categories = [c.get("name", "") for c in (raw.get("categories") or [])]
    levels = [l.get("name", "") for l in (raw.get("levels") or [])]
    tags = normalize_tags([*categories, *(raw.get("tags") or [])])

    locations = [l.get("name", "") for l in (raw.get("locations") or [])]
    location = ", ".join(loc for loc in locations if loc) or "Remote"
    if is_us_only(location):
        return None
    if not has_tech_tag(title, tags):
        return None

    level = levels[0].lower() if levels else ""
    level_map = {"entry level": "Junior", "mid level": "N/A",
                 "senior level": "Senior", "internship": "Intern"}
    min_exp = level_map.get(level, infer_min_experience(title))

    is_remote = "remote" in location.lower() or any("flexible" in l.lower() for l in locations)

    return JobAd(
        role=title[:255],
        company=company[:255],
        location=location[:255],
        min_experience=min_exp,
        employment_type="FULL_TIME",
        category="IT",
        remote="Remote" if is_remote else "On-site",
        details=html_to_details(raw.get("contents")),
        tags=tags,
        ad_link=url[:255],
        date_posted=_parse_when(raw),
        report=True,
        source="themuse",
    )


def fetch() -> list[JobAd]:
    out: list[JobAd] = []
    seen_links: set[str] = set()
    for page in range(MAX_PAGES):
        qs = urllib.parse.urlencode(
            [("page", str(page))] + [("category", c) for c in CATEGORIES]
        )
        url = f"{BASE}?{qs}"
        try:
            payload = _http_get_json(url)
        except Exception:
            logger.exception("themuse: fetch failed for page %s", page)
            continue
        results = payload.get("results") or []
        if not results:
            break
        for raw in results:
            try:
                ad = _to_job_ad(raw)
            except Exception:
                logger.exception("themuse: failed to normalize an item")
                continue
            if ad is None or ad.ad_link in seen_links:
                continue
            seen_links.add(ad.ad_link)
            out.append(ad)
    return out


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidate count + a sample, do not write to DB")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ads = fetch()
    print(f"themuse: {len(ads)} candidates after filtering")
    if args.dry_run:
        for ad in ads[:5]:
            print(f"  - {ad.date_posted.date()} {ad.role} @ {ad.company} [{ad.location}] {ad.ad_link}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test**

Run: `cd /home/a_andriopoulos/kariera-job-scraper && python -m sources.themuse --dry-run`
Expected: `themuse: N candidates after filtering` with N > 0 (it's a US-heavy board, so a chunk gets filtered out by `is_us_only` — but enough remote/global roles remain).

- [ ] **Step 4: Commit**

```bash
git add sources/themuse.py
git commit -m "sources: add themuse (paginated) ingestor"
```

---

## Task 5: workable_gr ingestor

**API:** Two calls per company:
1. List: `GET https://apply.workable.com/api/v1/widget/accounts/{slug}` → `{name, description, jobs: [{title, shortcode, url, country, city, telecommuting, department, employment_type, published_on (ISO), created_at (ISO), ...}]}`. **No description in listing.**
2. Detail: `GET https://apply.workable.com/api/v1/widget/accounts/{slug}/jobs/{shortcode}` → `{title, description (HTML), requirements (HTML), benefits (HTML), ...}`. **Only call this for jobs we don't already have.**

The detail call is per-job and expensive; the aggregator's across-run dedup (commit `1046370`) means we can safely skip the detail call entirely on this first iteration and ship with the description left empty — kariera ads also sometimes have thin descriptions, and the consumer can backfill later if needed.

**Decision:** ship without detail-call enrichment for now. The `details` field will be `[]` for workable_gr jobs. This keeps the module simple and avoids hitting the API 50× per run. Mark this as a known limitation; revisit if the consumer needs the description text.

**Files:**
- Create: `sources/workable_gr.py`

- [ ] **Step 1: Verify the widget endpoint with one slug**

Run:
```bash
curl -s 'https://apply.workable.com/api/v1/widget/accounts/blueground' | python3 -c "import json,sys; d=json.load(sys.stdin); print('name:', d.get('name')); print('jobs:', len(d.get('jobs',[]))); j=d['jobs'][0]; print('sample:', {k:j.get(k) for k in ['title','shortcode','url','country','city','telecommuting','department','employment_type','published_on','created_at']})"
```

Expected: prints `name: Blueground`, jobs count > 0, sample populated.

- [ ] **Step 2: Create `sources/workable_gr.py`**

```python
"""Workable per-company widget ingestor (Greek companies).

API: GET https://apply.workable.com/api/v1/widget/accounts/{slug}
returns {"name": ..., "jobs": [...]}. Each job has title, shortcode,
url, country, city, telecommuting, department, employment_type,
published_on, created_at — but no description in the listing.

We intentionally do NOT call the per-job detail endpoint; the description
backfill can happen later if the consumer asks for it. The listing has
enough signal for tag-matching and dedup.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Iterable

from job_ad import JobAd
from sources.common import (
    has_tech_tag,
    infer_min_experience,
    is_us_only,
    normalize_tags,
)

logger = logging.getLogger(__name__)

WIDGET_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"
USER_AGENT = "career-copilot/1.0 (letsiki@gmail.com)"

# Verified live on 2026-05-19. See
# docs/superpowers/specs/2026-05-19-additional-sources-design.md for
# how this list was assembled.
COMPANIES: tuple[str, ...] = (
    # High activity
    "blueground", "orfium", "learnworlds", "skroutz", "upstream",
    "welcomepickups", "volton", "d-one", "careers", "epignosis",
    "schoox", "persado", "athens-technology-center-1",
    # Valid slug, currently no open jobs (still polled — they post regularly)
    "beat", "taxibeat", "viva-wallet", "pollfish", "causaly",
    "intelligencia", "softomotive", "efood", "plum", "doctoranytime",
    "kaizen-gaming", "netcompany", "instashop", "bryq", "eworx",
    "profile-software", "softone", "hellas-direct", "regate", "moosend",
    "pendo", "agroknow", "atosgr", "deepsea-technologies", "cosmote",
    "kpler", "augmenta",
    # Greek office / Athens hiring but non-GR HQ
    "wolt", "accenture-greece", "metlen", "elinoil", "mango", "freshdesk",
)


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_when(raw: dict) -> datetime:
    for key in ("published_on", "created_at"):
        s = raw.get(key)
        if isinstance(s, str):
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                continue
    return datetime.now(tz=timezone.utc)


def _format_location(raw: dict) -> str:
    parts = [raw.get("city"), raw.get("state"), raw.get("country")]
    loc = ", ".join(p for p in parts if p)
    if not loc:
        return "Remote" if raw.get("telecommuting") else ""
    if raw.get("telecommuting"):
        loc = f"{loc} (Remote)"
    return loc


def _to_job_ad(raw: dict, company_name: str) -> JobAd | None:
    title = (raw.get("title") or "").strip()
    shortcode = (raw.get("shortcode") or "").strip()
    url = (raw.get("url") or raw.get("shortlink") or "").strip()
    if not (title and company_name and url):
        return None

    department = (raw.get("department") or "").strip()
    function = (raw.get("function") or "").strip()
    tags = normalize_tags([t for t in (department, function) if t])

    location = _format_location(raw) or "Remote"
    if is_us_only(location):
        return None
    if not has_tech_tag(title, tags):
        return None

    employment_type = (raw.get("employment_type") or "").upper().replace("-", "_") or "FULL_TIME"

    return JobAd(
        role=title[:255],
        company=company_name[:255],
        location=location[:255],
        min_experience=infer_min_experience(title),
        employment_type=employment_type,
        category="IT",
        remote="Remote" if raw.get("telecommuting") else "On-site",
        details=[],  # widget listing has no description; backfill later if needed
        tags=tags,
        ad_link=url[:255],
        date_posted=_parse_when(raw),
        report=True,
        source="workable",
    )


def _fetch_company(slug: str) -> list[JobAd]:
    try:
        payload = _http_get_json(WIDGET_URL.format(slug=slug))
    except Exception:
        logger.warning("workable_gr: fetch failed for %s", slug, exc_info=True)
        return []
    company_name = (payload.get("name") or slug).strip()
    out: list[JobAd] = []
    for raw in payload.get("jobs") or []:
        try:
            ad = _to_job_ad(raw, company_name)
        except Exception:
            logger.exception("workable_gr: failed to normalize a job for %s", slug)
            continue
        if ad is not None:
            out.append(ad)
    return out


def fetch() -> list[JobAd]:
    out: list[JobAd] = []
    for slug in COMPANIES:
        out.extend(_fetch_company(slug))
    return out


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidate count + a sample, do not write to DB")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ads = fetch()
    print(f"workable_gr: {len(ads)} candidates after filtering")
    if args.dry_run:
        for ad in ads[:5]:
            print(f"  - {ad.date_posted.date()} {ad.role} @ {ad.company} [{ad.location}] {ad.ad_link}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test**

Run: `cd /home/a_andriopoulos/kariera-job-scraper && python -m sources.workable_gr --dry-run`
Expected: `workable_gr: N candidates after filtering` with N somewhere between 20 and 80 (the active companies in the list had ~140 total jobs at design time; `has_tech_tag` cuts non-engineering roles).

- [ ] **Step 4: Commit**

```bash
git add sources/workable_gr.py
git commit -m "sources: add workable_gr ingestor with curated Greek-company slug list"
```

---

## Task 6: Wire new sources into the aggregator

**Files:**
- Modify: `sources/aggregator.py` (imports at line 17, fetch tuple at line 28)

- [ ] **Step 1: Update imports and `gather()`**

Edit `sources/aggregator.py`:

Replace:
```python
from sources import remoteok, weworkremotely
```
with:
```python
from sources import arbeitnow, jobicy, remoteok, remotive, themuse, weworkremotely, workable_gr
```

Replace the `for src in (...)` tuple inside `gather()`:
```python
    for src in (remoteok.fetch(), weworkremotely.fetch()):
```
with:
```python
    for src in (
        remoteok.fetch(),
        weworkremotely.fetch(),
        arbeitnow.fetch(),
        remotive.fetch(),
        jobicy.fetch(),
        themuse.fetch(),
        workable_gr.fetch(),
    ):
```

- [ ] **Step 2: Smoke-test the aggregator**

Run: `cd /home/a_andriopoulos/kariera-job-scraper && python -m sources.aggregator --dry-run`
Expected: log line like `aggregator: N candidates after dedup ({'remoteok': X, 'wwr': X, 'arbeitnow': X, 'remotive': X, 'jobicy': X, 'themuse': X, 'workable': X})` with all seven keys present and counts > 0 (except workable which may be a smaller number).

If any source returned 0, re-run that module's individual `--dry-run` and inspect.

- [ ] **Step 3: Commit**

```bash
git add sources/aggregator.py
git commit -m "aggregator: wire in arbeitnow, remotive, jobicy, themuse, workable_gr"
```

---

## Done

After all six tasks, the v2-playwright branch has five new ingestors plus aggregator wiring. The next scheduled run on the VM (`kariera-scraper.service` timer) will pick them up automatically — no deployment change needed beyond a `git pull` since none of these add new dependencies.

Optional follow-ups (not in scope):
- Backfill workable_gr job descriptions via per-shortcode detail calls (skipped per design above).
- Add Skywalker.gr / jobfind.gr if they ever expose a JSON API or someone writes a Playwright scraper for them.
- Add a per-source ad-count alert if any source drops to 0 for N consecutive runs (signals API churn).
