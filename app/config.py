from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "us-east-1"
    sqs_queue_url: str
    sqs_endpoint_url: str | None = Field(
        default=None,
        description="e.g. http://127.0.0.1:4566 for LocalStack SQS",
    )

    redis_url: str = "redis://localhost:6379/0"

    sqs_max_messages: int = 10
    sqs_wait_time_seconds: int = 20
    sqs_visibility_timeout: int = 60

    feed_max_length: int = 500
    dedup_ttl_seconds: int = 86400

    secret_key: str
    algorithm: str = "HS256"


settings = Settings()
