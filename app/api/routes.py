from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.ledger.engine import process_transaction, TransactionEntry
from app.fx.routing import route_fx

router = APIRouter()

class TransactionRequest(BaseModel):
    entries: List[TransactionEntry]
    base_currency: str


@router.post("/transactions")
async def create_transaction(req: TransactionRequest):
    try:
        txid = await process_transaction(req.entries, req.base_currency)
        return {"tx_id": txid}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fx/route")
async def fx_route(from_currency: str, to_currency: str, amount: float):
    path = route_fx(from_currency, to_currency, amount)
    if path is None:
        raise HTTPException(status_code=400, detail="No route found or arbitrage detected")
    return path


@router.get("/accounts/{account_id}/balance")
async def account_balance(account_id: int, as_of: str = None):
    # simple projection API placeholder
    from app.db.models import get_balance_projection

    bal = await get_balance_projection(account_id, as_of)
    return {"account_id": account_id, "balance": bal}
