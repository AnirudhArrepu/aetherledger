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


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"
    id = Column(BigInteger, primary_key=True)
    account_id = Column(Integer, nullable=False, index=True)
    currency = Column(String(8), nullable=False)
    balance = Column(Numeric, nullable=False)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_entry_id = Column(BigInteger, nullable=True)


async def get_balance_projection(account_id: int, as_of: str = None):
    from sqlalchemy import text
    import datetime

    # Parse as_of into a datetime; default to now (UTC)
    if as_of:
        try:
            as_of_dt = datetime.datetime.fromisoformat(as_of)
        except Exception:
            # Fallback: let DB interpret the string
            as_of_dt = as_of
    else:
        as_of_dt = datetime.datetime.now(datetime.timezone.utc)

    Session = get_session()
    async with Session() as s:
        # find latest snapshot for account at or before as_of
        q = await s.execute(
            text(
                "SELECT id, balance, snapshot_at FROM balance_snapshots WHERE account_id = :aid AND snapshot_at <= :as_of ORDER BY snapshot_at DESC LIMIT 1"
            ),
            {"aid": account_id, "as_of": as_of_dt},
        )
        snap = q.first()

        if snap:
            snap_balance = snap.balance or 0
            snap_at = snap.snapshot_at
            # sum ledger entries after snapshot up to as_of
            q2 = await s.execute(
                text(
                    "SELECT COALESCE(SUM(amount),0) AS delta FROM ledger_entries WHERE account_id = :aid AND created_at > :snap_at AND created_at <= :as_of"
                ),
                {"aid": account_id, "snap_at": snap_at, "as_of": as_of_dt},
            )
            row = q2.first()
            delta = row.delta or 0
            return float(snap_balance + delta)
        else:
            # no snapshot: sum all ledger entries up to as_of
            q3 = await s.execute(
                text("SELECT COALESCE(SUM(amount),0) AS balance FROM ledger_entries WHERE account_id = :aid AND created_at <= :as_of"),
                {"aid": account_id, "as_of": as_of_dt},
            )
            row = q3.first()
            return float(row.balance or 0)


async def create_snapshot(account_id: int, as_of: str = None):
    """
    Create a balance snapshot for the given account up to `as_of` (defaults to now). Returns the inserted snapshot row dict.
    """
    from sqlalchemy import text
    import datetime

    if as_of:
        try:
            as_of_dt = datetime.datetime.fromisoformat(as_of)
        except Exception:
            as_of_dt = as_of
    else:
        as_of_dt = datetime.datetime.now(datetime.timezone.utc)

    Session = get_session()
    async with Session() as s:
        async with s.begin():
            # fetch account currency
            q = await s.execute(text("SELECT currency FROM accounts WHERE id = :aid"), {"aid": account_id})
            acc = q.first()
            if not acc:
                raise ValueError("account not found")
            currency = acc.currency

            # aggregate and insert snapshot atomically
            insert_sql = text(
                "WITH agg AS (\n                    SELECT COALESCE(SUM(amount),0) AS balance, MAX(id) AS last_entry_id, MAX(created_at) AS snapshot_at\n                    FROM ledger_entries\n                    WHERE account_id = :aid AND created_at <= :as_of\n                )\n                INSERT INTO balance_snapshots (account_id, currency, balance, snapshot_at, last_entry_id)\n                SELECT :aid, :currency, agg.balance, COALESCE(agg.snapshot_at, now()), agg.last_entry_id FROM agg\n                RETURNING id, balance, snapshot_at, last_entry_id"
            )
            res = await s.execute(insert_sql, {"aid": account_id, "currency": currency, "as_of": as_of_dt})
            row = res.first()
            if row:
                return {"id": row.id, "balance": float(row.balance), "snapshot_at": row.snapshot_at, "last_entry_id": row.last_entry_id}
            else:
                raise RuntimeError("failed to create snapshot")
