import logging

import redis
from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger("knifeforge")
settings = get_settings()

try:
    _redis = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
except Exception:  # noqa: BLE001 - constructing the client never talks to the network yet
    _redis = None


def rate_limit_login(request: Request) -> None:
    """Redis-backed rate limit on login attempts, keyed by client IP.
    Fails open (allows the request) if Redis is unreachable — an outage in
    the rate limiter shouldn't lock the sole admin out of their own tool."""
    if _redis is None:
        return
    key = f"login-attempts:{request.client.host if request.client else 'unknown'}"
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, 60)
        if count > settings.rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts, try again shortly")
    except redis.RedisError:
        logger.warning("Rate limiter unreachable, failing open")
