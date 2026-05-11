# Feed Service

Read-only API backed by **Redis** sorted sets. An **asyncio** background task long-polls **SQS** (via **aioboto3**), fans out `new_post` events into per-user feeds, trims to **500** entries, and uses **`ZADD NX`** plus **`SET` dedup keys** (24h TTL) for idempotency. Failed processing leaves messages in the queue until **maxReceiveCount** sends them to a **DLQ** (configure on the queue in AWS).

## ALB path prefix

Use path prefix `/feed` so the feed API is `GET /feed/{user_id}`. Probes use `/health` on the pod.

## Local run

```bash
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --port 8002
```

Requires Redis and a reachable SQS queue (or ElasticMQ) for the consumer loop to be useful.
