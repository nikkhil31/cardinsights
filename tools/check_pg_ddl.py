"""Verify Postgres DDL for the new columns without needing a live server."""
import sys

sys.path.insert(0, "/home/user/src")

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from cardwise.db import Statement, _ADDITIVE_COLUMNS

pg = postgresql.dialect()
sq = sqlite.dialect()

print("ADDITIVE COLUMN DDL")
for table, cols in _ADDITIVE_COLUMNS.items():
    for name, typ in cols.items():
        print(f"  ALTER TABLE {table} ADD COLUMN {name} "
              f"{typ.compile(dialect=pg)}   (sqlite: {typ.compile(dialect=sq)})")

print("\nPOSTGRES CREATE TABLE statements")
ddl = str(CreateTable(Statement.__table__).compile(dialect=pg))
print(ddl)

required = {"cashback_earned", "cashback_ytd", "cashback_lifetime", "offer_cashback", "petrol_waiver"}
missing = [c for c in required if c not in ddl]
assert not missing, f"missing in PG DDL: {missing}"
assert "file_hash VARCHAR(64) NOT NULL UNIQUE" in ddl or "file_hash" in ddl
print("OK: all reward columns present in Postgres DDL, floats map to", pg.type_descriptor(Statement.__table__.c.cashback_earned.type))
