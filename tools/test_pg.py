"""Verify the Postgres backend end-to-end (runs inside E2B sandbox as root)."""
import os
import sys

sys.path.insert(0, "/home/user/src")

import pandas as pd
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from cardwise.db import _resolve_url, get_engine, get_session
from cardwise.ingest import ingest_pdf

pdf = sys.argv[1]
failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
    if not cond:
        failures.append(name)


# 0. URL resolution
resolved = _resolve_url()
check("resolve DATABASE_URL -> psycopg", resolved.startswith("postgresql+psycopg://"), resolved.split("@")[-1])

# 1. schema creation
eng = get_engine()
tables = set(sa_inspect(eng).get_table_names())
check("tables created", {"statements", "transactions"} <= tables, str(sorted(tables)))
with eng.connect() as c:
    print("  server:", c.execute(text("select version()")).scalar().split(",")[0])

# 2. ingest
s = get_session(eng)
r1 = ingest_pdf(pdf, s)
check("ingest ok", r1["status"] == "ok", f"inserted {r1.get('inserted')}/{r1.get('transactions')}")

# 3. dedup on re-ingest
r2 = ingest_pdf(pdf, s)
check("re-ingest skipped", r2["status"] == "skipped")

# 4. dashboard query path
df = pd.read_sql(
    "SELECT t.date, t.description, t.amount, t.txn_type, t.category, s.card_last4 "
    "FROM transactions t JOIN statements s ON s.id = t.statement_id",
    eng,
    parse_dates=["date"],
)
check("rows via read_sql", len(df) == 16, f"{len(df)} rows")
debits = df[df.txn_type == "debit"]
check("debit sum matches statement", abs(debits.amount.sum() - 9486.92) < 0.01, f"{debits.amount.sum():.2f}")
check("categories assigned", (df.category != "").all(), str(df.category.nunique()) + " distinct")

# 5. column types on PG
cols = {c["name"].lower(): str(c["type"]) for c in sa_inspect(eng).get_columns("transactions")}
check("expected columns only", set(cols) == {
    "id", "statement_id", "date", "description", "amount", "txn_type", "category", "fingerprint"
}, str(sorted(cols)))
check("date is a date column", "DATE" in cols.get("date", "").upper(), cols.get("date", ""))

# 6. sqlite path still works (regression)
eng_sqlite = get_engine("/tmp/cardwise_regress.db")
check("sqlite still works", eng_sqlite.url.get_backend_name() == "sqlite", str(eng_sqlite.url))

print("\n" + ("ALL CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
