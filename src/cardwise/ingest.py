"""Ingest a PDF: hash, detect bank, parse, store."""
from __future__ import annotations

import hashlib
import os
import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categorize import categorize
from .db import Statement, Transaction, make_fingerprint
from .parsers import parse_pdf

def _data_dir() -> str:
    return os.environ.get("CARDWISE_DATA", os.path.expanduser("~/.cardwise/statements"))


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_pdf(pdf_path: str, session: Session, archive: bool = True) -> dict:
    """Parse + store. Returns summary dict; raises on unknown bank."""
    fh = file_sha256(pdf_path)
    if session.scalar(select(Statement).where(Statement.file_hash == fh)):
        return {"status": "skipped", "reason": "already ingested", "file_hash": fh}

    stmt = parse_pdf(pdf_path)

    row = Statement(
        bank=stmt.bank,
        card_last4=stmt.card_last4,
        statement_date=stmt.statement_date,
        period_start=stmt.period_start,
        period_end=stmt.period_end,
        total_due=stmt.total_due,
        min_due=stmt.min_due,
        credit_limit=stmt.credit_limit,
        previous_balance=stmt.previous_balance,
        purchases_debits=stmt.purchases_debits,
        payments_credits=stmt.payments_credits,
        cashback_earned=stmt.cashback_earned,
        cashback_ytd=stmt.cashback_ytd,
        cashback_lifetime=stmt.cashback_lifetime,
        offer_cashback=stmt.offer_cashback,
        petrol_waiver=stmt.petrol_waiver,
        file_hash=fh,
    )
    session.add(row)
    session.flush()

    inserted = 0
    for t in stmt.transactions:
        fp = make_fingerprint(t.date, t.description, t.amount, t.txn_type)
        if session.scalar(select(Transaction).where(Transaction.fingerprint == fp)):
            continue
        session.add(
            Transaction(
                statement_id=row.id,
                date=t.date,
                description=t.description,
                amount=t.amount,
                txn_type=t.txn_type,
                category=categorize(t.description),
                fingerprint=fp,
            )
        )
        inserted += 1

    session.commit()

    if archive:
        dd = _data_dir()
        os.makedirs(dd, exist_ok=True)
        dst = os.path.join(dd, os.path.basename(pdf_path))
        if os.path.abspath(dst) != os.path.abspath(pdf_path):
            shutil.copy2(pdf_path, dst)

    return {
        "status": "ok",
        "bank": stmt.bank,
        "card_last4": stmt.card_last4,
        "statement_date": str(stmt.statement_date),
        "transactions": len(stmt.transactions),
        "inserted": inserted,
        "total_due": stmt.total_due,
    }
