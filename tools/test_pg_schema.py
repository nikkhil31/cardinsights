"""Live Postgres check: fresh schema -> ingest -> rewards persisted -> aggregates.

Deliberately no ALTER TABLE here: dropping columns on a table that another
connection may reference takes an ACCESS EXCLUSIVE lock and hangs. The additive
migration is covered by SQLite/PG DDL checks elsewhere.
"""
import os
import sys

sys.path.insert(0, "/home/user/src")

import pandas as pd
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from cardwise.analysis import overview
from cardwise.db import get_engine, get_session
from cardwise.ingest import ingest_pdf

pdf = sys.argv[1]
failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}", flush=True)
    if not cond:
        failures.append(name)


eng = get_engine()
with eng.connect() as c:
    print("server:", c.execute(text("select version()")).scalar().split(",")[0], flush=True)

# 1. fresh schema carries the reward columns
scols = {c["name"]: str(c["type"]) for c in sa_inspect(eng).get_columns("statements")}
check("reward columns in PG schema",
      {"cashback_earned", "cashback_ytd", "cashback_lifetime", "offer_cashback", "petrol_waiver"} <= set(scols),
      str(sorted(scols)))
check("earned is double precision", "DOUBLE PRECISION" in scols.get("cashback_earned", "").upper()
      or "FLOAT" in scols.get("cashback_earned", "").upper(), scols.get("cashback_earned", ""))

# 2. ingest persists statement-reported cashback
s = get_session(eng)
r1 = ingest_pdf(pdf, s)
check("ingest ok", r1["status"] == "ok", f"inserted {r1.get('inserted')}/{r1.get('transactions')}")
check("re-ingest skipped", ingest_pdf(pdf, s)["status"] == "skipped")

stmts = pd.read_sql("SELECT * FROM statements", eng)
check("cashback_earned", float(stmts.cashback_earned.iloc[0]) == 435.0, str(stmts.cashback_earned.iloc[0]))
check("cashback_ytd", float(stmts.cashback_ytd.iloc[0]) == 2502.0, str(stmts.cashback_ytd.iloc[0]))
check("cashback_lifetime", float(stmts.cashback_lifetime.iloc[0]) == 4815.0, str(stmts.cashback_lifetime.iloc[0]))

# 3. aggregates match the SQLite report exactly
txns = pd.read_sql(
    "SELECT t.statement_id, t.date, t.description, t.amount, t.txn_type, t.category, s.card_last4 "
    "FROM transactions t JOIN statements s ON s.id = t.statement_id",
    eng, parse_dates=["date"],
)
agg = overview(txns, stmts)
check("total spend", abs(agg["total_spend"] - 9486.92) < 0.01, f"{agg['total_spend']:.2f}")
check("eligible spend", abs(agg["eligible_spend"] - 8816.13) < 0.01, f"{agg['eligible_spend']:.2f}")
check("rewards credited", abs(agg["rewards_credited"] - 206.0) < 0.01, f"{agg['rewards_credited']:.2f}")
check("return pct", agg["return_pct"] == 4.93, f"{agg['return_pct']}%")
check("net spend", abs(agg["net_spend"] - 9280.92) < 0.01, f"{agg['net_spend']:.2f}")

s.close()
print("\n" + ("ALL CHECKS PASSED" if not failures else f"FAILURES: {failures}"), flush=True)
sys.exit(1 if failures else 0)
