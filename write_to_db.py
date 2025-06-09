import psycopg2
import logging
from logger import configure_logging
import os
import time

# dbname is kariera_gr


configure_logging()
logger = logging.getLogger(__name__ + ".py")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Password21!!!")


def wait_for_pg_to_be_ready():
    while True:
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=5432,
                dbname="postgres",
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
            )
            conn.close()
            logger.info("Postgres is ready!")
            break
        except psycopg2.OperationalError:
            logger.info("Waiting for Postgres...")
            time.sleep(2)


from sqlalchemy import (
    create_engine,
    Table,
    Column,
    MetaData,
    Integer,
    TIMESTAMP,
    insert,
    text,
)

# code to retrieve last day and save to list of dicts
engine = create_engine("postgresql://user:pass@localhost/dbname")

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT id, my_int_column FROM my_table")
    )
    rows = result.fetchall()

# Save as list of dicts
dict_rows = [dict(row._mapping) for row in rows]

# write code to check for duplicates
# ... (dict now vs dict yesterday)
# update days_old on existing entries (+1) and insert new timestamp
# return dict to insert

engine = create_engine("postgresql://user:pass@localhost/dbname")


# Receive [dict] to be inserted and insert
# Insert many rows
rows = [
    {"my_int_column": 10},
    {"my_int_column": 20},
    {"my_int_column": 30},
]

with engine.connect() as conn:
    result = conn.execute(
        text("INsert rows")
    )
    conn.commit()
"""
INSERT INTO my_table (my_int_column, my_timestamp_column)
VALUES (42, DEFAULT);
"""

"""
INSERT INTO my_table (my_int_column, my_timestamp_column)
VALUES
    (10, DEFAULT),
    (20, DEFAULT),
    (30, DEFAULT);

"""

"""
select * 
from alex
    where john
    group by
        
"""