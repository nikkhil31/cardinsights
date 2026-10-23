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
    transactions: list[Transaction] = field(default_factory=list)
