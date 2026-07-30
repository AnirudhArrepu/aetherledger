import asyncio
from app.outbox.worker import sign_payload, SHARED_SECRET
import hmac, hashlib


def test_sign_payload_sync_equivalence():
    payload = b"hello"
    # compute expected
    expected = hmac.new(SHARED_SECRET, payload, hashlib.sha256).hexdigest()
    got = asyncio.get_event_loop().run_until_complete(sign_payload(payload))
    assert got == expected
