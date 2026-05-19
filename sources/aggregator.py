"""Remote-jobs aggregator entry point.

Pulls RemoteOK + WeWorkRemotely, dedups by ad_link (RemoteOK and WWR
overlap heavily across days), upserts into the same job_ads table as the
kariera scraper, and re-emits the rolling-window exports that the
downstream career-copilot orchestrator consumes.

Scheduled by deploy/remote-aggregator.timer on the VM."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from logging_setup import logging_setup
from sources import arbeitnow, jobicy, remoteok, remotive, themuse, weworkremotely, workable_gr
from write_to_db import DBWriter

logger = logging.getLogger(__name__)


def gather():
    """Return a deduplicated list[JobAd]. First-seen wins on ad_link
    conflicts; ordering reflects RemoteOK-first, WWR-second priority."""
    seen: set[str] = set()
    out = []
    for src in (
        remoteok.fetch(),
        weworkremotely.fetch(),
        arbeitnow.fetch(),
        remotive.fetch(),
        jobicy.fetch(),
        themuse.fetch(),
        workable_gr.fetch(),
    ):
        for ad in src:
            if ad.ad_link in seen:
                continue
            seen.add(ad.ad_link)
            out.append(ad)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + normalize + filter, but do not write to DB")
    args = parser.parse_args()

    date = datetime.now().strftime("%Y-%m-%d")
    logging_setup(logger, mode="fc", filename=f"log/remote-{date}.log", filemode="w")

    ads = gather()
    by_src: dict[str, int] = {}
    for ad in ads:
        by_src[ad.source] = by_src.get(ad.source, 0) + 1
    logger.info("aggregator: %d candidates after dedup (%s)", len(ads), by_src)

    if args.dry_run:
        for ad in ads[:10]:
            logger.info("sample: [%s] %s @ %s — %s", ad.source, ad.role, ad.company, ad.ad_link)
        return

    writer = DBWriter()
    writer.upsert_jobs(ads)
    writer.export_snapshots()
    logger.info("aggregator: done")


if __name__ == "__main__":
    main()
