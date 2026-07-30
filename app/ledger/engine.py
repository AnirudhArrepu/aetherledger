import uuid
from typing import List
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
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
    while True:
        attempt += 1
        async with Session() as s:
            async with s.begin():
                await s.execute(text("SET LOCAL TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

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
                out = OutboxEvent(tx_id=tx_id, payload={"tx_id": tx_id, "entries": [e.__dict__ for e in entries]})
                s.add(out)

            # commit happens here
        # if no exception, return tx_id
        return tx_id

        # TODO: handle serialization errors by catching specific exceptions and retrying
        if attempt >= max_retries:
            raise RuntimeError("Failed to commit transaction after retries")
