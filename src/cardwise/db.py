"""SQLite storage layer via SQLAlchemy."""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime

from sqlalchemy import (Date, DateTime, Float, ForeignKey, Integer, String,
                        UniqueConstraint, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DB_PATH = os.environ.get("CARDWISE_DB", os.path.expanduser("~/.cardwise/cardwise.db"))


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
    fingerprint: Mapped[str] = mapped_column(String(64))

    statement: Mapped[Statement] = relationship(back_populates="transactions")


def make_fingerprint(d: date, desc: str, amount: float, txn_type: str) -> str:
    return hashlib.sha256(f"{d.isoformat()}|{desc}|{amount:.2f}|{txn_type}".encode()).hexdigest()


def get_engine(path: str | None = None):
    p = path or DB_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    eng = create_engine(f"sqlite:///{p}")
    Base.metadata.create_all(eng)
    return eng


def get_session(engine):
    return sessionmaker(bind=engine)()
