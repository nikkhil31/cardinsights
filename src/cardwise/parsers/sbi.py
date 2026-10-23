"""SBI Card statement parser.

SBI e-statements are machine-generated PDFs with a text layer. Transactions
appear on the account page as rows like:

    03 Sep 26 RAZ*Zomato Online Orde Gurgaon IND 164.33 D
    19 Sep 26 PAYMENT RECEIVED 000DP0162621759273OF1fE 4,117.00 C

Strategy: pull the text layer with pdfplumber, regex the transaction rows,
and grab summary fields (total due, limits, period) with targeted regexes.
"""
from __future__ import annotations

import re
from datetime import date

import pdfplumber

from .base import ParsedStatement, Transaction

BANK = "SBI"
_DETECT_RE = re.compile(r"(SBI Card|SBICPSL|sbicard\.com)", re.IGNORECASE)

# 03 Sep 26 RAZ*Zomato Online Orde Gurgaon IND 164.33 D
_TXN_RE = re.compile(
    r"^(\d{2}\s[A-Za-z]{3}\s\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+(C|D)\s*$"
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(s: str, default_year: int | None = None) -> date:
    """'03 Sep 26' or '03 Oct 2026' -> date."""
    d, mon, yy = s.split()
    y = int(yy)
    year = 2000 + y if y < 100 else y
    return date(year, _MONTHS[mon.lower()], int(d))


def _parse_period_date(s: str, ref_year: int) -> date:
    """'04 Sep 26' (statement period dates) -> date."""
    return _parse_date(s)


def _money(s: str) -> float:
    return float(s.replace(",", "").replace("`", "").strip())


def _full_text(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n".join(parts)


def detect(path: str) -> bool:
    """True if this PDF looks like an SBI Card statement."""
    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return False
            text = pdf.pages[0].extract_text() or ""
        return bool(_DETECT_RE.search(text))
    except Exception:
        return False


def parse(path: str) -> ParsedStatement:
    text = _full_text(path)
    lines = [ln.strip() for ln in text.splitlines()]

    stmt = ParsedStatement(
        bank=BANK,
        card_last4="",
        statement_date=None,
        period_start=None,
        period_end=None,
        total_due=None,
        min_due=None,
        credit_limit=None,
        previous_balance=None,
        purchases_debits=None,
        payments_credits=None,
    )

    # Card last4: "XXXX XXXX XXXX XX17"
    m = re.search(r"X{4}\sX{4}\sX{4}\sX{2}(\d{2})", text)
    if m:
        stmt.card_last4 = m.group(1)

    # Statement date: "Statement Date\n2,74,000.00 79,460.00 03 Oct 2026"
    m = re.search(r"Statement Date[^\n]*\n[\d,\.]+\s+[\d,\.]+\s+(\d{2}\s\w{3}\s\d{4})", text)
    if m:
        stmt.statement_date = _parse_date(m.group(1))

    # Statement period: "for Statement Period: 04 Sep 26 to 03 Oct 26"
    m = re.search(
        r"Statement Period:\s*(\d{2}\s\w{3}\s\d{2})\s*to\s*(\d{2}\s\w{3}\s\d{2})",
        text,
    )
    if m:
        stmt.period_start = _parse_period_date(m.group(1), 2000)
        stmt.period_end = _parse_period_date(m.group(2), 2000)

    # Totals & limits
    m = re.search(r"Total Amount Due\s*\(?\s*`?\s*\)?\s*\n?([\d,]+\.\d{2})", text)
    if m:
        stmt.total_due = _money(m.group(1))

    m = re.search(r"Minimum Amount Due.*?\n.*?([\d,]+\.\d{2})", text, re.DOTALL)
    if m:
        stmt.min_due = _money(m.group(1))

    # Credit limit: line after "Credit Limit( ` ) ... Cash Limit ... Statement Date"
    m = re.search(r"Credit Limit.*?Statement Date\n([\d,]+\.\d{2})", text, re.DOTALL)
    if m:
        stmt.credit_limit = _money(m.group(1))

    # Account summary row: prev balance, payments/credits, purchases/debits, interest, total
    # "4,117.18 4,323.00 9,486.92 0.00 9,281.00"
    m = re.search(
        r"ACCOUNT SUMMARY.*?\n(?:.*?\n)*?([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+"
        r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
        text,
    )
    if m:
        stmt.previous_balance = _money(m.group(1))
        stmt.payments_credits = _money(m.group(2))
        stmt.purchases_debits = _money(m.group(3))

    # Transactions
    for ln in lines:
        m = _TXN_RE.match(ln)
        if not m:
            continue
        date_s, desc, amt_s, dc = m.groups()
        # Skip the summary-looking rows that match pattern but aren't txns
        if "STATEMENT PERIOD" in desc.upper():
            continue
        stmt.transactions.append(
            Transaction(
                date=_parse_date(date_s),
                description=" ".join(desc.split()),
                amount=_money(amt_s),
                txn_type="credit" if dc == "C" else "debit",
            )
        )

    return stmt
