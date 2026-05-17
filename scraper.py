import json
import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from time import perf_counter
from typing import Set
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)
from pydantic import ValidationError

from job_ad import JobAd
from logging_setup import logging_setup

logger = logging.Logger(__name__)
date = datetime.strftime(datetime.now(), "%Y-%m-%d")
logging_setup(
    logger,
    mode="fc",
    filename=f"log/{date}.log",
    filemode="w",
)

BASE_URL = "https://www.kariera.gr"
SEARCH_TERMS = ("Data", "Python", "IT", "Software", "Developer")
SEL_COOKIE_ACCEPT = "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
DEFAULT_TIMEOUT_MS = 45_000

# Matches absolute or relative hrefs of form /en/jobs/<slug>/<numeric-id>
AD_LINK_RE = re.compile(r"^/en/jobs/[^/?]+/\d+(?:[/?#].*)?$")


class _BlockTextExtractor(HTMLParser):
    """Pulls text from <p>, <li>, <strong>, <br>-separated lines. Used to convert
    JSON-LD description HTML into the list-of-strings `JobAd.details` expects."""

    BLOCK_TAGS = {"p", "li", "strong", "h1", "h2", "h3", "h4", "h5", "h6", "div"}

    def __init__(self) -> None:
        super().__init__()
        self._buf: list[str] = []
        self._out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        self._buf.append(data)

    def _flush(self):
        text = "".join(self._buf).strip()
        if text:
            self._out.append(text)
        self._buf.clear()

    def close(self):
        super().close()
        self._flush()

    @property
    def lines(self) -> list[str]:
        return self._out


def _html_to_lines(html: str) -> list[str]:
    if not html:
        return []
    parser = _BlockTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.lines


def _accept_cookies(page: Page) -> None:
    try:
        page.click(SEL_COOKIE_ACCEPT, timeout=5_000)
        logger.info("accepted cookie banner")
    except PlaywrightTimeoutError:
        logger.info("no cookie banner")


def _collect_ad_links_on_listing(page: Page) -> list[str]:
    """Return absolute URLs to job-ad detail pages on the current listing page."""
    raw = page.eval_on_selector_all(
        "a[href]",
        "els => Array.from(new Set(els.map(e => e.getAttribute('href')).filter(Boolean)))",
    )
    out: list[str] = []
    seen: set[str] = set()
    for href in raw:
        if not AD_LINK_RE.match(href):
            continue
        url = urljoin(BASE_URL, href.split("?")[0])
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _scroll_to_load_more(
    page: Page, max_scrolls: int = 8, max_ad_links: int = 50
) -> None:
    """Scroll to bottom until link count stops growing, we hit `max_scrolls`,
    or we have `max_ad_links` collected. Capped to keep DOM size — and
    Chromium memory — bounded on small (1GB) hosts."""
    prev = -1
    for _ in range(max_scrolls):
        page.mouse.wheel(0, 20_000)
        page.wait_for_timeout(800)
        ad_count = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
                .filter(a => /^\\/en\\/jobs\\/[^\\/?]+\\/\\d+/.test(a.getAttribute('href') || ''))
                .length"""
        )
        if ad_count >= max_ad_links or ad_count == prev:
            break
        prev = ad_count


def _parse_ad_from_jsonld(page: Page, ad_url: str) -> JobAd | None:
    page.goto(ad_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    try:
        raw = page.eval_on_selector(
            "script[type='application/ld+json']", "el => el && el.textContent"
        )
    except Exception:
        raw = None
    if not raw:
        logger.error(f"no JSON-LD on {ad_url}")
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON-LD decode failed for {ad_url}: {e}")
        return None
    if data.get("@type") != "JobPosting":
        return None

    org = data.get("hiringOrganization") or {}
    addr = (data.get("jobLocation") or {}).get("address") or {}
    location_parts = [
        addr.get("addressLocality"),
        addr.get("addressRegion"),
        addr.get("addressCountry"),
    ]
    location = ", ".join(p for p in location_parts if p) or ""

    skills = data.get("skills") or []
    tags = [
        s.get("name", "").strip()
        for s in skills
        if isinstance(s, dict) and s.get("name")
    ]

    date_posted_raw = data.get("datePosted")
    if not date_posted_raw:
        return None
    try:
        date_posted = datetime.fromisoformat(date_posted_raw.replace("Z", "+00:00"))
    except ValueError as e:
        logger.error(f"bad datePosted {date_posted_raw!r} on {ad_url}: {e}")
        return None

    job_ad_dict = {
        "role": (data.get("title") or "").strip(),
        "company": (org.get("name") or "").strip(),
        "location": location,
        "min_experience": data.get("experienceRequirements"),
        "employment_type": (data.get("employmentType") or "").strip(),
        "category": (data.get("occupationalCategory") or "").strip(),
        "remote": None,  # not in JSON-LD; could be derived from page text in a follow-up
        "details": _html_to_lines(data.get("description") or ""),
        "tags": tags,
        "ad_link": ad_url,
        "date_posted": date_posted,
    }
    try:
        return JobAd(**job_ad_dict)
    except ValidationError as e:
        logger.exception(f"validation failed for {ad_url}: {e}")
        return None


def scrape(debug: bool = False, retries: int = 0, to_pkl: bool = True) -> Set[JobAd]:
    """Scrape kariera.gr job ads. In debug mode, caps to ~5 ads per search term."""
    start = perf_counter()
    results: Set[JobAd] = set()
    seen_links: set[str] = set()

    with sync_playwright() as p:
        # Memory-friendly Chromium flags so this also runs on 1GB VMs.
        # --disable-dev-shm-usage: use /tmp instead of /dev/shm (often tiny).
        # --no-sandbox: we're already inside an isolated VM/container.
        # --disable-gpu: no GPU available, skip the init path.
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--no-zygote",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            page.goto(f"{BASE_URL}/en", wait_until="domcontentloaded")
            _accept_cookies(page)

            collected: list[str] = []
            for term in SEARCH_TERMS:
                logger.info(f"collecting links for term: {term}")
                # Recreate the page between terms so Chromium drops the heavy
                # post-scroll DOM. Important on 1GB hosts where carrying it
                # across navigations leads to swap thrashing.
                page.close()
                page = context.new_page()
                page.set_default_timeout(DEFAULT_TIMEOUT_MS)

                page.goto(
                    f"{BASE_URL}/en/jobs?title={term}",
                    wait_until="domcontentloaded",
                )
                if not debug:
                    _scroll_to_load_more(page)
                links = _collect_ad_links_on_listing(page)
                if debug:
                    links = links[:5]
                logger.info(f"  {len(links)} ad links from term={term}")
                for link in links:
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    collected.append(link)

            logger.info(f"collected {len(collected)} unique ad links")

            for ad_url in collected:
                logger.info(f"fetching {ad_url}")
                ad = _parse_ad_from_jsonld(page, ad_url)
                if ad is not None:
                    results.add(ad)
        finally:
            context.close()
            browser.close()

    elapsed = perf_counter() - start
    logger.info(
        f"fetched {len(results)} ads in {int(elapsed // 60)}m {round(elapsed % 60)}s"
    )

    if to_pkl:
        pd.DataFrame([ja.model_dump() for ja in results]).to_pickle("latest_scrapings.pkl")

    return results
