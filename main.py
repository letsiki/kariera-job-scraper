import pandas as pd
from datetime import datetime
from scraper import scrape
from filtering import filter_
import argparse
from filter_daily_md import filter_daily_md


def main():
    date = datetime.strftime(datetime.now(), "%Y-%m-%d")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    args = parser.parse_args()

    df = pd.DataFrame(scrape(debug=args.debug))

    df.to_pickle(f"data/{'debug' if args.debug else date}-df.pkl")
    df.to_csv(
        f"data/{'debug' if args.debug else date}.csv", index=False
    )

    # filter and save again
    df = filter_(df)
    df.to_pickle(
        f"data/{'debug' if args.debug else date}-filtered-df.pkl"
    )
    df.to_csv(
        f"data/{'debug' if args.debug else date}-filtered.csv",
        index=False,
    )

    links = [link for link in df["ad_link"]]
    roles = [role for role in df["role"]]
    companies = [company for company in df["company"]]
    locations = [location for location in df["location"]]
    try:
        with open(
            f"data/daily-urls/{'debug-' if args.debug else ''}daily-urls.md",
            "r",
        ) as f:
            original = f.read()
    except FileNotFoundError:
        with open(
            f"data/daily-urls/{'debug-' if args.debug else ''}daily-urls.md",
            "w+",
        ) as f:
            original = f.read()

    with open(
        f"data/daily-urls/{'debug-' if args.debug else ''}daily-urls.md",
        "w",
    ) as f:
        f.write(f"#### {date}\n")
        for role, link, company, location in zip(
            roles, links, companies, locations
        ):
            f.write(
                f"[{role}{' - ' if company else ''}{company} - {location}]({link})  \n"
            )
        f.write(f"  \n{original}")

    if not args.debug:
        filter_daily_md()


if __name__ == "__main__":
    main()
