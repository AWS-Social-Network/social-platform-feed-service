import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import redis.asyncio as redis

from app.core.consumer import consume_loop
from app.core.config import settings
from app.api import feed, health

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    consumer_task = asyncio.create_task(consume_loop(app.state.redis))
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await app.state.redis.close()


app = FastAPI(title="Feed Service", version="0.1.0", lifespan=lifespan)
app.include_router(feed.router)
app.include_router(health.router)
