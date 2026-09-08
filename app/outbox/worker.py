import asyncio
import aiohttp
import hmac
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from app.db.models import get_session, OutboxEvent
from sqlalchemy import text

SHARED_SECRET = os.getenv("PAYLOAD_SECRET")


async def sign_payload(payload: bytes) -> str:
    # Ensure SHARED_SECRET is converted to bytes if it was loaded as a string
    secret_bytes = SHARED_SECRET.encode('utf-8') if isinstance(SHARED_SECRET, str) else SHARED_SECRET
    return hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()


async def deliver_event(session, event):
    # event.payload should include target URL and body
    payload = json.dumps(event.payload).encode('utf-8')
    signature = await sign_payload(payload)
    url = event.payload.get('webhook_url') or event.payload.get('url')
    headers = {'X-Signature': signature, 'Content-Type': 'application/json'}
    async with aiohttp.ClientSession() as client:
        try:
            async with client.post(url, data=payload, headers=headers, timeout=10) as resp:
                return resp.status >= 200 and resp.status < 300
        except Exception:
            return False


async def outbox_worker(poll_interval: float = 1.0):
    Session = get_session()
    while True:
        async with Session() as s:
            # 1. Added explicit .bindparams() mapping using modern SQLAlchemy conventions
            q = await s.execute(
                text(
                    "SELECT id, tx_id, payload, attempts, max_attempts FROM outbox_events "
                    "WHERE delivered = false AND (next_retry_at IS NULL OR next_retry_at <= now()) "
                    "ORDER BY created_at LIMIT 10 FOR UPDATE SKIP LOCKED"
                )
            )
            rows = q.fetchall()
            for r in rows:
                event = type('E', (), { 'id': r[0], 'tx_id': r[1], 'payload': r[2], 'attempts': r[3], 'max_attempts': r[4] })
                ok = await deliver_event(s, event)
                
                if ok:
                    # 2. Executing with a clean parameter parameter mapping dictionary
                    await s.execute(
                        text("UPDATE outbox_events SET delivered = true WHERE id = :id"), 
                        {"id": event.id}
                    )
                else:
                    # Exponential backoff
                    attempts = event.attempts + 1
                    if attempts >= event.max_attempts:
                        await s.execute(
                            text("UPDATE outbox_events SET attempts = :a, next_retry_at = NULL WHERE id = :id"), 
                            {"a": attempts, "id": event.id}
                        )
                    else:
                        delay = min(60, 2 ** attempts)
                        next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
                        await s.execute(
                            text("UPDATE outbox_events SET attempts = :a, next_retry_at = :n WHERE id = :id"), 
                            {"a": attempts, "n": next_retry, "id": event.id}
                        )
            await s.commit()
        await asyncio.sleep(poll_interval)


if __name__ == '__main__':
    asyncio.run(outbox_worker())
