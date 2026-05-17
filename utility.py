import csv
from pathlib import Path


def read_csv_f_column_data(
    filename,
) -> list:
    """Return the first column of `filename` (skipping a header row).
    Returns [] if the file is missing — the filter rules can run without
    a populated locations.csv."""
    if not Path(filename).exists():
        return []
    with open(filename, "r") as f:
        reader = csv.reader(f)
        next(reader, None)
        return [row[0] for row in reader if row]
