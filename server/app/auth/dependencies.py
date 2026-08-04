"""FastAPI dependencies for JWT authentication."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.database import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Decode the access-token JWT and return the authenticated user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise INVALID_CREDENTIALS

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise INVALID_CREDENTIALS

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise INVALID_CREDENTIALS
    return user


def get_current_user_id(current_user: User = Depends(get_current_user)) -> int:
    """Convenience dependency that returns just the authenticated user id."""
    return current_user.id
