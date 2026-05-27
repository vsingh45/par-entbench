"""
Seed Postgres with TPC-H scale factor 1 + SAM-flavored tables.

Run after `docker compose up -d` and after Postgres health check passes.

Note: TPC-H data generation requires the `dbgen` utility. For this pilot,
we generate a synthetic SAM-flavored schema sufficient for EntBench tasks
and seed minimal TPC-H tables. Full TPC-H scale factor 1 requires the
official TPC-H Tools available from https://www.tpc.org/tpch/.
"""
import os
import psycopg2
from datetime import datetime, timedelta
import random


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "entbench",
    "password": "entbench",
    "dbname": "entbench",
}


SCHEMA_SQL = """
-- SAM-flavored tables
CREATE TABLE IF NOT EXISTS consumption_facts (
    event_id BIGSERIAL PRIMARY KEY,
    license_id VARCHAR(50),
    publisher VARCHAR(100),
    product VARCHAR(100),
    event_date DATE,
    event_type VARCHAR(50),
    amount_usd NUMERIC(12, 2),
    daily_active_seats INTEGER,
    user_id VARCHAR(50),
    fiscal_year INTEGER,
    fiscal_quarter INTEGER
);
CREATE INDEX IF NOT EXISTS idx_consumption_publisher ON consumption_facts(publisher);
CREATE INDEX IF NOT EXISTS idx_consumption_event_date ON consumption_facts(event_date);

-- Billing
CREATE TABLE IF NOT EXISTS invoice_facts (
    invoice_id BIGSERIAL PRIMARY KEY,
    contract_id VARCHAR(50),
    vendor_name VARCHAR(100),
    invoice_date DATE,
    due_date DATE,
    paid_date DATE,
    amount_usd NUMERIC(12, 2),
    status VARCHAR(20)
);

-- IAM
CREATE TABLE IF NOT EXISTS access_log_facts (
    log_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    permission VARCHAR(100),
    resource VARCHAR(200),
    access_time TIMESTAMP,
    action VARCHAR(50),
    result VARCHAR(20)
);
CREATE INDEX IF NOT EXISTS idx_access_user ON access_log_facts(user_id);
CREATE INDEX IF NOT EXISTS idx_access_time ON access_log_facts(access_time);

-- Minimal TPC-H placeholder tables (use real TPC-H dbgen for full benchmark)
CREATE TABLE IF NOT EXISTS customer (
    c_custkey INTEGER PRIMARY KEY,
    c_name VARCHAR(25),
    c_nationkey INTEGER,
    c_mktsegment VARCHAR(10),
    c_acctbal NUMERIC(12, 2)
);

CREATE TABLE IF NOT EXISTS orders (
    o_orderkey INTEGER PRIMARY KEY,
    o_custkey INTEGER REFERENCES customer(c_custkey),
    o_orderstatus CHAR(1),
    o_totalprice NUMERIC(12, 2),
    o_orderdate DATE,
    o_orderpriority VARCHAR(15)
);

CREATE TABLE IF NOT EXISTS lineitem (
    l_orderkey INTEGER,
    l_linenumber INTEGER,
    l_quantity NUMERIC(12, 2),
    l_extendedprice NUMERIC(12, 2),
    l_discount NUMERIC(4, 2),
    l_tax NUMERIC(4, 2),
    l_returnflag CHAR(1),
    l_linestatus CHAR(1),
    l_shipdate DATE,
    PRIMARY KEY (l_orderkey, l_linenumber)
);
"""


def seed_sam_data(cur):
    """Insert synthetic SAM data — publishers, consumption events."""
    publishers = [
        ("Microsoft", "Office 365"),
        ("Microsoft", "Azure"),
        ("Adobe", "Creative Cloud"),
        ("Adobe", "Acrobat Pro"),
        ("Adobe", "Document Cloud"),
        ("Salesforce", "Sales Cloud"),
        ("Salesforce", "Service Cloud"),
        ("Atlassian", "Jira"),
        ("Atlassian", "Confluence"),
        ("Slack", "Business+"),
    ]

    random.seed(42)
    base_date = datetime(2024, 1, 1)
    inserts = []
    license_counter = 1

    for pub, prod in publishers:
        for q in range(1, 5):
            for month_offset in range(3):
                event_date = base_date + timedelta(days=(q - 1) * 90 + month_offset * 30)
                amount = random.uniform(5000, 50000)
                seats = random.randint(50, 500)
                license_id = f"LIC-{pub[:3].upper()}-{license_counter:04d}"
                inserts.append((
                    license_id, pub, prod, event_date, "renewal",
                    amount, seats, f"USER-{random.randint(1000, 9999)}",
                    2024, q,
                ))
                license_counter += 1

    cur.executemany(
        """INSERT INTO consumption_facts
           (license_id, publisher, product, event_date, event_type,
            amount_usd, daily_active_seats, user_id, fiscal_year, fiscal_quarter)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        inserts,
    )
    print(f"Inserted {len(inserts)} consumption_facts rows")


def main():
    print("Connecting to Postgres...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating schema...")
    cur.execute(SCHEMA_SQL)

    print("Seeding SAM data...")
    seed_sam_data(cur)

    print("Done. Postgres seeded.")
    print()
    print("NOTE: TPC-H tables (customer, orders, lineitem) are created but empty.")
    print("For full TPC-H scale factor 1, generate data with dbgen and COPY into these tables.")
    print("See https://www.tpc.org/tpch/ for the official toolkit.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
