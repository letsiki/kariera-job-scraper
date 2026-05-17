from scraper import scrape
from write_to_db import DBWriter
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    args = parser.parse_args()

    # Connect first so the scraper can skip already-known ads.
    dbwriter = DBWriter()
    known = dbwriter.known_ad_links()
    dbwriter.scraped_jobs = scrape(args.debug, skip_links=known)
    dbwriter.insert_job_ads()
    dbwriter.to_markdown(filtered_only=True)
    dbwriter.export_snapshots()


if __name__ == "__main__":
    main()


# TODO:
#   - Add a default 0, repost_count field -> done add both two database and jobad class
#   - In upserts increment it -> done
#   - Make it part of the JobAd __str__ -> done
