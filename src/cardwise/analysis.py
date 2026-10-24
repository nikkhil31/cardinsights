"""Spend and rewards analysis.

Definitions are explicit so every number on the dashboard can be audited:

  total_spend       sum of debit transactions in scope
  eligible_spend    total_spend minus categories that never earn rewards
                    (Fuel, Finance & Fees) — the correct denominator for a
                    reward rate
  rewards_earned    cashback accrued on the cycle, taken from the statement's
                    own Savings & Benefits section (never estimated)
  rewards_credited  cashback actually posted to the account — ₹ credit lines
                    whose description mentions cashback
  return_pct        rewards_earned / eligible_spend * 100
  net_spend         total_spend - rewards_credited

Cashback accrues one cycle before it is credited, so `rewards_earned` for a
statement and `rewards_credited` on the same statement legitimately differ.
Both are reported rather than netted, so the lag stays visible.
"""
from __future__ import annotations

import pandas as pd

# Categories that never earn rewards; excluded from the reward-rate denominator.
EXCLUDED_CATEGORIES = ("Fuel", "Finance & Fees")


def is_cashback_credit(description: str) -> bool:
    d = (description or "").lower()
    return "cashback" in d or "cash back" in d


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 2) if whole else 0.0


def overview(txns: pd.DataFrame, statements: pd.DataFrame) -> dict:
    """Single-scope totals for the KPI row."""
    if txns is None or txns.empty:
        return {
            "total_spend": 0.0, "eligible_spend": 0.0, "rewards_earned": 0.0,
            "rewards_credited": 0.0, "payments": 0.0, "return_pct": 0.0,
            "credited_pct": 0.0, "net_spend": 0.0, "cashback_ytd": 0.0,
            "cashback_lifetime": 0.0,
        }

    debits = txns[txns["txn_type"] == "debit"]
    credits = txns[txns["txn_type"] == "credit"]

    is_cb = credits["description"].map(is_cashback_credit)
    credited = float(credits.loc[is_cb, "amount"].sum())
    payments = float(credits.loc[~is_cb, "amount"].sum())

    total_spend = float(debits["amount"].sum())
    eligible = float(debits.loc[~debits["category"].isin(EXCLUDED_CATEGORIES), "amount"].sum())

    earned = float(statements["cashback_earned"].fillna(0).sum()) if len(statements) else 0.0
    ytd = float(statements["cashback_ytd"].fillna(0).max()) if len(statements) else 0.0
    lifetime = float(statements["cashback_lifetime"].fillna(0).max()) if len(statements) else 0.0

    return {
        "total_spend": round(total_spend, 2),
        "eligible_spend": round(eligible, 2),
        "rewards_earned": round(earned, 2),
        "rewards_credited": round(credited, 2),
        "payments": round(payments, 2),
        "return_pct": _pct(earned, eligible),
        "credited_pct": _pct(credited, eligible),
        "net_spend": round(total_spend - credited, 2),
        "cashback_ytd": round(ytd, 2),
        "cashback_lifetime": round(lifetime, 2),
    }


def per_statement(txns: pd.DataFrame, statements: pd.DataFrame) -> pd.DataFrame:
    """One row per statement: spend, rewards earned, rewards credited, return %."""
    cols = ["period_end", "card_last4", "spend", "eligible", "earned", "credited",
            "return_pct", "credited_pct"]
    if txns is None or txns.empty or statements is None or statements.empty:
        return pd.DataFrame(columns=cols)

    debits = txns[txns["txn_type"] == "debit"]
    credits = txns[txns["txn_type"] == "credit"]
    cb = credits[credits["description"].map(is_cashback_credit)]

    spend = debits.groupby("statement_id")["amount"].sum()
    eligible = (
        debits[~debits["category"].isin(EXCLUDED_CATEGORIES)]
        .groupby("statement_id")["amount"].sum()
    )
    credited = cb.groupby("statement_id")["amount"].sum()

    rows = []
    for _, s in statements.iterrows():
        sid = s["id"]
        sp = float(spend.get(sid, 0.0))
        el = float(eligible.get(sid, 0.0))
        er = float(s.get("cashback_earned") or 0.0)
        cr = float(credited.get(sid, 0.0))
        rows.append({
            "period_end": s.get("period_end"),
            "card_last4": s.get("card_last4"),
            "spend": round(sp, 2),
            "eligible": round(el, 2),
            "earned": round(er, 2),
            "credited": round(cr, 2),
            "return_pct": _pct(er, el),
            "credited_pct": _pct(cr, el),
        })
    out = pd.DataFrame(rows, columns=cols)
    return out.sort_values("period_end").reset_index(drop=True)
