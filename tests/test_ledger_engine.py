import pytest
from decimal import Decimal
from app.ledger.engine import TransactionEntry, process_transaction


# @pytest.mark.asyncio
async def test_transaction_sum_invariant():
    entries = [
        TransactionEntry(account_id=1, currency="USD", amount=Decimal("100.00")),
        TransactionEntry(account_id=2, currency="USD", amount=Decimal("-50.00")),
    ]

    # sum != 0 so process_transaction should raise ValueError before attempting DB writes
    with pytest.raises(ValueError):
        await process_transaction(entries, base_currency="USD")
