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
