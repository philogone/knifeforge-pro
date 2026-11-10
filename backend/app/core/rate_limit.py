import logging
import threading
import time

import redis
from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger("knifeforge")
settings = get_settings()

_redis = None
if settings.redis_url:
    try:
        _redis = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    except Exception:  # noqa: BLE001 - constructing the client never talks to the network yet
        _redis = None

# Without Redis (the desktop build: one process on one machine) attempts are counted in memory.
_local_lock = threading.Lock()
_local_attempts: dict[str, tuple[float, int]] = {}


def _too_many() -> HTTPException:
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts, try again shortly")


def _count_locally(key: str) -> int:
    now = time.monotonic()
    with _local_lock:
        start, count = _local_attempts.get(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        _local_attempts[key] = (start, count + 1)
        return count + 1


def rate_limit_login(request: Request) -> None:
    """Rate limit on login attempts, keyed by client IP. Redis-backed under Docker, where it
    fails open (allows the request) if Redis is unreachable — an outage in the rate limiter
    shouldn't lock the sole admin out of their own tool."""
    key = f"login-attempts:{request.client.host if request.client else 'unknown'}"
    if _redis is None:
        if not settings.redis_url and _count_locally(key) > settings.rate_limit_per_minute:
            raise _too_many()
        return
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, 60)
        if count > settings.rate_limit_per_minute:
            raise _too_many()
    except redis.RedisError:
        logger.warning("Rate limiter unreachable, failing open")
