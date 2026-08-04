"""Login attempt rate limiting.

Primary backend is Redis (shared across instances, survives restarts). If
Redis is unreachable we fall back to an in-process TTL cache so a Redis
outage never 500s the login endpoint — it just degrades to per-process
limits until Redis is back.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60  # 15 minutes
RESET_HEADER_SECONDS = WINDOW_SECONDS

_pool: "redis.Redis | None" = None
_pool_lock = threading.Lock()


def _client() -> "redis.Redis | None":
    """Return a Redis client, or None if Redis is unavailable."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    _pool = redis.from_url(REDIS_URL, socket_connect_timeout=1)
                    _pool.ping()
                except Exception:
                    logger.warning(
                        "Redis unavailable (%s); login rate limiting falls back to in-memory",
                        REDIS_URL,
                    )
                    _pool = None
    return _pool


# ── In-memory fallback ──

_mem_attempts: dict[str, deque[float]] = defaultdict(deque)
_mem_lock = threading.Lock()


def _mem_register_attempt(email: str) -> None:
    now = time.monotonic()
    with _mem_lock:
        dq = _mem_attempts[email]
        while dq and now - dq[0] > WINDOW_SECONDS:
            dq.popleft()
        dq.append(now)


def _mem_attempts_in_window(email: str) -> int:
    now = time.monotonic()
    with _mem_lock:
        dq = _mem_attempts[email]
        while dq and now - dq[0] > WINDOW_SECONDS:
            dq.popleft()
        return len(dq)


def register_failed_login(email: str) -> None:
    client = _client()
    if client is not None:
        try:
            key = f"login_fail:{email.lower()}"
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, WINDOW_SECONDS, nx=True)
            pipe.execute()
            return
        except Exception:
            logger.warning("Redis rate-limit write failed; using in-memory")
    _mem_register_attempt(email)


def reset_failed_logins(email: str) -> None:
    client = _client()
    if client is not None:
        try:
            client.delete(f"login_fail:{email.lower()}")
            return
        except Exception:
            pass
    with _mem_lock:
        _mem_attempts.pop(email, None)


def login_attempts_in_window(email: str) -> int:
    client = _client()
    if client is not None:
        try:
            val = client.get(f"login_fail:{email.lower()}")
            return int(val) if val else 0
        except Exception:
            pass
    return _mem_attempts_in_window(email)


def is_login_blocked(email: str) -> bool:
    return login_attempts_in_window(email) >= MAX_ATTEMPTS


def retry_after_seconds(email: str) -> int:
    """Seconds until the current window expires (best effort)."""
    client = _client()
    if client is not None:
        try:
            ttl = client.ttl(f"login_fail:{email.lower()}")
            if ttl and ttl > 0:
                return int(ttl)
        except Exception:
            pass
    return RESET_HEADER_SECONDS
