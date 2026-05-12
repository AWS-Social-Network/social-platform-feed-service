import json

from fastapi import APIRouter, Query

from app.dependencies.get_current_user import CurrentUserDep
from app.dependencies.get_redis import RedisDep


router = APIRouter(prefix="/feed", tags=["Feed"])


@router.get("/{user_id}")
async def get_feed(
    user_id: str,
    current_user: CurrentUserDep,
    redis: RedisDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
