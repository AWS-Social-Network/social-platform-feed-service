import asyncio
import json
import logging
from datetime import UTC, datetime
from time import time
from typing import Any

import aioboto3

from app.config import settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_session = aioboto3.Session()


def _sqs_kwargs() -> dict[str, Any]:
    return {"region_name": settings.aws_region}


def _parse_created_at(created_at: str) -> float:
    try:
        s = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except ValueError:
        return time()


async def _handle_new_post(payload: dict[str, Any], redis) -> None:
    post_id = str(payload["post_id"])
    author_id = str(payload["author_id"])
    created_at = str(payload.get("created_at", ""))
    follower_ids: list[str] = [str(x) for x in payload.get("follower_ids", [])]
    content = str(payload.get("content", ""))

    member = json.dumps(
        {
            "post_id": post_id,
            "author_id": author_id,
            "content": content,
            "created_at": created_at,
        }
    )
    score = _parse_created_at(created_at)

    for user_id in follower_ids:
        feed_key = f"feed:{user_id}"
        dedup_key = f"dedup:{post_id}:{user_id}"

        added = await redis.zadd(feed_key, {member: score}, nx=True)
        if added:
            card = await redis.zcard(feed_key)
            if card > settings.feed_max_length:
                to_drop = card - settings.feed_max_length
                await redis.zremrangebyrank(feed_key, 0, to_drop - 1)
            await redis.set(dedup_key, "1", ex=settings.dedup_ttl_seconds)


async def process_message(body: str, redis) -> None:
    msg = json.loads(body)
    event_type = msg.get("event_type")
    payload = msg.get("payload", {})
    if event_type == "new_post":
        await _handle_new_post(payload, redis)
    else:
        logger.debug("Ignoring event_type=%s", event_type)


async def consume_loop() -> None:
    redis = await get_redis()
    logger.info("SQS consumer started, polling %s", settings.sqs_queue_url)

    async with _session.client("sqs", **_sqs_kwargs()) as sqs:
        while True:
            try:
                resp = await sqs.receive_message(
                    QueueUrl=settings.sqs_queue_url,
                    MaxNumberOfMessages=settings.sqs_max_messages,
                    WaitTimeSeconds=settings.sqs_wait_time_seconds,
                    VisibilityTimeout=settings.sqs_visibility_timeout,
                )
                messages = resp.get("Messages", [])
                for msg in messages:
                    receipt = msg["ReceiptHandle"]
                    try:
                        await process_message(msg["Body"], redis)
                        await sqs.delete_message(
                            QueueUrl=settings.sqs_queue_url,
                            ReceiptHandle=receipt,
                        )
                    except Exception:
                        logger.exception("Message left for retry: %s", msg.get("MessageId"))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Consumer loop error")
                await asyncio.sleep(5)
