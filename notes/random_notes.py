
# from datetime import datetime
# from zoneinfo import ZoneInfo

# dt = datetime.now(tz=ZoneInfo("UTC"))
# dt_athens = dt.astimezone(ZoneInfo("Europe/Athens"))
# print(dt_athens.isoformat())


# # Save as list of dicts
# dict_rows = [dict(row._mapping) for row in rows]

# # write code to check for duplicates
# # ... (dict now vs dict yesterday)
# # update days_old on existing entries (+1) and insert new timestamp
# # return dict to insert

# engine = create_engine("postgresql://user:pass@localhost/dbname")


# # Receive [dict] to be inserted and insert
# # Insert many rows
# rows = [
#     {"my_int_column": 10},
#     {"my_int_column": 20},
#     {"my_int_column": 30},
# ]

# with engine.connect() as conn:
#     result = conn.execute(text("INsert rows"))
#     conn.commit()
# """
# INSERT INTO my_table (my_int_column, my_timestamp_column)
# VALUES (42, DEFAULT);
# """

# """
# INSERT INTO my_table (my_int_column, my_timestamp_column)
# VALUES
#     (10, DEFAULT),
#     (20, DEFAULT),
#     (30, DEFAULT);

# """

# """
# select *
# from alex
#     where john
#     group by

# """


# class JobAdDB:
#     def __init__(
#         self, alchemy_engine: Engine, days_old: int = 0
#     ):
#         with alchemy_engine.connect() as conn:
#             if (
#                 not isinstance(days_old, int)
#                 or days_old <= 0
#             ):
#                 result = conn.execute(text("SELECT * FROM job_ads"))
#             else:
#                 result = conn.execute(
#                     text(
#                         "SELECT * FROM job_ads WHERE created_at >= date_trunc('day', NOW()) -  (:days || ' days')::INTERVAL"
#                     ),
#                     {"days": str(days_old)},
#                 )
#         self._data = [
#             JobAd(**data_row) for data_row in result.mappings().all()
#         ]

#     @property
#     def data(self):
#         return self._data

# def get_daily_ads(self, day: int = 0):
#     date = datetime.now().date() - timedelta(day)
#     return [
#         job_ad
#         for job_ad in self.data
#         if job_ad.created_at is not None
#         and job_ad.created_at.date() == date
#     ]

# def update_db(self, scraped_data: List[dict]):
# for job_ad in scraped_data:
#     if job_ad in self.data and job_ad.cre


# use only current day from self (get_daily_ads)
# if last day in pg is today:
# use sets to find what one has and the other has not
# what ever self.

# """
# I am gonna assume that ads can be reniewed, keeping original ad_link. a field is_active default True will be added to database, and model


# ✅ 1. Load all scraped into a collection of JobAd instances. handle pydantic.ValidationError

# ✅ 2. Get max(date_updated) from database

# ✅ 3. if max is null, pass the whole collection of the scraped jobads with last_update as max create_date

# ✅ 4. if not filter those created_at after last_update and upsert them with with last_update as the max created date again

# ✅ 4. upsert them with do update (most or all fields) in case there are reniewed ads

# No need to use is_active column (which takes up resources), last 30 days are the active ones.

# For generating the daily report
# append a new daily entry on top of md file with a now().date header (already doing)
# then
# get jobs with update_date.date = now.date
# Reverse sorted Job ads
# and print (str())
# (select timezone to discplay as current timezone.)

#  active jobs -> timestampt.day + interval '30 days' >= now
# """


# def wait_for_pg_to_be_ready(self):
#     while True:
#         try:
#             conn = psycopg2.connect(
#                 host=POSTGRES_HOST,
#                 port=5432,
#                 dbname="postgres",
#                 user=POSTGRES_USER,
#                 password=POSTGRES_PASSWORD,
#             )
#             conn.close()
#             logger.info("Postgres is ready!")
#             break
#         except psycopg2.OperationalError:
#             logger.info("Waiting for Postgres...")
#             time.sleep(2)


# with engine.connect() as conn:
#     result = conn.execute(
#         text("SELECT id, my_int_column FROM my_table")
#     )
#     rows = result.fetchall()