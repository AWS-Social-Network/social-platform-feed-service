from typing import Annotated

from core.redis_client import get_redis

from fastapi import Depends
from redis.asyncio import Redis


RedisDep = Annotated[Redis, Depends(get_redis)]