"""Rewards parsing + spend/return math."""
import pandas as pd
import pytest

from cardwise.analysis import EXCLUDED_CATEGORIES, is_cashback_credit, overview, per_statement
from cardwise.parsers import parse_pdf


# ---------- real statement: the figures must match what the PDF says ----------
def test_cashback_figures_parsed(pdf_path):
    s = parse_pdf(pdf_path)
    assert s.cashback_earned == 435.0, "this-statement cashback"
    assert s.cashback_ytd == 2502.0, "year-to-date cashback"
    assert s.cashback_lifetime == 4815.0, "lifetime cashback"
    assert s.offer_cashback == 0.0
    assert s.petrol_waiver == 0.0


def test_cashback_credit_is_a_transaction(pdf_path):
    s = parse_pdf(pdf_path)
    cb = [t for t in s.transactions if is_cashback_credit(t.description)]
    assert len(cb) == 1
    assert cb[0].txn_type == "credit"
    assert cb[0].amount == 206.0


# ---------- math on synthetic data ----------
@pytest.fixture
def sample():
    txns = pd.DataFrame([
        # statement 1
        {"statement_id": 1, "txn_type": "debit", "category": "Groceries", "amount": 1000.0,
         "description": "Zepto", "date": pd.Timestamp("2026-09-05")},
        {"statement_id": 1, "txn_type": "debit", "category": "Fuel", "amount": 500.0,
         "description": "BPCL", "date": pd.Timestamp("2026-09-06")},
        {"statement_id": 1, "txn_type": "credit", "category": "Finance & Fees", "amount": 50.0,
         "description": "CARD CASHBACK CREDIT", "date": pd.Timestamp("2026-09-07")},
        {"statement_id": 1, "txn_type": "credit", "category": "Finance & Fees", "amount": 200.0,
         "description": "PAYMENT RECEIVED", "date": pd.Timestamp("2026-09-08")},
    ])
    stmts = pd.DataFrame([
        {"id": 1, "card_last4": "17", "period_end": pd.Timestamp("2026-10-03"),
         "cashback_earned": 100.0, "cashback_ytd": 100.0, "cashback_lifetime": 100.0},
    ])
    return txns, stmts


def test_overview_math(sample):
    txns, stmts = sample
    agg = overview(txns, stmts)
    assert agg["total_spend"] == 1500.0
    assert agg["eligible_spend"] == 1000.0          # fuel excluded
    assert agg["rewards_earned"] == 100.0
    assert agg["rewards_credited"] == 50.0          # only the cashback line
    assert agg["payments"] == 200.0                 # payment is not cashback
    assert agg["return_pct"] == 10.0                # 100 / 1000
    assert agg["net_spend"] == 1450.0


def test_per_statement(sample):
    txns, stmts = sample
    ps = per_statement(txns, stmts)
    assert len(ps) == 1
    row = ps.iloc[0]
    assert row["spend"] == 1500.0
    assert row["eligible"] == 1000.0
    assert row["earned"] == 100.0
    assert row["credited"] == 50.0
    assert row["return_pct"] == 10.0
    assert row["credited_pct"] == 5.0


def test_excluded_categories_are_the_nones():
    assert set(EXCLUDED_CATEGORIES) == {"Fuel", "Finance & Fees"}


def test_empty_input_is_safe():
    empty = pd.DataFrame(columns=["statement_id", "txn_type", "category", "amount", "description"])
    agg = overview(empty, pd.DataFrame())
    assert agg["total_spend"] == 0.0 and agg["return_pct"] == 0.0
    assert per_statement(empty, pd.DataFrame()).empty


def test_cashback_description_variants():
    assert is_cashback_credit("CARD CASHBACK CREDIT")
    assert is_cashback_credit("cash back refund")
    assert not is_cashback_credit("PAYMENT RECEIVED")
    assert not is_cashback_credit("Zepto Bengaluru IND")


def test_dashboard_compiles():
    """Cheap guard: the Streamlit script must at least be valid Python."""
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "src/cardwise/dashboard/app.py"
    compile(path.read_text(), str(path), "exec")
