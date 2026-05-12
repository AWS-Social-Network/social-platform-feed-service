from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.dependencies.get_redis import RedisDep

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
async def health(redis: RedisDep):
    try:
        pong = await redis.ping()
        if pong is not True:
            raise RuntimeError("unexpected PING response")
        return {"status": "ok", "redis": "up"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "redis": "down"},
        )
