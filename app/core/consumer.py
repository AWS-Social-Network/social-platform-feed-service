import asyncio
import json
import logging
from datetime import UTC, datetime
from time import time
from typing import Any, cast


from app.core.config import settings


import aioboto3
from redis.asyncio import Redis
from types_aiobotocore_sqs.client import SQSClient

logger = logging.getLogger(__name__)

_session = aioboto3.Session()


def _sqs_kwargs() -> dict[str, Any]:
    kw: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.sqs_endpoint_url:
        kw["endpoint_url"] = settings.sqs_endpoint_url
    return kw


def _parse_created_at(created_at: str, post_id: str) -> float:
    try:
        s = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except ValueError:
        logger.warning(
            f"Unparseable created_at={created_at} for post_id={post_id}, using now"
        )
        return time()


async def _handle_new_post(payload: dict[str, Any], redis: Redis) -> None:
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
    write_count = 0
    score = _parse_created_at(created_at, post_id)

    async with redis.pipeline(transaction=False) as add_pipe:
        for user_id in follower_ids:
            feed_key = f"feed:{user_id}"
            add_pipe.zadd(feed_key, {member: score}, nx=True)

        results = await add_pipe.execute()

    async with redis.pipeline(transaction=False) as cards_pipe:
        for idx, user_id in enumerate(follower_ids):
            if results[idx]:
                feed_key = f"feed:{user_id}"
                dedup_key = f"dedup:{post_id}:{user_id}"
                cards_pipe.zcard(feed_key)
        cards = await cards_pipe.execute()

    async with redis.pipeline(transaction=False) as trim_pipe:
        for idx, (user_id, card) in enumerate(zip(follower_ids, cards)):
            if results[idx]:
                write_count += 1
                feed_key = f"feed:{user_id}"
                dedup_key = f"dedup:{post_id}:{user_id}"
                if card > settings.feed_max_length:
                    trim_pipe.zremrangebyrank(
                        feed_key, 0, card - settings.feed_max_length - 1
                    )
                trim_pipe.set(dedup_key, "1", ex=settings.dedup_ttl_seconds)
        await trim_pipe.execute()
    logger.info(
        f"Fan-out complete post_id={post_id} followers={len(follower_ids)} written={write_count}",
    )


async def process_message(body: str, redis) -> None:
    msg = json.loads(body)
    event_type = msg.get("event_type")
    payload = msg.get("payload", {})
    if event_type == "new_post":
        await _handle_new_post(payload, redis)
    else:
        logger.debug(f"Ignoring event_type={event_type}")


async def consume_loop(redis: Redis) -> None:
    logger.info("SQS consumer started, polling %s", settings.sqs_queue_url)

    async with cast(SQSClient, _session.client("sqs", **_sqs_kwargs())) as sqs:
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
                    receipt = msg.get("ReceiptHandle")
                    body = msg.get("Body")
                    if not (body and receipt):
                        logger.error(
                            f"Invalid message: missing body or receipt: {msg.get("MessageId")}"
                        )
                        continue
                    try:
                        await process_message(body, redis)
                        await sqs.delete_message(
                            QueueUrl=settings.sqs_queue_url,
                            ReceiptHandle=receipt,
                        )
                    except Exception:
                        logger.exception(
                            f"Message left for retry: {msg.get("MessageId")}"
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Consumer loop error")
                await asyncio.sleep(5)
