"""
Mock Telecom Data Generator
Generates ~2,000 customers with realistic billing and network usage records.

Usage:
    python generate_data.py

Overwrites any existing data in telecom.db.
"""

import random
import uuid
from datetime import date, timedelta

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

from config import SQLITE_DB_PATH

# ---------------------------------------------------------------------------
# Seed for reproducibility
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna",
    "Kenneth", "Michelle", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Frank", "Samantha", "Raymond", "Katherine", "Gregory", "Christine", "Samuel", "Debra",
    "Benjamin", "Rachel", "Patrick", "Carolyn", "Jack", "Janet", "Dennis", "Catherine",
    "Jerry", "Maria", "Alexander", "Heather", "Tyler", "Diane", "Aaron", "Julie",
    "Aria", "Liam", "Noah", "Oliver", "Elijah", "Lucas", "Mason", "Logan",
    "Ethan", "Aiden", "Caden", "Jackson", "Grayson", "Carter", "Jayden", "Wyatt",
    "Santiago", "Mateo", "Levi", "Sebastian", "Owen", "Caleb", "Henry", "Isaac",
    "Zoe", "Nora", "Lily", "Mia", "Ava", "Sophia", "Isabella", "Charlotte",
    "Amelia", "Harper", "Evelyn", "Abigail", "Luna", "Ella", "Scarlett", "Grace",
    "Priya", "Anjali", "Rohan", "Vikram", "Deepa", "Arjun", "Kavya", "Rahul",
    "Chen", "Wei", "Ling", "Hui", "Fang", "Ming", "Jing", "Xin",
    "Mohammed", "Fatima", "Ali", "Omar", "Aisha", "Hassan", "Yasmin", "Khalid",
    "Sofia", "Matteo", "Lorenzo", "Giulia", "Marco", "Elena", "Luca", "Chiara",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
    "Mitchell", "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz",
    "Parker", "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales",
    "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson",
    "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward",
    "Richardson", "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray",
    "Mendoza", "Ruiz", "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel",
    "Myers", "Long", "Ross", "Foster", "Jimenez", "Powell", "Jenkins", "Perry",
    "Russell", "Sullivan", "Bell", "Coleman", "Butler", "Henderson", "Barnes", "Gonzales",
    "Fisher", "Vasquez", "Simmons", "Romero", "Jordan", "Patterson", "Alexander", "Hamilton",
    "Graham", "Reynolds", "Griffin", "Wallace", "Moreno", "West", "Cole", "Hayes",
    "Bryant", "Herrera", "Gibson", "Ellis", "Tran", "Medina", "Aguilar", "Stevens",
    "Murray", "Ford", "Castro", "Marshall", "Owens", "Harrison", "Fernandez", "Mcdonald",
    "Chen", "Wang", "Li", "Zhang", "Liu", "Singh", "Kumar", "Sharma",
    "Nakamura", "Tanaka", "Suzuki", "Watanabe", "Ito", "Yamamoto", "Kobayashi", "Kato",
    "Okafor", "Nwosu", "Adeyemi", "Mensah", "Diallo", "Traoré", "Koné", "Bah",
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker",
    "Johansson", "Andersson", "Karlsson", "Nilsson", "Eriksson", "Larsson", "Svensson",
]

PLAN_TYPES = ["Prepaid", "Postpaid_5G", "Enterprise"]

# Weighted distribution: more Prepaid, fewer Enterprise
PLAN_WEIGHTS = [0.40, 0.45, 0.15]

# Churn rates by plan type
CHURN_RATES = {
    "Prepaid": 0.28,
    "Postpaid_5G": 0.18,
    "Enterprise": 0.08,
}

# Monthly billing amount ranges by plan type (min, max)
BILLING_RANGES = {
    "Prepaid":     (25.00,   75.00),
    "Postpaid_5G": (85.00,  175.00),
    "Enterprise":  (2500.00, 12000.00),
}

# Data usage (GB/month) ranges by plan type
USAGE_RANGES = {
    "Prepaid":     (1.0,   55.0),
    "Postpaid_5G": (15.0, 120.0),
    "Enterprise":  (60.0, 400.0),
}

# Dropped call ranges by plan type (heavier usage = more risk)
DROPPED_CALL_RANGES = {
    "Prepaid":     (0, 20),
    "Postpaid_5G": (0, 15),
    "Enterprise":  (0, 10),
}

# Months to generate billing/usage for (recent 12 months)
BILLING_MONTHS = [
    "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06",
    "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12",
]

# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_signup_date() -> str:
    start = date(2018, 1, 1)
    end = date(2023, 12, 31)
    delta = (end - start).days
    return str(start + timedelta(days=random.randint(0, delta)))


def generate_customers(n: int) -> list[dict]:
    customers = []
    for i in range(1, n + 1):
        plan = random.choices(PLAN_TYPES, weights=PLAN_WEIGHTS, k=1)[0]
        churn = "Churned" if random.random() < CHURN_RATES[plan] else "Active"
        customers.append({
            "customer_id": f"C{i:05d}",
            "name": random_name(),
            "plan_type": plan,
            "signup_date": random_signup_date(),
            "churn_status": churn,
        })
    return customers


