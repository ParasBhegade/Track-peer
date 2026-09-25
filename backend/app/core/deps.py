import time
from collections.abc import AsyncGenerator

import jwt
import redis.asyncio as redis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models.user import User

# Redis connection for rate limiting
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, auto-closed after use."""
    async with async_session_factory() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        raise AppError(401, "token_invalid", "Missing access token")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as e:
        raise AppError(401, "token_expired", "Access token expired") from e
    except jwt.InvalidTokenError as e:
        raise AppError(401, "token_invalid", "Invalid access token") from e

    user_id = payload.get("sub")
    if not user_id:
        raise AppError(401, "token_invalid", "Invalid access token payload")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AppError(401, "token_invalid", "User no longer exists")

    return user


async def check_rate_limit(action: str, ip: str, email: str | None = None) -> None:
    """Check 5 req/min rate limit per IP and optionally per email."""
    current_minute = int(time.time() / 60)
    limit = 5

    keys = [f"auth:{action}:ip:{ip}:{current_minute}"]
    if email:
        keys.append(f"auth:{action}:email:{email.lower()}:{current_minute}")

    # Use pipeline to increment all keys efficiently
    pipeline = redis_client.pipeline()
    for key in keys:
        pipeline.incr(key)
    
    results = await pipeline.execute()

    # Set expiry for newly created keys
    pipeline = redis_client.pipeline()
    for i, count in enumerate(results):
        if count == 1:
            pipeline.expire(keys[i], 120)  # 2 minutes is enough for a 1-minute window key
        if count > limit:
            raise AppError(429, "rate_limited", "Too many requests, please try again later.")
            
    if len(pipeline.command_stack) > 0:
        await pipeline.execute()
