import csv


def read_csv_f_column_data(
    filename,
) -> list:
    with open(filename, "r") as f:
        reader = csv.reader(f)
        next(reader)
        return [row[0] for row in reader]
