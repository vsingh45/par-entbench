"""
Seed MongoDB with SAM operational collections.

Run after `docker compose up -d` and after MongoDB health check passes.

Note: Atlas sample datasets (sample_mflix, sample_airbnb, sample_analytics)
required by some Mongo-Gen tasks must be loaded separately via mongorestore.
Download dumps from MongoDB Atlas sample dataset distribution.
"""
from pymongo import MongoClient
from datetime import datetime, timedelta
import random


MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "entbench"


def seed_sam_licenses(db):
    """Seed sam_licenses operational collection."""
    publishers = [
        ("Microsoft", "Office 365", "critical"),
        ("Microsoft", "Azure", "critical"),
        ("Adobe", "Creative Cloud", "standard"),
        ("Adobe", "Acrobat Pro", "standard"),
        ("Adobe", "Document Cloud", "cuttable"),
        ("Salesforce", "Sales Cloud", "critical"),
        ("Salesforce", "Service Cloud", "standard"),
        ("Atlassian", "Jira", "standard"),
        ("Atlassian", "Confluence", "standard"),
        ("Slack", "Business+", "standard"),
    ]

    teams = ["Engineering", "Sales", "Marketing", "Finance", "HR", "Legal"]

    random.seed(42)
    docs = []
    for i, (pub, prod, criticality) in enumerate(publishers):
        for j in range(3):  # multiple contracts per publisher
            license_id = f"LIC-{pub[:3].upper()}-{i*3+j+1:04d}"
            term_start = datetime(2024, random.randint(1, 6), 1)
            term_end = term_start + timedelta(days=365)
            contract_value = random.uniform(20000, 250000)
            seat_count = random.randint(20, 500)
            docs.append({
                "license_id": license_id,
                "publisher": pub,
                "product": prod,
                "contract_value_usd": round(contract_value, 2),
                "seat_count": seat_count,
                "cost_per_seat_usd": round(contract_value / seat_count, 2),
                "term_start": term_start,
                "term_end": term_end,
                "renewal_terms": random.choice(["annual", "monthly", "biennial"]),
                "assigned_team": random.choice(teams),
                "status": "active",
                "criticality_tier": criticality,
            })

    db.sam_licenses.delete_many({})
    db.sam_licenses.insert_many(docs)
    print(f"Inserted {len(docs)} sam_licenses documents")


def seed_sam_seat_assignments(db):
    """Seed sam_seat_assignments collection."""
    licenses = list(db.sam_licenses.find({}, {"license_id": 1, "seat_count": 1}))

    random.seed(43)
    docs = []
    for lic in licenses:
        n_assignments = min(lic["seat_count"], random.randint(5, 50))
        for k in range(n_assignments):
            assigned_date = datetime(2024, random.randint(1, 10), random.randint(1, 28))
            # Some seats have last_active_date, some don't (missing field test)
            if random.random() < 0.8:
                last_active = assigned_date + timedelta(days=random.randint(1, 180))
            else:
                last_active = None  # tests null handling
            doc = {
                "assignment_id": f"ASN-{lic['license_id']}-{k:03d}",
                "license_id": lic["license_id"],
                "user_id": f"USER-{random.randint(1000, 9999)}",
                "assigned_date": assigned_date,
                "status": "active" if random.random() < 0.9 else "inactive",
            }
            if last_active is not None:
                doc["last_active_date"] = last_active
            docs.append(doc)

    db.sam_seat_assignments.delete_many({})
    db.sam_seat_assignments.insert_many(docs)
    print(f"Inserted {len(docs)} sam_seat_assignments documents")


def seed_billing_contracts(db):
    """Seed billing_contracts collection."""
    vendors = ["Microsoft", "Adobe", "Salesforce", "Atlassian", "Slack"]
    random.seed(44)
    docs = []
    for v in vendors:
        for k in range(3):
            docs.append({
                "contract_id": f"CTR-{v[:3].upper()}-{k:03d}",
                "vendor_name": v,
                "term_months": 12,
                "annual_value_usd": round(random.uniform(50000, 300000), 2),
                "payment_terms_days": 30,
                "early_payment_discount_pct": 2.0,
                "status": "active",
            })

    db.billing_contracts.delete_many({})
    db.billing_contracts.insert_many(docs)
    print(f"Inserted {len(docs)} billing_contracts documents")


def seed_iam_roles(db):
    """Seed iam_roles collection."""
    roles = [
        ("engineer", ["db.production.read", "db.dev.write", "deploy.staging"]),
        ("senior-engineer", ["db.production.read", "db.production.write", "deploy.staging", "deploy.production"]),
        ("admin", ["iam.users.read", "iam.users.write", "iam.users.delete", "secrets.read"]),
        ("finance-analyst", ["finance.reports.read", "finance.dashboards.read"]),
        ("procurement-analyst", ["procurement.contracts.read", "procurement.invoices.read"]),
    ]
    docs = []
    for role_name, perms in roles:
        docs.append({
            "role_name": role_name,
            "permissions": perms,
            "is_elevated": any(p in ["secrets.read", "iam.users.delete", "db.production.write"]
                               for p in perms),
        })
    db.iam_roles.delete_many({})
    db.iam_roles.insert_many(docs)
    print(f"Inserted {len(docs)} iam_roles documents")


def main():
    print("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("Seeding SAM operational collections...")
    seed_sam_licenses(db)
    seed_sam_seat_assignments(db)

    print("Seeding billing collections...")
    seed_billing_contracts(db)

    print("Seeding IAM collections...")
    seed_iam_roles(db)

    print("\nDone. MongoDB seeded.")
    print()
    print("NOTE: Atlas sample datasets (sample_mflix, sample_airbnb, sample_analytics)")
    print("required by some Mongo-Gen tasks must be loaded separately:")
    print("  mongorestore --uri mongodb://localhost:27017 atlas_samples/")

    client.close()


if __name__ == "__main__":
    main()
