"""Parser reconciliation: parsed rows must match the statement's own totals.

This is the guard that catches a bank layout change. Without it a parser can
silently return fewer transactions and still look healthy.

Run with a real statement:  pytest tests/ --pdf=/path/to/statement.pdf
"""
from datetime import date

import pytest

from cardwise.parsers import parse_pdf
from cardwise.parsers import sbi


@pytest.fixture
def statement(pdf_path):
    return parse_pdf(pdf_path)


def test_parser_detected(statement):
    assert statement.bank == "SBI"
    assert statement.card_last4, "card last4 not extracted"


def test_transactions_found(statement):
    assert len(statement.transactions) > 0, "parser returned no transactions"


def test_header_fields_extracted(statement):
    assert isinstance(statement.statement_date, date)
    assert isinstance(statement.period_start, date)
    assert isinstance(statement.period_end, date)
    assert statement.period_start < statement.period_end
    assert statement.total_due is not None and statement.total_due > 0
    assert statement.credit_limit is not None and statement.credit_limit > 0


def test_debits_reconcile(statement):
    """Sum of parsed debits must equal the statement's 'Purchases & Other Debits'."""
    parsed = sum(t.amount for t in statement.transactions if t.txn_type == "debit")
    assert statement.purchases_debits is not None, "statement total not parsed"
    assert abs(parsed - statement.purchases_debits) < 0.01, (
        f"debit mismatch: parsed {parsed:.2f} vs statement {statement.purchases_debits:.2f}"
    )


def test_credits_reconcile(statement):
    """Sum of parsed credits must equal the statement's 'Payments & Credits'."""
    parsed = sum(t.amount for t in statement.transactions if t.txn_type == "credit")
    assert statement.payments_credits is not None, "statement total not parsed"
    assert abs(parsed - statement.payments_credits) < 0.01, (
        f"credit mismatch: parsed {parsed:.2f} vs statement {statement.payments_credits:.2f}"
    )


def test_transaction_fields_sane(statement):
    for t in statement.transactions:
        assert t.txn_type in ("debit", "credit")
        assert t.amount > 0
        assert t.description.strip(), "empty description"
        assert isinstance(t.date, date)
        # transactions must fall in or just before the billing period
        assert t.date <= statement.period_end


def test_detect_rejects_non_sbi(tmp_path):
    """A non-SBI PDF should not be claimed by the SBI parser."""
    fake = tmp_path / "not_a_statement.pdf"
    # minimal valid PDF with no SBI markers
    fake.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    assert sbi.detect(str(fake)) is False
