import uuid
from typing import List
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
import asyncio
from app.db.models import get_session, LedgerEntry, OutboxEvent


@dataclass
class TransactionEntry:
    account_id: int
    currency: str
    amount: Decimal


async def process_transaction(entries: List[TransactionEntry], base_currency: str) -> str:
    Session = get_session()
    tx_id = str(uuid.uuid4())

    total = sum((e.amount for e in entries))
    if total != 0:
        raise ValueError("Transaction entries do not sum to zero")

    max_retries = 5
    attempt = 0
    base_backoff = 0.1

    while attempt < max_retries:
        attempt += 1
        try:
            async with Session() as s:
                async with s.begin():
                    await s.execute(text("SET LOCAL TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

                    # # enforce overdraft limits per-account BEFORE inserting entries
                    # # lock account rows to avoid lost-update races; rely on SERIALIZABLE + retries for safety
                    # affected_accounts = sorted({int(e.account_id) for e in entries})
                    # account_limits = {}
                    # for aid in affected_accounts:
                    #     q = await s.execute(text("SELECT id, overdraft_limit FROM accounts WHERE id = :aid FOR UPDATE"), {"aid": aid})
                    #     acc_row = q.first()
                    #     if not acc_row:
                    #         raise ValueError(f"account {aid} not found")
                    #     account_limits[aid] = acc_row.overdraft_limit or 0

                    # # compute current balances and check post-transaction balances
                    # for aid in affected_accounts:
                    #     q2 = await s.execute(text("SELECT COALESCE(SUM(amount),0) AS balance FROM ledger_entries WHERE account_id = :aid"), {"aid": aid})
                    #     row = q2.first()
                    #     current_balance = row.balance or 0
                    #     # compute delta from this transaction for this account
                    #     delta = sum((e.amount for e in entries if int(e.account_id) == aid))
                    #     new_balance = current_balance + delta
                    #     overdraft_limit = account_limits[aid]
                    #     # overdraft_limit is amount allowed to go negative (e.g., 0 means no overdraft)
                    #     if new_balance < -overdraft_limit:
                    #         raise ValueError(f"would overdraft account {aid}")

                    # insert ledger entries
                    for e in entries:
                        le = LedgerEntry(
                            account_id=e.account_id,
                            currency=e.currency,
                            amount=e.amount,
                            tx_id=tx_id,
                            metadata={"base_currency": base_currency},
                        )
                        s.add(le)

                    # insert outbox event in same transaction
                    # serialize Decimal amounts to strings to ensure JSON serializability
                    serializable_entries = [
                        {"account_id": int(e.account_id), "currency": e.currency, "amount": str(e.amount)}
                        for e in entries
                    ]
                    out = OutboxEvent(tx_id=tx_id, payload={"tx_id": tx_id, "entries": serializable_entries})
                    s.add(out)

                    # commit happens on exit from transactional block
            return tx_id
        except DBAPIError as e:
            # Postgres serialization error SQLSTATE = '40001'
            orig = getattr(e, 'orig', None)
            pgcode = getattr(orig, 'pgcode', None)
            if pgcode == '40001' and attempt < max_retries:
                await asyncio.sleep(base_backoff * (2 ** (attempt - 1)))
                continue
            raise
        except Exception:
            raise

    raise RuntimeError("Failed to commit transaction after retries")
