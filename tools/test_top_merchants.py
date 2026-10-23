"""Reproduce the dashboard top-merchants code path against the real DB."""
import os
import sys
import tempfile

sys.path.insert(0, "/home/user/src")

tmp = tempfile.mkdtemp(prefix="cardwise_test_")
os.environ["CARDWISE_DB"] = os.path.join(tmp, "test.db")
os.environ["CARDWISE_DATA"] = os.path.join(tmp, "statements")

import pandas as pd
from cardwise.db import get_engine, get_session
from cardwise.ingest import ingest_pdf

pdf_path = sys.argv[1]
eng = get_engine()
ingest_pdf(pdf_path, get_session(eng))

df = pd.read_sql(
    "SELECT t.date, t.description, t.amount, t.txn_type, t.category, s.card_last4 "
    "FROM transactions t JOIN statements s ON s.id = t.statement_id",
    eng, parse_dates=["date"],
)
debits = df[df.txn_type == "debit"]

# Exact code from app.py
top = (
    debits.groupby("description")["amount"]
    .agg(Total="sum", Txns="count")
    .reset_index()
    .sort_values("Total", ascending=False)
    .head(10)
)
top.columns = ["Merchant", "Total ₹", "Txns"]
print(top.to_string(index=False))
print(f"\nOK: shape {top.shape}, columns {list(top.columns)}")
