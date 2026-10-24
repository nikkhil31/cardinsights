"""Print the spend-vs-rewards report from an ingested statement (dev/QA helper).

Works both locally (repo checkout) and inside the E2B sandbox.
"""
import os
import sys
import tempfile

_here = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.join(_here, "..", "src"), "/home/user/src"):
    if os.path.isdir(_cand):
        sys.path.insert(0, os.path.abspath(_cand))
        break

tmp = tempfile.mkdtemp(prefix="cardwise_rep_")
os.environ["CARDWISE_DB"] = os.path.join(tmp, "r.db")
os.environ["CARDWISE_DATA"] = os.path.join(tmp, "s")

import pandas as pd

from cardwise.analysis import overview, per_statement
from cardwise.db import get_engine, get_session
from cardwise.ingest import ingest_pdf

pdf = sys.argv[1]
eng = get_engine()
ingest_pdf(pdf, get_session(eng))

txns = pd.read_sql(
    "SELECT t.statement_id, t.date, t.description, t.amount, t.txn_type, t.category, s.card_last4 "
    "FROM transactions t JOIN statements s ON s.id = t.statement_id",
    eng, parse_dates=["date"],
)
stmts = pd.read_sql("SELECT * FROM statements", eng, parse_dates=["statement_date", "period_end"])

agg = overview(txns, stmts)
print("=" * 62)
print("SPEND vs REWARDS")
print("=" * 62)
print(f"  Total spend          ₹{agg['total_spend']:>12,.2f}")
print(f"  Eligible spend       ₹{agg['eligible_spend']:>12,.2f}   (fuel + fees excluded)")
print(f"  Rewards earned       ₹{agg['rewards_earned']:>12,.2f}   (statement-reported)")
print(f"  Rewards credited     ₹{agg['rewards_credited']:>12,.2f}   (posted to account)")
print(f"  Payments made        ₹{agg['payments']:>12,.2f}")
print(f"  Return on spend        {agg['return_pct']:>11.2f}%")
print(f"  Net spend            ₹{agg['net_spend']:>12,.2f}")
print(f"  Cashback YTD         ₹{agg['cashback_ytd']:>12,.2f}")
print(f"  Cashback lifetime    ₹{agg['cashback_lifetime']:>12,.2f}")
print()
print("PER STATEMENT")
ps = per_statement(txns, stmts)
print(ps.to_string(index=False))

print()
print("SPEND BY CATEGORY")
d = txns[txns.txn_type == "debit"]
cat = d.groupby("category")["amount"].agg(["sum", "count"]).sort_values("sum", ascending=False)
for name, row in cat.iterrows():
    share = row["sum"] / d.amount.sum() * 100
    print(f"  {name:22} ₹{row['sum']:>9,.2f}  {share:5.1f}%  ({int(row['count'])} txns)")
