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
