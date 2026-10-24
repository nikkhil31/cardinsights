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

from cardwise.analysis import overview, per_statement  # noqa: E402
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
    SELECT t.statement_id, t.date, t.description, t.amount, t.txn_type, t.category,
           s.bank, s.card_last4
    FROM transactions t JOIN statements s ON s.id = t.statement_id
    """
    return pd.read_sql(q, eng, parse_dates=["date"])


def load_statements() -> pd.DataFrame:
    eng = get_engine()
    return pd.read_sql(
        "SELECT * FROM statements",
        eng,
        parse_dates=["statement_date", "period_start", "period_end"],
    )


def rupees(x: float) -> str:
    return f"₹{x:,.0f}"


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
                st.cache_data.clear()
        except Exception as e:
            st.error(f"Parse failed: {e}")
        finally:
            os.unlink(tmp_path)

    st.divider()
    st.caption("DB at `~/.cardwise/cardwise.db`. Edit `categories.yaml` to tune categorization.")


# ---------- Main ----------
st.title("💳 CardWise — spend & rewards")

df = load_transactions()
stmts = load_statements()

if df.empty:
    st.info("No data yet. Upload a statement from the sidebar.")
    st.stop()

# Filters — default to everything so the view answers "what have I spent so far"
col1, col2, col3 = st.columns(3)
with col1:
    months = sorted(df["date"].dt.to_period("M").astype(str).unique(), reverse=True)
    sel_months = st.multiselect("Month", options=months, default=months)
with col2:
    cards = sorted(df["card_last4"].unique())
    sel_cards = st.multiselect("Card (last4)", options=cards, default=cards)
with col3:
    cats = sorted(df["category"].unique())
    sel_cats = st.multiselect("Category", options=cats, default=cats)

month_sel = sel_months or months
card_sel = sel_cards or cards
cat_sel = sel_cats or cats

mask = (
    df["date"].dt.to_period("M").astype(str).isin(month_sel)
    & df["card_last4"].isin(card_sel)
    & df["category"].isin(cat_sel)
)
fdf = df[mask]
fstmts = stmts[stmts["id"].isin(fdf["statement_id"].unique())]

debits = fdf[fdf["txn_type"] == "debit"]

# ---------- Headline: spend vs what came back ----------
st.subheader("Spend vs rewards")
agg = overview(fdf, fstmts)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total spend", rupees(agg["total_spend"]), help="All debit transactions in the current filter")
k2.metric("Rewards earned", rupees(agg["rewards_earned"]),
          help="Cashback accrued this cycle, as reported by the statement (Savings & Benefits)")
k3.metric("Rewards credited", rupees(agg["rewards_credited"]),
          help="Cashback actually posted as ₹ credits on the account")
k4.metric("Return on spend", f"{agg['return_pct']:.2f}%",
          help=f"Rewards earned ÷ eligible spend (₹{agg['eligible_spend']:,.0f}). "
               "Fuel and fees/interest are excluded — they earn nothing.")
k5.metric("Net spend", rupees(agg["net_spend"]), help="Total spend minus cashback credited")

st.caption(
    f"Eligible spend {rupees(agg['eligible_spend'])} · payments made {rupees(agg['payments'])} · "
    f"cashback this year {rupees(agg['cashback_ytd'])} · lifetime {rupees(agg['cashback_lifetime'])}. "
    "Cashback accrues one cycle before it is credited, so earned and credited normally differ."
)

# Per-statement breakdown
ps = per_statement(fdf, fstmts)
if not ps.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Spend vs cashback per statement**")
        melt = ps.melt(
            id_vars=["period_end"],
            value_vars=["spend", "earned"],
            var_name="series",
            value_name="amount",
        )
        melt["series"] = melt["series"].map({"spend": "Spend", "earned": "Cashback earned"})
        st.plotly_chart(
            px.bar(melt, x="period_end", y="amount", color="series", barmode="group",
                   text_auto=".3s"),
            use_container_width=True,
        )
    with c2:
        st.markdown("**Return rate per statement**")
        st.plotly_chart(
            px.line(ps, x="period_end", y="return_pct", markers=True,
                    labels={"return_pct": "return %", "period_end": "statement"}),
            use_container_width=True,
        )

    st.markdown("**Statement detail**")
    show_ps = ps.rename(columns={
        "period_end": "Statement",
        "card_last4": "Card",
        "spend": "Spend ₹",
        "eligible": "Eligible ₹",
        "earned": "Cashback earned ₹",
        "credited": "Cashback credited ₹",
        "return_pct": "Return %",
        "credited_pct": "Credited %",
    })
    st.dataframe(show_ps, use_container_width=True, hide_index=True)

st.divider()

# ---------- Spend breakdown ----------
st.subheader("Where the money went")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**By category**")
    cat = debits.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    st.plotly_chart(px.pie(cat, values="amount", names="category", hole=0.4), use_container_width=True)
with c2:
    st.markdown("**By month**")
    trend = debits.copy()
    trend["month"] = trend["date"].dt.to_period("M").astype(str)
    tr = trend.groupby("month", as_index=False)["amount"].sum()
    st.plotly_chart(px.bar(tr, x="month", y="amount", text_auto=".2s"), use_container_width=True)

c3, c4 = st.columns(2)
with c3:
    st.markdown("**Per card**")
    pc = debits.groupby("card_last4", as_index=False)["amount"].sum()
    st.plotly_chart(px.bar(pc, x="card_last4", y="amount", text_auto=".2s"), use_container_width=True)
with c4:
    st.markdown("**Top merchants**")
    top = (
        debits.groupby("description")["amount"]
        .agg(Total="sum", Txns="count")
        .reset_index()
        .sort_values("Total", ascending=False)
        .head(10)
    )
    top.columns = ["Merchant", "Total ₹", "Txns"]
    st.dataframe(top, use_container_width=True, hide_index=True)

# ---------- Card status ----------
if not fstmts.empty:
    st.divider()
    st.subheader("Card status (latest statement)")
    latest = fstmts.sort_values("statement_date").iloc[-1]
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total amount due", rupees(latest["total_due"] or 0))
    s2.metric("Minimum due", rupees(latest["min_due"] or 0))
    s3.metric("Credit limit", rupees(latest["credit_limit"] or 0))
    if latest["credit_limit"]:
        s4.metric("Utilization", f"{(latest['total_due'] or 0) / latest['credit_limit'] * 100:.1f}%")

# ---------- Raw table ----------
st.divider()
st.subheader("Transactions")
show = fdf.sort_values("date", ascending=False)[
    ["date", "description", "category", "amount", "txn_type", "card_last4"]
]
st.dataframe(show, use_container_width=True, hide_index=True)
