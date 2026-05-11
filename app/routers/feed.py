import json

from fastapi import APIRouter, Depends, Query

from app.redis_client import get_redis
from app.security import get_current_user

router = APIRouter(prefix="/feed")


@router.get("/{user_id}")
async def get_feed(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    redis=Depends(get_redis),
):
    _ = current_user
    feed_key = f"feed:{user_id}"
    start = (page - 1) * page_size
    end = start + page_size - 1
    raw_items = await redis.zrevrange(feed_key, start, end)
    posts = [json.loads(item) for item in raw_items]
    return {
        "user_id": user_id,
        "page": page,
        "page_size": page_size,
        "posts": posts,
    }
