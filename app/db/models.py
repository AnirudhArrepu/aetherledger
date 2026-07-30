from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    DateTime,
    JSON,
    Boolean,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    currency = Column(String(8), nullable=False)
    overdraft_limit = Column(Numeric, default=0)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(BigInteger, primary_key=True)
    account_id = Column(Integer, nullable=False, index=True)
    currency = Column(String(8), nullable=False)
    amount = Column(Numeric, nullable=False)  # positive for credit, negative for debit convention
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata = Column(JSON, nullable=True)
    tx_id = Column(String, nullable=False, index=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id = Column(BigInteger, primary_key=True)
    tx_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    locked = Column(Boolean, default=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    delivered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


_engine = None
_async_session = None


def get_engine(url=None):
    global _engine
    if _engine is None:
        _engine = create_async_engine(url)
    return _engine


def get_session(url=None):
    global _async_session
    if _async_session is None:
        engine = get_engine(url)
        _async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session

#TODO: implement snapshot based time projection
async def get_balance_projection(account_id: int, as_of: str = None):
    sessionmaker = get_session()
    async with sessionmaker() as s:
        q = await s.execute(
            "SELECT SUM(amount) as balance FROM ledger_entries WHERE account_id = :aid",
            {"aid": account_id},
        )
        row = q.first()
        return float(row.balance or 0)
