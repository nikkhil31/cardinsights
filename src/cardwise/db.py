"""Storage layer via SQLAlchemy — SQLite by default, Postgres via DATABASE_URL."""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime

from sqlalchemy import (Date, DateTime, Float, ForeignKey, Integer, String,
                        UniqueConstraint, create_engine, inspect, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DB_PATH = os.environ.get("CARDWISE_DB", os.path.expanduser("~/.cardwise/cardwise.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


class Base(DeclarativeBase):
    pass


class Statement(Base):
    __tablename__ = "statements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank: Mapped[str] = mapped_column(String(32))
    card_last4: Mapped[str] = mapped_column(String(8))
    statement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_due: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_due: Mapped[float | None] = mapped_column(Float, nullable=True)
    credit_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchases_debits: Mapped[float | None] = mapped_column(Float, nullable=True)
    payments_credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_txn_fp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id"))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(256))
    amount: Mapped[float] = mapped_column(Float)
    txn_type: Mapped[str] = mapped_column(String(8))  # debit | credit
    category: Mapped[str] = mapped_column(String(64), default="Other")
    channel: Mapped[str | None] = mapped_column(String(8), nullable=True, default="offline")
    cashback: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    cashback_rate: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    fingerprint: Mapped[str] = mapped_column(String(64))

    statement: Mapped[Statement] = relationship(back_populates="transactions")


def make_fingerprint(d: date, desc: str, amount: float, txn_type: str) -> str:
    return hashlib.sha256(f"{d.isoformat()}|{desc}|{amount:.2f}|{txn_type}".encode()).hexdigest()


_ADDITIVE_COLUMNS: dict[str, dict[str, object]] = {
    "transactions": {
        "channel": String(8),
        "cashback": Float(),
        "cashback_rate": Float(),
    },
}


def _migrate(engine) -> None:
    """Lightweight additive migration (create_all won't alter existing tables).

    Types are compiled for the active dialect so this works on SQLite and Postgres.
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for table, cols in _ADDITIVE_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        missing = [(n, t) for n, t in cols.items() if n not in existing]
        if not missing:
            continue
        with engine.begin() as conn:
            for name, typ in missing:
                ddl_type = typ.compile(dialect=engine.dialect)
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def _resolve_url(path: str | None = None) -> str:
    """Pick the DB URL: explicit path/URL > DATABASE_URL > local SQLite file."""
    if path and "://" in path:
        return path
    if path:
        return f"sqlite:///{path}"
    if DATABASE_URL:
        # normalise Heroku/Render-style schemes to the psycopg3 driver
        for prefix in ("postgres://", "postgresql://"):
            if DATABASE_URL.startswith(prefix):
                return "postgresql+psycopg://" + DATABASE_URL[len(prefix):]
        return DATABASE_URL
    return f"sqlite:///{DB_PATH}"


def get_engine(path: str | None = None):
    url = _resolve_url(path)
    kwargs: dict = {}
    if url.startswith("sqlite"):
        fs_path = url.replace("sqlite:///", "", 1)
        parent = os.path.dirname(fs_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    else:
        kwargs = {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
    eng = create_engine(url, **kwargs)
    Base.metadata.create_all(eng)
    _migrate(eng)
    return eng


def get_session(engine):
    return sessionmaker(bind=engine)()
