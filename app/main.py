from fastapi import FastAPI
from app.api.routes import router as api_router
from app.core.config import settings
from app.idempotency.middleware import IdempotencyMiddleware
from app.ratelimit.middleware import RateLimitMiddleware

app = FastAPI()

app.add_middleware(RateLimitMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "healthy"}
