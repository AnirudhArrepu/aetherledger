from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
import aioredis
from pathlib import Path
import time
import json
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = None, window_ms: int = 60000, limit: int = 100):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self.window_ms = window_ms
        self.limit = limit
        self.redis = None
        script_path = Path(__file__).parent / "scripts" / "sliding_window.lua"
        self.lua = script_path.read_text()
        self._sha = None

    async def dispatch(self, request: Request, call_next):
        if self.redis is None:
            self.redis = await aioredis.from_url(self.redis_url)
            try:
                self._sha = await self.redis.script_load(self.lua)
            except Exception:
                self._sha = None

        client = request.headers.get("X-Client-Id", "anonymous")
        route = request.url.path
        key = f"ratelimit:{client}:{route}"
        now = int(time.time() * 1000)

        try:
            if self._sha:
                allowed, count = await self.redis.evalsha(self._sha, 1, key, now, self.window_ms, self.limit)
            else:
                await self.redis.zadd(key, {str(now): now})
                await self.redis.zremrangebyscore(key, 0, now - self.window_ms)
                count = await self.redis.zcard(key)
                await self.redis.pexpire(key, self.window_ms)
                allowed = 1 if count <= self.limit else 0
        except Exception:
            allowed = 1
            count = 0

        if int(allowed) == 0:
            retry_after = int(self.window_ms / 1000)
            return Response(json.dumps({"error": "rate_limited", "count": count}), status_code=429, headers={"Retry-After": str(retry_after)}, media_type="application/json")

        return await call_next(request)
