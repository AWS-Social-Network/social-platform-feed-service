import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.consumer import consume_loop
from app.redis_client import close_redis, get_redis
from app.routers.feed import router as feed_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(consume_loop())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await close_redis()


app = FastAPI(title="Feed Service", version="0.1.0", lifespan=lifespan)
app.include_router(feed_router)


@app.get("/health")
async def health():
    try:
        r = await get_redis()
        pong = await r.ping()
        if pong is not True:
            raise RuntimeError("unexpected PING response")
        return {"status": "ok", "redis": "up"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "redis": "down"},
        )