def generate_billing(customers: list[dict]) -> list[dict]:
    invoices = []
    inv_num = 1
    for cust in customers:
        plan = cust["plan_type"]
        lo, hi = BILLING_RANGES[plan]

        # Active customers have records for most months; churned for fewer
        if cust["churn_status"] == "Churned":
            months = random.sample(BILLING_MONTHS, k=random.randint(1, 6))
        else:
            months = random.sample(BILLING_MONTHS, k=random.randint(6, 12))

        months.sort()
        unpaid_streak = 0  # track consecutive unpaid for realism

        for month in months:
            amount = round(random.uniform(lo, hi), 2)

            # Payment probability: churned customers more likely to have unpaid bills
            if cust["churn_status"] == "Churned":
                pay_prob = max(0.3, 0.85 - unpaid_streak * 0.15)
            else:
                pay_prob = max(0.7, 0.97 - unpaid_streak * 0.05)

            is_paid = 1 if random.random() < pay_prob else 0
            unpaid_streak = 0 if is_paid else unpaid_streak + 1

            invoices.append({
                "invoice_id": f"INV{inv_num:07d}",
                "customer_id": cust["customer_id"],
                "billing_month": month,
                "amount_due": amount,
                "is_paid": is_paid,
            })
            inv_num += 1

    return invoices


def generate_network_usage(customers: list[dict]) -> list[dict]:
    usage_records = []
    usage_num = 1
    for cust in customers:
        plan = cust["plan_type"]
        gb_lo, gb_hi = USAGE_RANGES[plan]
        dc_lo, dc_hi = DROPPED_CALL_RANGES[plan]

        if cust["churn_status"] == "Churned":
            months = random.sample(BILLING_MONTHS, k=random.randint(1, 6))
        else:
            months = random.sample(BILLING_MONTHS, k=random.randint(6, 12))

        months.sort()

        for month in months:
            # Churned customers with high dropped calls — a contributing churn factor
            if cust["churn_status"] == "Churned":
                dropped = random.randint(dc_lo, min(dc_hi + 15, 40))
            else:
                dropped = random.randint(dc_lo, dc_hi)

            usage_records.append({
                "usage_id": f"U{usage_num:07d}",
                "customer_id": cust["customer_id"],
                "month": month,
                "data_gb_used": round(random.uniform(gb_lo, gb_hi), 2),
                "dropped_calls_count": dropped,
            })
            usage_num += 1

    return usage_records


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

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


def write_to_db(customers, billing, usage) -> None:
    engine = create_engine(f"sqlite:///{SQLITE_DB_PATH}", echo=False)
    with engine.begin() as conn:
        # Wipe and recreate
        conn.execute(text("DROP TABLE IF EXISTS network_usage"))
        conn.execute(text("DROP TABLE IF EXISTS billing"))
        conn.execute(text("DROP TABLE IF EXISTS customers"))
        for stmt in _DDL_STATEMENTS:
            conn.execute(text(stmt))

        # Bulk insert in chunks of 500 for performance
        chunk = 500

        for i in range(0, len(customers), chunk):
            conn.execute(
                text("INSERT INTO customers VALUES (:customer_id,:name,:plan_type,:signup_date,:churn_status)"),
                customers[i:i + chunk],
            )
        print(f"  customers  : {len(customers):,} rows")

        for i in range(0, len(billing), chunk):
            conn.execute(
                text("INSERT INTO billing VALUES (:invoice_id,:customer_id,:billing_month,:amount_due,:is_paid)"),
                billing[i:i + chunk],
            )
        print(f"  billing    : {len(billing):,} rows")

        for i in range(0, len(usage), chunk):
            conn.execute(
                text("INSERT INTO network_usage VALUES (:usage_id,:customer_id,:month,:data_gb_used,:dropped_calls_count)"),
                usage[i:i + chunk],
            )
        print(f"  network_usage: {len(usage):,} rows")


# ---------------------------------------------------------------------------
# Stats summary
# ---------------------------------------------------------------------------

def print_stats(customers, billing, usage) -> None:
    total = len(customers)
    by_plan = {}
    churned = 0
    for c in customers:
        by_plan[c["plan_type"]] = by_plan.get(c["plan_type"], 0) + 1
        if c["churn_status"] == "Churned":
            churned += 1

    unpaid = sum(1 for b in billing if b["is_paid"] == 0)
    total_revenue = sum(b["amount_due"] for b in billing if b["is_paid"] == 1)
    outstanding = sum(b["amount_due"] for b in billing if b["is_paid"] == 0)
    high_drops = sum(1 for u in usage if u["dropped_calls_count"] > 15)

    print("\n  === Dataset Summary ===")
    print(f"  Customers   : {total:,}")
    for plan, count in sorted(by_plan.items()):
        pct = count / total * 100
        print(f"    {plan:<15}: {count:>5,}  ({pct:.1f}%)")
    print(f"  Churned     : {churned:,}  ({churned/total*100:.1f}%)")
    print(f"\n  Billing rows      : {len(billing):,}")
    print(f"  Unpaid invoices   : {unpaid:,}  ({unpaid/len(billing)*100:.1f}%)")
    print(f"  Paid revenue      : ${total_revenue:,.2f}")
    print(f"  Outstanding AR    : ${outstanding:,.2f}")
    print(f"\n  Usage rows        : {len(usage):,}")
    print(f"  High drop events  : {high_drops:,}  (>15 dropped calls/month)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Generating mock telecom data...")

    customers = generate_customers(2000)
    print(f"  Generated {len(customers):,} customers")

    billing = generate_billing(customers)
    print(f"  Generated {len(billing):,} billing records")

    usage = generate_network_usage(customers)
    print(f"  Generated {len(usage):,} usage records")

    print(f"\nWriting to {SQLITE_DB_PATH}...")
    write_to_db(customers, billing, usage)

    print_stats(customers, billing, usage)
    print(f"\nDone. Database saved to: {SQLITE_DB_PATH}")


if __name__ == "__main__":
    main()
