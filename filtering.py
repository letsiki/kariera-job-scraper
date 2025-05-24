import pandas as pd
from datetime import datetime

date = datetime.strftime(datetime.now(), "%Y-%m-%d")

excluded_categories = (
    "Τηλεφωνικό Κέντρο / Εξυπηρέτηση Πελατών",
    "Λογιστικά",
    "Γραμματειακή Υποστήριξη / Υπάλληλος Γραφείου",
    "Αποθήκη / Logistics",
    "Προμήθειες / Αγορές",
    "Πωλήσεις / Διαχείριση Πελατών",
    "Τεχνικοί / Service",
    "Οικονομικά",
    "Μάρκετινγκ / Διαφήμιση",
    "Ανθρώπινο Δυναμικό",
)
excluded_min_experience = (
    "C-level / Executive",
    "Με μεγάλη εμπειρία",
    "",
)
excluded_role_patterns = (
    r"(?<!mid-)senior",
    r"\.net",
    r"C#",
    r"Angular",
    r"custsomer support",
    r"customer service",
    r"front[ -]?end",
    r"full[- ]?stack",
    r"IT support",
    r"Trainer",
    r"technician",
    r"php",
    r"deutsch",
    r"retail",
    r"react",
    r"java",
    r"Ηλεκτρολόγος",
    r"Invoicing",
    r"Πωλητές",
    r"τεχνικ[οό]ς",
    r"υποστ[ήη]ριξη",
    r"backoffice",
    r"cobol",
    r"business",
    r"german",
    r"business",
    r"experienced",
    r"lead",
    r"system[s] support",
    r"call  center",
    r"procurement",
    r"logistic",
    r"sales",
    r"data[- ]entry",
    r"hr",
    r"sap",
    r"abap",
    r"node.js",
    r"hospitality",
    r"market",
    r"Φαρμακοποιός",
    r"website",
    r"receptionist",
    r"civil engineer",
    r"Web Developer",
    r"helpdesk",
    r"Πωλητής",
    r"Μάγειρας",
)
excluded_role_pattern = "|".join(excluded_role_patterns)


def filter_(df: pd.DataFrame):
    df = df[~df["category"].isin(excluded_categories)]
    df = df[~df["min_experience"].isin(excluded_min_experience)]
    df = df[
        ~df["role"].str.contains(
            excluded_role_pattern, na=False, case=False
        )
    ]

    df["role"] = df["role"].astype("string")

    df[
        (
            (df["role"].str.lower().str.contains("data"))
            & (~df["role"].str.lower().str.contains("scientist"))
            & (~df["role"].str.lower().str.contains("analyst"))
        )
        | (df["role"].str.lower().str.contains("python"))
    ]
