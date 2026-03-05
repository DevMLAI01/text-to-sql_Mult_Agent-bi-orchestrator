"""
Creates and seeds the mock telecom SQLite database.
Returns a SQLAlchemy engine for safe query execution.

Note: If generate_data.py has already been run, get_engine() detects
the existing data and skips seeding (uses the 2,000-row dataset).
"""

import os
import sqlite3
from sqlalchemy import create_engine, text, Engine
from config import SQLITE_DB_PATH


_DDL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS customers (
    customer_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    plan_type    TEXT NOT NULL,
    signup_date  DATE NOT NULL,
    churn_status TEXT NOT NULL
)""",
    """CREATE TABLE IF NOT EXISTS billing (
    invoice_id    TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES customers(customer_id),
    billing_month TEXT NOT NULL,
    amount_due    REAL NOT NULL,
    is_paid       INTEGER NOT NULL
)""",
    """CREATE TABLE IF NOT EXISTS network_usage (
    usage_id            TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
    month               TEXT NOT NULL,
    data_gb_used        REAL NOT NULL,
    dropped_calls_count INTEGER NOT NULL
)""",
]

# Minimal fallback seed data (used only if generate_data.py hasn't been run)
_CUSTOMERS = [
    ("C001", "Aria Chen",      "Enterprise",   "2021-03-15", "Active"),
    ("C002", "Bob Marsh",      "Postpaid_5G",  "2022-07-01", "Active"),
    ("C003", "Carol Singh",    "Prepaid",      "2020-11-20", "Churned"),
    ("C004", "David Okafor",   "Enterprise",   "2019-06-10", "Active"),
    ("C005", "Elena Russo",    "Postpaid_5G",  "2023-01-05", "Churned"),
    ("C006", "Frank Liu",      "Prepaid",      "2021-09-30", "Active"),
    ("C007", "Grace Kim",      "Enterprise",   "2022-04-18", "Active"),
    ("C008", "Henry Patel",    "Postpaid_5G",  "2020-08-22", "Active"),
    ("C009", "Isabella Nwoko", "Prepaid",      "2023-05-11", "Churned"),
    ("C010", "James Tran",     "Enterprise",   "2021-12-01", "Churned"),
    ("C011", "Karen Lopez",    "Postpaid_5G",  "2022-10-15", "Active"),
    ("C012", "Leo Bergmann",   "Prepaid",      "2020-02-28", "Active"),
    ("C013", "Maya Johansson", "Enterprise",   "2023-03-07", "Active"),
    ("C014", "Nate Williams",  "Postpaid_5G",  "2019-07-19", "Churned"),
    ("C015", "Olivia Martin",  "Prepaid",      "2022-06-14", "Active"),
    ("C016", "Paul Nakamura",  "Enterprise",   "2021-01-30", "Active"),
    ("C017", "Quinn Hassan",   "Postpaid_5G",  "2023-08-03", "Active"),
    ("C018", "Rachel Torres",  "Prepaid",      "2020-05-17", "Churned"),
    ("C019", "Sam Gupta",      "Enterprise",   "2022-11-25", "Active"),
    ("C020", "Tina Moreau",    "Postpaid_5G",  "2021-04-08", "Active"),
]

_BILLING = [
    ("INV001", "C001", "2024-01", 4200.00, 1),
    ("INV002", "C001", "2024-02", 4200.00, 1),
    ("INV003", "C001", "2024-03", 4200.00, 0),
    ("INV004", "C002", "2024-01",  120.00, 1),
    ("INV005", "C002", "2024-02",  120.00, 0),
    ("INV006", "C003", "2024-01",   45.00, 1),
    ("INV007", "C004", "2024-01", 8500.00, 1),
    ("INV008", "C004", "2024-02", 8500.00, 0),
    ("INV009", "C005", "2024-01",  135.00, 0),
    ("INV010", "C007", "2024-01", 6200.00, 1),
    ("INV011", "C007", "2024-02", 6200.00, 1),
    ("INV012", "C007", "2024-03", 6200.00, 0),
    ("INV013", "C008", "2024-01",  110.00, 1),
    ("INV014", "C008", "2024-02",  110.00, 1),
    ("INV015", "C010", "2024-01", 5100.00, 0),
    ("INV016", "C011", "2024-01",  125.00, 1),
    ("INV017", "C013", "2024-01", 9900.00, 1),
    ("INV018", "C013", "2024-02", 9900.00, 0),
    ("INV019", "C016", "2024-01", 3800.00, 1),
    ("INV020", "C019", "2024-01", 7200.00, 0),
]

_NETWORK_USAGE = [
    ("U001", "C001", "2024-09",  85.4,  2),
    ("U002", "C002", "2024-09",  42.1,  8),
    ("U003", "C003", "2024-09",  12.5, 15),
    ("U004", "C004", "2024-09", 210.3,  1),
    ("U005", "C005", "2024-09",  67.8, 22),
    ("U006", "C006", "2024-09",  28.9,  4),
    ("U007", "C007", "2024-09", 195.6,  0),
    ("U008", "C008", "2024-09",  88.2,  6),
    ("U009", "C009", "2024-09",   9.1, 18),
    ("U010", "C010", "2024-09", 145.0, 30),
    ("U011", "C011", "2024-09",  55.3,  3),
    ("U012", "C012", "2024-09",  19.7,  7),
    ("U013", "C013", "2024-09", 302.1,  0),
    ("U014", "C014", "2024-09",  73.4, 25),
    ("U015", "C015", "2024-09",  33.0,  5),
    ("U016", "C016", "2024-09", 120.8,  1),
    ("U017", "C017", "2024-09",  48.6,  9),
    ("U018", "C018", "2024-09",  15.2, 20),
    ("U019", "C019", "2024-09", 175.4,  2),
    ("U020", "C020", "2024-09",  61.7, 11),
]


def get_engine() -> Engine:
    """
    Opens the SQLite DB and returns a READ-ONLY engine for safe query execution.

    A separate write engine is used only for initial table creation and seeding,
    then immediately disposed. All agent queries run against the read-only engine,
    providing a second line of defence alongside the Pydantic SELECT guard.
    """
    # --- Write engine: table creation + seeding only ---
    write_engine = create_engine(f"sqlite:///{SQLITE_DB_PATH}", echo=False)
    with write_engine.begin() as conn:
        for stmt in _DDL_STATEMENTS:
            conn.execute(text(stmt))

        existing = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
        if existing == 0:
            conn.execute(
                text("INSERT INTO customers VALUES (:id,:name,:plan,:date,:status)"),
                [{"id": r[0], "name": r[1], "plan": r[2], "date": r[3], "status": r[4]}
                 for r in _CUSTOMERS],
            )
            conn.execute(
                text("INSERT INTO billing VALUES (:inv,:cid,:month,:amt,:paid)"),
                [{"inv": r[0], "cid": r[1], "month": r[2], "amt": r[3], "paid": r[4]}
                 for r in _BILLING],
            )
            conn.execute(
                text("INSERT INTO network_usage VALUES (:uid,:cid,:month,:gb,:dc)"),
                [{"uid": r[0], "cid": r[1], "month": r[2], "gb": r[3], "dc": r[4]}
                 for r in _NETWORK_USAGE],
            )
    write_engine.dispose()

    # --- Read-only engine returned to callers ---
    # Use a creator function with an absolute path so SQLite's file: URI resolves
    # correctly regardless of the working directory, and inspect() works normally.
    abs_db_path = os.path.abspath(SQLITE_DB_PATH)

    def _ro_creator():
        return sqlite3.connect(f"file:{abs_db_path}?mode=ro", uri=True)

    read_engine = create_engine("sqlite+pysqlite://", creator=_ro_creator, echo=False)
    return read_engine
