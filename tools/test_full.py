"""Full MVP test: parse + ingest + categorize + dashboard data queries."""
import os
import sys
import tempfile

sys.path.insert(0, "/home/user/src")

# Redirect storage to a temp dir for this test
tmp = tempfile.mkdtemp(prefix="cardwise_test_")
os.environ["CARDWISE_DB"] = os.path.join(tmp, "test.db")
os.environ["CARDWISE_DATA"] = os.path.join(tmp, "statements")

from cardwise.db import get_engine, get_session
from cardwise.ingest import ingest_pdf
from cardwise.parsers import parse_pdf

pdf_path = sys.argv[1]

# 1. Parse
stmt = parse_pdf(pdf_path)
print(f"PARSE: {stmt.bank} ••{stmt.card_last4} | {len(stmt.transactions)} txns | TAD ₹{stmt.total_due}")

# 2. Ingest (twice to test dedup)
eng = get_engine()
s = get_session(eng)
r1 = ingest_pdf(pdf_path, s)
r2 = ingest_pdf(pdf_path, s)
print(f"INGEST 1: {r1['status']} | inserted {r1['inserted']}/{r1['transactions']}")
print(f"INGEST 2: {r2['status']} (expected skipped)")

# 3. Query like the dashboard does
import pandas as pd
q = """
SELECT t.date, t.description, t.amount, t.txn_type, t.category, s.bank, s.card_last4
FROM transactions t JOIN statements s ON s.id = t.statement_id
"""
df = pd.read_sql(q, eng, parse_dates=["date"])
debits = df[df.txn_type == "debit"]

print(f"\nDASHBOARD DATA: {len(df)} rows ({len(debits)} debits, {len(df)-len(debits)} credits)")
print("\nCategory breakdown (debits):")
cat = debits.groupby("category")["amount"].agg(["sum", "count"]).sort_values("sum", ascending=False)
for c, row in cat.iterrows():
    print(f"  {c:20} ₹{row['sum']:>10,.2f}  ({int(row['count'])} txns)")

print("\nTop 5 merchants:")
top = debits.groupby("description")["amount"].sum().sort_values(ascending=False).head(5)
for m, amt in top.items():
    print(f"  {m[:45]:45} ₹{amt:>10,.2f}")

# 4. Reconciliation
credits = df[df.txn_type == "credit"]["amount"].sum()
print(f"\nRECONCILE: credits ₹{credits:,.2f} vs statement ₹{stmt.payments_credits}")
print(f"           debits  ₹{debits['amount'].sum():,.2f} vs statement ₹{stmt.purchases_debits}")
