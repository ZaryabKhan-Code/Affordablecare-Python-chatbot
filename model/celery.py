from celery import Celery
import os

redis_url = os.environ.get("REDISCLOUD_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=redis_url, backend=redis_url)
