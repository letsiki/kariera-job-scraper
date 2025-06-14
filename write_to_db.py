import logging
from logger import configure_logging
import os
from datetime import datetime
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine, text
from job_ad import JobAd
from pathlib import Path
from filtering import filter_
import pandas as pd
from logging_setup import logging_setup
import re

logger = logging.Logger(__name__)
date = datetime.strftime(datetime.now(), "%Y-%m-%d")
logging_setup(
    logger,
    mode="fc",
    filename=f"log/{date}.log",
    filemode="w",
)

# adjust the variables if needed.
# Use the provided .sql to create the table
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Password21!!!")
POSTGRES_DB = "kariera_gr"
POSTGRES_TABLE = "job_ads"


class DBWriter:
    def __init__(self, scraped_jobs: set[JobAd]):
        self._engine: Engine = create_engine(
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"
        )
        self._scraped_jobs = scraped_jobs

    def _get_last_update_from_db(self) -> datetime | None:

        with self._engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT MAX(date_updated) FROM {POSTGRES_TABLE}"),
            )
            return result.scalar()

    def insert_job_ads(self):
        last_update = self._get_last_update_from_db()
        try:
            most_recent_ad = max(self._scraped_jobs).date_posted
        except ValueError as e:
            logger.info("Couldn't return data, e")
        with self._engine.begin() as conn:
            if last_update is None:
                for job_ad in self._scraped_jobs:
                    param_dict = dict(
                        **job_ad.model_dump(),
                    )
                    param_dict["date_updated"] = most_recent_ad
                    conn.execute(
                        text(
                            f"""
                            INSERT INTO {POSTGRES_TABLE} (
                                role, company, location, min_experience, employment_type, category, remote, details, tags, ad_link, date_posted, date_updated
                            )
                            VALUES (
                                :role, :company, :location, :min_experience, :employment_type, :category, :remote, :details, :tags, :ad_link, :date_posted, :date_updated
                            )
                        """
                        ),
                        param_dict,  # This converts the Pydantic model to a dict {id: ..., name: ..., email: ...}
                    )
            else:
                filtered_scraped_jobs = set(
                    filter(
                        lambda job_ad: job_ad.date_posted > last_update,
                        self._scraped_jobs,
                    )
                )
                for job_ad in filtered_scraped_jobs:
                    param_dict = dict(
                        **job_ad.model_dump(),
                    )
                    param_dict["date_updated"] = most_recent_ad
                    # possible conflict on job ad renewals. If that
                    # is the case update all fields, and set report
                    # to False
                    conn.execute(
                        text(
                            f"""
                            INSERT INTO {POSTGRES_TABLE} (
                                role, company, location, min_experience, employment_type, category, remote, details, tags, ad_link, date_posted, date_updated
                            )
                            VALUES (
                                :role, :company, :location, :min_experience, :employment_type, :category, :remote, :details, :tags, :ad_link, :date_posted, :date_updated
                            )
                            ON CONFLICT (ad_link) DO UPDATE SET
                                role = EXCLUDED.role,
                                company = EXCLUDED.company,
                                location = EXCLUDED.location,
                                min_experience = EXCLUDED.min_experience,
                                employment_type = EXCLUDED.employment_type,
                                category = EXCLUDED.category,
                                remote = EXCLUDED.remote,
                                details = EXCLUDED.details,
                                tags = EXCLUDED.tags,
                                date_posted = EXCLUDED.date_posted,
                                date_updated = EXCLUDED.date_updated,
                                report = FALSE
                            """
                        ),
                        param_dict,
                    )

    def to_markdown(
        self,
        filtered_only: bool,
        du_md_filename="data/daily-urls/daily-urls.md",
    ):
        def _prepend_daily_report(daily_report: str):
            """Inserts daily segment in to the overall"""
            with open(du_md_filename, "r") as f:
                original = f.read()
            with open(du_md_filename, "w") as f:
                f.write(daily_report + "  \n" + original)

        # check if daily report file exists - create it
        if not os.path.exists(du_md_filename):
            logger.info("Markdown file Not Found")
            logger.info("Creating it...")
            p = Path(du_md_filename)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()

        # retrieve entries that have not been reported yet as a list of dicts
        results = self._retrieve_unreported()
        results_df = pd.DataFrame(results)
        # potentially filter the retrieved results
        if filtered_only:
            results_df = filter_(results_df)

        # Each segment in the markdown, will start with the report date (today)
        # It will be followed by the entries we get to report today
        # date_posted and date_created do not matter here.
        daily_report = self._create_daily_segment(results_df)

        # Prepend result to daily report
        _prepend_daily_report(daily_report)

        # change date to 'days-old' format for all entries (including older ones)
        self._adjust_markdown_date_fmt(du_md_filename)

        # set all unreported entries, to reported in the database
        self._set_all_unreported_to_reported()

    def _retrieve_unreported(self) -> list[dict]:
        with self._engine.connect() as conn:
            return (
                conn.execute(
                    text(
                        f"SELECT * FROM {POSTGRES_TABLE} WHERE report = FALSE"
                    ),
                )
                .mappings()
                .all()
            )  # type: ignore

    def _set_all_unreported_to_reported(self):
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                UPDATE {POSTGRES_TABLE}
                SET report = TRUE
                WHERE report = FALSE;
                    """
                ),
            )

    @staticmethod
    def _create_daily_segment(df: pd.DataFrame) -> str:
        """
        Turns daily to-be-reported job-ads into a string segment,
        that includes current date as a header.

        Dependencies:
            Validates job ads by inserting them into a JobAd object,
            and takes advantage of the JobAd __str__ method.
        """
        job_ad_strings = sorted([(JobAd(**job_ad)) for job_ad in df.to_dict(orient="records")], reverse=True)  # type: ignore

        contents = (
            "  \n".join(map(str, job_ad_strings))
            if len(job_ad_strings) != 0
            else "Nothing new to show."
        )
        return (
            f"#### {datetime.now().strftime('%Y-%m-%d')}\n" + contents
        )

    @staticmethod
    def _adjust_markdown_date_fmt(md_filename: str):
        """swap all entry dates (excludes headers) with 'days-old' using current date"""

        def repl(match: re.Match):
            value = datetime.strptime(match.group(0), "%Y-%m-%d")
            now = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return f"{str((now - value).days).zfill(2)}d"

        with open(md_filename, "r") as f:
            original = f.read()

        with open(md_filename, "w") as f:
            adjusted = re.sub(
                r"(?<! )\b\d{4}-\d{2}-\d{2}\b", repl, original
            )
            f.write(adjusted)
