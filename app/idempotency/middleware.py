from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import aioredis
import json
from app.core.config import settings
from pathlib import Path


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = None, ttl: int = 3600):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self.ttl = ttl
        self.redis = None
        # load script
        script_path = Path(__file__).parent / "scripts" / "idempotency.lua"
        self.lua_script = script_path.read_text()
        self._script_sha = None

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PATCH", "DELETE"):
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        body = await request.body()
        if not key:
            return Response(json.dumps({"error": "missing_idempotency_key"}), status_code=400, media_type="application/json")

        if self.redis is None:
            self.redis = await aioredis.from_url(self.redis_url)
            try:
                self._script_sha = await self.redis.script_load(self.lua_script)
            except Exception:
                self._script_sha = None

        cached = await self.redis.get(key)
        if cached:
            return Response(cached, media_type="application/json", status_code=200)

        try:
            if self._script_sha:
                res = await self.redis.evalsha(self._script_sha, 1, key, json.dumps({"inflight": True}), self.ttl)
            else:
                res = await self.redis.set(key, json.dumps({"inflight": True}), ex=self.ttl, nx=True)
        except Exception:
            res = None

        if not res:
            return Response(json.dumps({"error": "duplicate_in_flight"}), status_code=409, media_type="application/json")

        response: Response = await call_next(request)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        await self.redis.set(key, body.decode('utf-8'), ex=self.ttl)
        return Response(body, status_code=response.status_code, media_type=response.media_type)
