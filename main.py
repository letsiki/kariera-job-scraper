from scraper import scrape
from write_to_db import DBWriter
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    args = parser.parse_args()

    dbwriter = DBWriter(scraped_jobs=scrape(args.debug))
    dbwriter.insert_job_ads()
    dbwriter.to_markdown(filtered_only=True)


if __name__ == "__main__":
    main()


# TODO:
#   - Add a default 0, repost_count field -> done add both two database and jobad class
#   - In upserts increment it -> done
#   - Make it part of the JobAd __str__ -> done
