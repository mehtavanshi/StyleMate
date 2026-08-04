from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.rate_limit import (
    is_login_blocked,
    register_failed_login,
    reset_failed_logins,
    retry_after_seconds,
)
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    refresh_token_hash,
    token_expires_at,
    tokens_match,
    verify_password,
)
from app.database import get_db
from app.models import RefreshToken, User
from app.schemas import (
    LoginIn,
    LogoutIn,
    RefreshIn,
    RegisterIn,
    RegisterResponse,
    TokenPair,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User, db: Session) -> TokenPair:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash(refresh_token),
            expires_at=token_expires_at(refresh_token),
            revoked=False,
        )
    )
    db.commit()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    name = (payload.name or "").strip() or payload.email.split("@")[0]
    user = User(
        name=name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    tokens = _issue_tokens(user, db)
    return RegisterResponse(**tokens.model_dump(), user=user)


@router.post("/login", response_model=RegisterResponse)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    if is_login_blocked(payload.email):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many failed login attempts. Try again later.",
            },
            headers={"Retry-After": str(retry_after_seconds(payload.email))},
        )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        register_failed_login(payload.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    reset_failed_logins(payload.email)
    tokens = _issue_tokens(user, db)
    return RegisterResponse(**tokens.model_dump(), user=user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    # 1. Verify signature + expiry + token type.
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(claims["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    token_hash = refresh_token_hash(payload.refresh_token)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    # 2. Verify the DB hash matches and the token isn't revoked/expired.
    now = datetime.now(timezone.utc)
    if not record:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    if record.revoked:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    if record.user_id != user_id:
        raise HTTPException(status_code=401, detail="Refresh token mismatch")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # 3. Rotate: revoke the old token, issue a new pair.
    record.revoked = True
    record.revoked_at = now
    db.commit()

    return _issue_tokens(user, db)


@router.post("/logout", status_code=204)
def logout(payload: LogoutIn, db: Session = Depends(get_db)):
    # Reject garbage immediately; tolerate unknown-but-well-formed tokens by
    # still succeeding (logout is idempotent from the client's perspective).
    try:
        decode_token(payload.refresh_token, expected_type="refresh")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = refresh_token_hash(payload.refresh_token)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )
    if record:
        db.delete(record)
        db.commit()
    return None
