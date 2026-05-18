"""WeWorkRemotely ingestor (RSS).

WWR splits roles across category-scoped RSS feeds. We pull the ones that
overlap with our target tech-tags (programming, devops/sysadmin)."""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timezone
from typing import Iterable

import feedparser

from job_ad import JobAd
from sources.common import (
    has_tech_tag,
    html_to_details,
    infer_min_experience,
    normalize_tags,
)

logger = logging.getLogger(__name__)

FEEDS = (
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
)
USER_AGENT = "career-copilot/1.0 (letsiki@gmail.com)"


def _split_company_role(title: str) -> tuple[str, str]:
    """WWR titles are usually 'Company: Role'. Split on the first ': '.
    Fallback: company = '' so the upstream check can drop the row."""
    if ": " in title:
        company, _, role = title.partition(": ")
        return company.strip(), role.strip()
    return "", title.strip()


def _parse_when(entry) -> datetime:
    pp = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if pp:
        return datetime(*pp[:6], tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc)


_TAG_FROM_TITLE_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.]{1,30}")


def _candidate_tags(role: str, category: str | None) -> list[str]:
    """WWR's RSS rarely exposes structured tags. Approximate by extracting
    words from the role title + the feed category, then let the tech-tag
    filter decide whether to keep the row."""
    tokens = _TAG_FROM_TITLE_RE.findall(role)
    if category:
        tokens.append(category)
    return normalize_tags(tokens)


def _to_job_ad(entry, feed_category: str | None) -> JobAd | None:
    raw_title = (getattr(entry, "title", "") or "").strip()
    link = (getattr(entry, "link", "") or "").strip()
    if not (raw_title and link):
        return None

    company, role = _split_company_role(raw_title)
    if not company or not role:
        return None

    tags = _candidate_tags(role, feed_category)
    if not has_tech_tag(role, tags):
        return None

    return JobAd(
        role=role[:255],
        company=company[:255],
        location="Remote",
        min_experience=infer_min_experience(role),
        employment_type="FULL_TIME",
        category="IT",
        remote="Remote",
        details=html_to_details(getattr(entry, "summary", "") or getattr(entry, "description", "")),
        tags=tags,
        ad_link=link[:255],
        date_posted=_parse_when(entry),
        report=True,
        source="wwr",
    )


def fetch() -> list[JobAd]:
    feedparser.USER_AGENT = USER_AGENT
    out: list[JobAd] = []
    seen_links: set[str] = set()
    for url in FEEDS:
        parsed = feedparser.parse(url)
        # Best-effort category label: take the slug of the feed URL.
        cat = url.rsplit("/", 1)[-1].replace(".rss", "")
        for entry in parsed.entries:
            try:
                ad = _to_job_ad(entry, cat)
            except Exception:
                logger.exception("wwr: failed to normalize an item")
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
    print(f"wwr: {len(ads)} candidates after filtering")
    if args.dry_run:
        for ad in ads[:5]:
            print(f"  - {ad.date_posted.date()} {ad.role} @ {ad.company} {ad.ad_link}")


if __name__ == "__main__":
    main()
