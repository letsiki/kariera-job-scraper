import re


def filter_daily_md():
    with open("data/daily-urls/daily-urls.md", "r") as f:
        text = f.read()
        sections = re.split(
            r"(?=^#### \d{4}-\d{2}-\d{2})",
            text.strip(),
            flags=re.MULTILINE,
        )
        sections = [s.strip() for s in sections if s.strip()]

    filtered_entries = list(
        map(
            lambda x: x[0],
            filter(
                lambda x: x[1],
                zip(sections, _map_is_unique_day(_get_dates(sections))),
            ),
        )
    )

    with open("data/daily-urls/daily-urls.md", "w") as f:
        md_text = "  \n\n".join(filtered_entries)
        f.write(md_text)


def _entry_to_date(entry):
    return re.split(r"(?<=\d)\s", entry)[0].split()[1]


def _get_dates(sections):
    return [_entry_to_date(entry) for entry in sections]


def _map_is_unique_day(dates):
    unique_dates = [True]
    for i in range(1, len(dates)):
        unique_dates.append(dates[i] != dates[i - 1])
    return unique_dates
