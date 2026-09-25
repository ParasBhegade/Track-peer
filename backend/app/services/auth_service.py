import uuid
from datetime import UTC, datetime, timedelta

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.auth_token import PasswordResetToken, RefreshToken
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthRequest,
    GoogleLinkRequest,
    LoginRequest,
    RegisterRequest,
    Tokens,
)


async def _create_refresh_token_row(
    db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID | None = None
) -> tuple[str, RefreshToken]:
    plain_token = generate_opaque_token()
    hashed = hash_token(plain_token)

    rt = RefreshToken(
        user_id=user_id,
        token_hash=hashed,
        family_id=family_id or uuid.uuid4(),
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    return plain_token, rt


async def _generate_tokens_for_user(
    db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID | None = None
) -> Tokens:
    access_token = create_access_token(subject=user_id)
    plain_refresh_token, _ = await _create_refresh_token_row(db, user_id, family_id)

    return Tokens(
        access_token=access_token,
        refresh_token=plain_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def register_user(db: AsyncSession, payload: RegisterRequest) -> tuple[User, Tokens]:
    email_lower = payload.email.lower()

    # Check existing user
    stmt = select(User).where(User.email == email_lower)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise AppError(409, "email_taken", "A user with this email already exists")

    hashed_pw = hash_password(payload.password)

    # Transactional registration
    user = User(
        email=email_lower,
        password_hash=hashed_pw,
        display_name=payload.display_name,
        timezone=payload.timezone,
    )
    db.add(user)
    await db.flush()  # ensure user.id is available

    tokens = await _generate_tokens_for_user(db, user.id)
    await db.commit()
    await db.refresh(user)
    return user, tokens


async def login_user(db: AsyncSession, payload: LoginRequest) -> tuple[User, Tokens]:
    email_lower = payload.email.lower()

    stmt = select(User).where(User.email == email_lower)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise AppError(401, "invalid_credentials", "Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid email or password")

    tokens = await _generate_tokens_for_user(db, user.id)
    await db.commit()
    return user, tokens


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> Tokens:
    hashed = hash_token(refresh_token)

    # FOR UPDATE ensures concurrency protection for rotation
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed).with_for_update()
    result = await db.execute(stmt)
    rt = result.scalar_one_or_none()

    if not rt:
        raise AppError(401, "refresh_token_invalid", "Invalid refresh token")

    now = datetime.now(UTC)
    if rt.expires_at < now:
        raise AppError(401, "refresh_token_invalid", "Refresh token expired")

    if rt.revoked_at is not None:
        # Replay detected -> Revoke family
        revoke_stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == rt.family_id)
            .values(revoked_at=now)
        )
        await db.execute(revoke_stmt)
        await db.commit()
        raise AppError(401, "refresh_token_invalid", "Refresh token revoked (reuse detected)")

    # Valid rotation
    rt.revoked_at = now

    tokens = await _generate_tokens_for_user(db, rt.user_id, rt.family_id)
    await db.commit()
    return tokens


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    hashed = hash_token(refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed)
    result = await db.execute(stmt)
    rt = result.scalar_one_or_none()

    if rt and rt.revoked_at is None:
        rt.revoked_at = datetime.now(UTC)
        await db.commit()


async def _verify_google_token(id_token: str) -> dict:
    try:
        request = google_requests.Request()
        id_info = google_id_token.verify_oauth2_token(
            id_token, request, settings.GOOGLE_CLIENT_ID
        )

        # Explicit validation checks
        if id_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer.")

        # google-auth already verifies signature, audience, and expiration during verify_oauth2_token

        if not id_info.get("email_verified", False):
            raise AppError(400, "bad_request", "Google email not verified")

        return dict(id_info)  # type: ignore[arg-type]
    except Exception as e:
        if isinstance(e, AppError):
            raise e
        raise AppError(401, "invalid_credentials", f"Invalid Google token: {str(e)}") from e


async def google_auth(db: AsyncSession, payload: GoogleAuthRequest) -> tuple[User, Tokens]:
    id_info = await _verify_google_token(payload.id_token)
    google_id = id_info["sub"]
    email = id_info["email"].lower()

    # 1. Match by google_id
    stmt = select(User).where(User.google_oauth_id == google_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        tokens = await _generate_tokens_for_user(db, user.id)
        await db.commit()
        return user, tokens

    # 2. Match by email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Existing email without link -> Link required
        raise AppError(
            409,
            "account_exists_link_required",
            "Account exists, please log in with password and link Google account",
        )

    # 3. New user
    user = User(
        email=email,
        display_name=id_info.get("name", "Google User")[:50],
        avatar_url=id_info.get("picture"),
        timezone=payload.timezone,
        google_oauth_id=google_id,
    )
    db.add(user)
    await db.flush()

    tokens = await _generate_tokens_for_user(db, user.id)
    await db.commit()
    await db.refresh(user)
    return user, tokens


async def google_link(db: AsyncSession, current_user: User, payload: GoogleLinkRequest) -> User:
    id_info = await _verify_google_token(payload.id_token)
    google_id = id_info["sub"]

    # Check if this google ID is already linked to another account
    stmt = select(User).where(User.google_oauth_id == google_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing and existing.id != current_user.id:
        raise AppError(409, "conflict", "This Google account is linked to another user")

    current_user.google_oauth_id = google_id
    await db.commit()
    await db.refresh(current_user)
    return current_user


async def forgot_password(db: AsyncSession, email: str) -> None:
    email_lower = email.lower()
    stmt = select(User).where(User.email == email_lower)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return  # Do not leak enumeration

    plain_token = generate_opaque_token()
    hashed = hash_token(plain_token)

    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=hashed,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db.add(prt)
    await db.commit()

    # In a real app, send email via Celery here.
    # For now, print to console as requested.
    print(f"MAILPIT MOCK: Reset password link -> habittracker://reset?token={plain_token}")


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    hashed = hash_token(token)

    stmt = (
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hashed)
        .with_for_update()
    )
    result = await db.execute(stmt)
    prt = result.scalar_one_or_none()

    now = datetime.now(UTC)
    if not prt or prt.used_at is not None or prt.expires_at < now:
        if prt:
            await db.rollback()
        raise AppError(400, "invalid_token", "Invalid or expired reset token")

    # Valid token
    prt.used_at = now

    # Update password
    stmt_user = select(User).where(User.id == prt.user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one()
    user.password_hash = hash_password(new_password)

    # Revoke all active refresh tokens
    revoke_stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.execute(revoke_stmt)
    await db.commit()
