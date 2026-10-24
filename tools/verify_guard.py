"""Mutation check: break the parser, confirm the reconciliation guards FAIL.

Runs inside E2B. Mutates the sandbox copy of sbi.py only.
"""
import pathlib
import sys

sys.path.insert(0, "/home/user/src")

import pytest

pdf = sys.argv[1]
parser = pathlib.Path("/home/user/src/cardwise/parsers/sbi.py")
original = parser.read_text()

# Mutation: silently drop the last transaction (a classic parser regression)
mutated = original.replace(
    "    return stmt",
    "    stmt.transactions = stmt.transactions[:-1]\n    return stmt",
)
assert mutated != original, "mutation did not apply"
parser.write_text(mutated)

print("--- running suite against MUTATED parser (expect failures) ---")
code = pytest.main(["-q", "/home/user/tests", f"--pdf={pdf}", "-k", "reconcile or transactions_found"])
parser.write_text(original)

print(f"\nmutation run exit code: {code} (non-zero = guards have teeth)")
sys.exit(0 if code != 0 else 1)
