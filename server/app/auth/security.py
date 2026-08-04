"""Password hashing and JWT token utilities."""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 7

BCRYPT_COST = 12

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ.get("JWT_SECRET") or "stylemate-dev-secret-change-me-0123456789abcdef"
JWT_ISSUER = "stylemate"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode(
        "utf-8"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(sub: str, token_type: str, ttl: timedelta) -> str:
    now = _now()
    payload = {
        "sub": sub,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl,
        "iss": JWT_ISSUER,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _encode(str(user_id), "access", timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES))


def create_refresh_token(user_id: int) -> str:
    return _encode(
        str(user_id), "refresh", timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    )


def decode_token(token: str, expected_type: str | None = None) -> dict:
    """Decode and validate a JWT.

    Raises jwt.PyJWTError for expired/invalid signatures.
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)
    if expected_type is not None and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected {expected_type!r} token, got {payload.get('type')!r}"
        )
    return payload


def refresh_token_hash(token: str) -> str:
    """SHA-256 of the refresh token, so raw tokens are never stored in DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_expires_at(token: str) -> datetime:
    """Return the expiry of a (valid) refresh token as an aware datetime."""
    payload = jwt.decode(
        token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False}
    )
    return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)


def tokens_match(token: str, token_hash: str) -> bool:
    """Constant-time comparison of a refresh token against its stored hash."""
    return hmac.compare_digest(refresh_token_hash(token), token_hash)
