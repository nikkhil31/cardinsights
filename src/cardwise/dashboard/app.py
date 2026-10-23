"""CardWise Streamlit dashboard — run: streamlit run src/cardwise/dashboard/app.py"""
from __future__ import annotations

import os
import sys
import tempfile

import pandas as pd
import plotly.express as px
import streamlit as st

# Make `cardwise` importable when run as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cardwise.db import get_engine, get_session  # noqa: E402
from cardwise.ingest import ingest_pdf  # noqa: E402

st.set_page_config(page_title="CardWise", page_icon="💳", layout="wide")


@st.cache_resource
def _session():
    eng = get_engine()
    return get_session(eng)


def load_transactions() -> pd.DataFrame:
    eng = get_engine()
    q = """
    SELECT t.date, t.description, t.amount, t.txn_type, t.category,
           s.bank, s.card_last4
    FROM transactions t JOIN statements s ON s.id = t.statement_id
    """
    df = pd.read_sql(q, eng, parse_dates=["date"])
    return df


def load_statements() -> pd.DataFrame:
    eng = get_engine()
    return pd.read_sql("SELECT * FROM statements", eng, parse_dates=["statement_date", "period_start", "period_end"])


# ---------- Sidebar: upload ----------
with st.sidebar:
    st.header("📤 Upload statement")
    uploaded = st.file_uploader("SBI PDF", type=["pdf"])
    if uploaded and st.button("Ingest"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = tmp.name
        try:
            res = ingest_pdf(tmp_path, _session())
            if res["status"] == "skipped":
                st.info("Already ingested.")
            else:
                st.success(f"{res['bank']} ••{res['card_last4']} — {res['inserted']}/{res['transactions']} new txns")
        except Exception as e:
            st.error(f"Parse failed: {e}")
        finally:
            os.unlink(tmp_path)

    st.divider()
    st.caption("DB at `~/.cardwise/cardwise.db`. Edit `categories.yaml` to tune categorization.")


# ---------- Main ----------
st.title("💳 CardWise — Credit Card Insights")

df = load_transactions()
stmts = load_statements()

if df.empty:
    st.info("No data yet. Upload a statement from the sidebar.")
    st.stop()

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    months = sorted(df["date"].dt.to_period("M").unique(), reverse=True)
    sel_months = st.multiselect("Month", options=[str(m) for m in months], default=[str(m) for m in months[:1]])
with col2:
    cards = sorted(df["card_last4"].unique())
    sel_cards = st.multiselect("Card (last4)", options=cards, default=cards)
with col3:
    cats = sorted(df["category"].unique())
    sel_cats = st.multiselect("Category", options=cats, default=cats)

mask = (
    df["date"].dt.to_period("M").astype(str).isin(sel_months)
    & df["card_last4"].isin(sel_cards)
    & df["category"].isin(sel_cats)
)
fdf = df[mask]

debits = fdf[fdf["txn_type"] == "debit"]
credits = fdf[fdf["txn_type"] == "credit"]

# KPIs
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total spend", f"₹{debits['amount'].sum():,.0f}")
k2.metric("Credits/payments", f"₹{credits['amount'].sum():,.0f}")
k3.metric("Transactions", len(debits))
latest = stmts.sort_values("statement_date").iloc[-1] if not stmts.empty else None
if latest is not None and pd.notna(latest["total_due"]):
    k4.metric("Latest TAD", f"₹{latest['total_due']:,.0f}")
if latest is not None and pd.notna(latest["credit_limit"]) and latest["credit_limit"]:
    util = (latest["total_due"] or 0) / latest["credit_limit"] * 100
    k5.metric("Utilization", f"{util:.1f}%")

st.divider()

# Charts row 1
c1, c2 = st.columns(2)
with c1:
    st.subheader("Spend by category")
    cat = debits.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    st.plotly_chart(px.pie(cat, values="amount", names="category", hole=0.4), use_container_width=True)
with c2:
    st.subheader("Monthly trend")
    trend = debits.copy()
    trend["month"] = trend["date"].dt.to_period("M").astype(str)
    tr = trend.groupby("month", as_index=False)["amount"].sum()
    st.plotly_chart(px.bar(tr, x="month", y="amount", text_auto=".2s"), use_container_width=True)

# Charts row 2
c3, c4 = st.columns(2)
with c3:
    st.subheader("Per-card spend")
    pc = debits.groupby("card_last4", as_index=False)["amount"].sum()
    st.plotly_chart(px.bar(pc, x="card_last4", y="amount", text_auto=".2s"), use_container_width=True)
with c4:
    st.subheader("Top merchants")
    top = (
        debits.groupby("description")["amount"]
        .agg(Total="sum", Txns="count")
        .reset_index()
        .sort_values("Total", ascending=False)
        .head(10)
    )
    top.columns = ["Merchant", "Total ₹", "Txns"]
    st.dataframe(top, use_container_width=True, hide_index=True)

# Raw table
st.subheader("Transactions")
show = fdf.sort_values("date", ascending=False)[["date", "description", "category", "amount", "txn_type", "card_last4"]]
st.dataframe(show, use_container_width=True, hide_index=True)
