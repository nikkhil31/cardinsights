"""Shared types for bank parsers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Transaction:
    date: date
    description: str
    amount: float          # positive number, sign carried by txn_type
    txn_type: str          # "debit" | "credit"


@dataclass
class ParsedStatement:
    bank: str
    card_last4: str
    statement_date: date | None
    period_start: date | None
    period_end: date | None
    total_due: float | None
    min_due: float | None
    credit_limit: float | None
    previous_balance: float | None
    purchases_debits: float | None
    payments_credits: float | None
    # rewards, as reported by the statement itself (no estimation)
    cashback_earned: float | None = None      # accrued on this statement
    cashback_ytd: float | None = None         # accrued this calendar year
    cashback_lifetime: float | None = None    # since card issue
    offer_cashback: float | None = None       # promotional cashback, this statement
    petrol_waiver: float | None = None        # fuel surcharge waiver, this statement
    transactions: list[Transaction] = field(default_factory=list)
