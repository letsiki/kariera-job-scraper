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
