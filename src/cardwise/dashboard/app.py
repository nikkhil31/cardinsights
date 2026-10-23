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

from cardwise.cashback import channel_for, compute_cashback, rate_for, reload_rates  # noqa: E402
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
           t.channel, t.cashback, t.cashback_rate,
           s.bank, s.card_last4
    FROM transactions t JOIN statements s ON s.id = t.statement_id
    """
    df = pd.read_sql(q, eng, parse_dates=["date"])
    if df.empty:
        return df
    if "channel" not in df.columns:
        df["channel"] = None
    # backfill channel
    from cardwise.cashback import channel_for
    ch_mask = df["channel"].isna() | (df["channel"].astype(str).str.strip() == "")
    if ch_mask.any():
        df.loc[ch_mask, "channel"] = df[ch_mask].apply(
            lambda r: channel_for(r["description"], r["txn_type"]), axis=1
        )
    df["channel"] = df["channel"].fillna("offline")
    if "cashback" not in df.columns:
        df["cashback"] = None
    mask = df["cashback"].isna()
    if mask.any():
        df.loc[mask, "cashback"] = df[mask].apply(
            lambda r: compute_cashback(r["description"], r["category"], r["card_last4"],
                                      r["amount"], r["txn_type"]),
            axis=1,
        )
    df["cashback"] = df["cashback"].fillna(0.0)
    if "cashback_rate" not in df.columns:
        df["cashback_rate"] = None
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
                st.success(f"{res['bank']} ••{res['card_last4']} — {res['inserted']}/{res['transactions']} new txns • est. cashback ₹{res.get('cashback', 0):,.2f}")
        except Exception as e:
            st.error(f"Parse failed: {e}")
        finally:
            os.unlink(tmp_path)

    st.divider()
    if st.button("Recompute cashback"):
        from sqlalchemy import select
        from cardwise.db import Transaction
        from cardwise.categorize import categorize
        sess = _session()
        eng = get_engine()
        rows = sess.query(Transaction).all()
        n = 0
        for t in rows:
            cat = t.category or categorize(t.description)
            t.category = cat
            ch = channel_for(t.description, t.txn_type)
            t.channel = ch
            cb = compute_cashback(t.description, cat, t.statement.card_last4 if t.statement else None, t.amount, t.txn_type)
            t.cashback = cb
            if t.txn_type == "debit":
                t.cashback_rate = rate_for(cat, t.statement.card_last4 if t.statement else None, ch == "online")
            n += 1
        sess.commit()
        reload_rates()
        st.success(f"Recomputed cashback for {n} transactions.")
        st.rerun()
    st.caption("DB at `~/.cardwise/cardwise.db`. Edit `categories.yaml` / `cashback.yaml` to tune.")


# ---------- Main ----------
st.title("💳 CardWise — Credit Card Insights")

df = load_transactions()
stmts = load_statements()

if df.empty:
    st.info("No data yet. Upload a statement from the sidebar.")
    st.stop()

# Filters
col1, col2, col3, col4 = st.columns(4)
with col1:
    months = sorted(df["date"].dt.to_period("M").unique(), reverse=True)
    sel_months = st.multiselect("Month", options=[str(m) for m in months], default=[str(m) for m in months[:1]])
with col2:
    cards = sorted(df["card_last4"].unique())
    sel_cards = st.multiselect("Card (last4)", options=cards, default=cards)
with col3:
    cats = sorted(df["category"].unique())
    sel_cats = st.multiselect("Category", options=cats, default=cats)
with col4:
    chans = sorted(df["channel"].fillna("offline").unique())
    sel_chans = st.multiselect("Channel", options=chans, default=chans)

mask = (
    df["date"].dt.to_period("M").astype(str).isin(sel_months)
    & df["card_last4"].isin(sel_cards)
    & df["category"].isin(sel_cats)
    & df["channel"].fillna("offline").isin(sel_chans)
)
fdf = df[mask]

debits = fdf[fdf["txn_type"] == "debit"]
credits = fdf[fdf["txn_type"] == "credit"]

# KPIs
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total spend", f"₹{debits['amount'].sum():,.0f}")
k2.metric("Credits/payments", f"₹{credits['amount'].sum():,.0f}")
k3.metric("Transactions", len(debits))
latest = stmts.sort_values("statement_date").iloc[-1] if not stmts.empty else None
if latest is not None and pd.notna(latest["total_due"]):
    k4.metric("Latest TAD", f"₹{latest['total_due']:,.0f}")
if latest is not None and pd.notna(latest["credit_limit"]) and latest["credit_limit"]:
    util = (latest["total_due"] or 0) / latest["credit_limit"] * 100
    k5.metric("Utilization", f"{util:.1f}%")
est_cb = debits["cashback"].sum() if "cashback" in debits.columns else 0.0
k6.metric("Est. cashback", f"₹{est_cb:,.2f}")

# Actual cashback received (credit lines)
cb_credits = credits[credits["description"].str.contains("cashback", case=False, na=False)] if not credits.empty else credits
cb_received = cb_credits["amount"].sum() if not cb_credits.empty else 0.0
st.caption(f"Cashback received (statement credits): ₹{cb_received:,.2f} • Net spend after est. cashback: ₹{debits['amount'].sum() - est_cb:,.2f}")

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
    # add estimated cashback per merchant
    cb_map = debits.groupby("description")["cashback"].sum() if "cashback" in debits.columns else None
    if cb_map is not None:
        top["Cashback ₹"] = top["Merchant"].map(cb_map).fillna(0.0).round(2)
    st.dataframe(top, use_container_width=True, hide_index=True)

# Cashback row
cb1, cb2 = st.columns(2)
with cb1:
    st.subheader("Cashback by category (est.)")
    if not debits.empty and "cashback" in debits.columns:
        cbc = debits.groupby("category", as_index=False)["cashback"].sum().sort_values("cashback", ascending=False)
        cbc = cbc[cbc["cashback"] > 0]
        if not cbc.empty:
            st.plotly_chart(px.bar(cbc, x="category", y="cashback", text_auto=".2s"), use_container_width=True)
        else:
            st.info("No estimated cashback for current filters.")
with cb2:
    st.subheader("Cashback by card (est.)")
    if not debits.empty and "cashback" in debits.columns:
        cbc2 = debits.groupby("card_last4", as_index=False)["cashback"].sum().sort_values("cashback", ascending=False)
        cbc2 = cbc2[cbc2["cashback"] > 0]
        if not cbc2.empty:
            st.plotly_chart(px.bar(cbc2, x="card_last4", y="cashback", text_auto=".2s"), use_container_width=True)
        else:
            st.info("No estimated cashback for current filters.")

# Raw table
st.subheader("Transactions")
show = fdf.sort_values("date", ascending=False)[["date", "description", "category", "channel", "amount", "txn_type", "cashback", "card_last4"]]
st.dataframe(show, use_container_width=True, hide_index=True)
