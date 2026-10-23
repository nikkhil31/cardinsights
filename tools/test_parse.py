"""Run the SBI parser against a real statement and print results + checks."""
import sys

sys.path.insert(0, "/home/user/src")
from cardwise.parsers import sbi

path = sys.argv[1]
print(f"detect: {sbi.detect(path)}")
stmt = sbi.parse(path)

print(f"\n=== HEADER ===")
print(f"bank:            {stmt.bank}")
print(f"card_last4:      {stmt.card_last4}")
print(f"statement_date:  {stmt.statement_date}")
print(f"period:          {stmt.period_start} -> {stmt.period_end}")
print(f"total_due:       {stmt.total_due}")
print(f"min_due:         {stmt.min_due}")
print(f"credit_limit:    {stmt.credit_limit}")
print(f"prev_balance:    {stmt.previous_balance}")
print(f"payments/credits:{stmt.payments_credits}")
print(f"purchases/debits:{stmt.purchases_debits}")

print(f"\n=== TRANSACTIONS ({len(stmt.transactions)}) ===")
for t in stmt.transactions:
    print(f"  {t.date}  {t.txn_type:6}  {t.amount:>10,.2f}  {t.description}")

# Cross-check against statement's own summary
credits = sum(t.amount for t in stmt.transactions if t.txn_type == "credit")
debits = sum(t.amount for t in stmt.transactions if t.txn_type == "debit")
print(f"\n=== CROSS-CHECK ===")
print(f"sum credits (parsed): {credits:,.2f}   statement says: {stmt.payments_credits}")
print(f"sum debits  (parsed): {debits:,.2f}   statement says: {stmt.purchases_debits}")
ok_c = stmt.payments_credits is None or abs(credits - stmt.payments_credits) < 0.01
ok_d = stmt.purchases_debits is None or abs(debits - stmt.purchases_debits) < 0.01
print(f"credits match: {ok_c}   debits match: {ok_d}")
