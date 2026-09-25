from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import check_rate_limit, get_current_user, get_db
from app.models.user import User as DBUser
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    GoogleLinkRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    Tokens,
)
from app.schemas.user import User as UserSchema
from app.services import auth_service

router = APIRouter()


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await check_rate_limit("register", get_client_ip(request), payload.email)
    user, tokens = await auth_service.register_user(db, payload)
    return {"user": user, "tokens": tokens}


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await check_rate_limit("login", get_client_ip(request), payload.email)
    user, tokens = await auth_service.login_user(db, payload)
    return {"user": user, "tokens": tokens}


@router.post("/google", response_model=AuthResponse)
async def google(
    payload: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user, tokens = await auth_service.google_auth(db, payload)
    return {"user": user, "tokens": tokens}


@router.post("/google/link", response_model=UserSchema)
async def google_link(
    payload: GoogleLinkRequest,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DBUser:
    user = await auth_service.google_link(db, current_user, payload)
    return user


@router.post("/refresh", response_model=Tokens)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> Tokens:
    tokens = await auth_service.refresh_tokens(db, payload.refresh_token)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    await auth_service.logout_user(db, payload.refresh_token)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def password_forgot(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    await check_rate_limit("password_forgot", get_client_ip(request), payload.email)
    await auth_service.forgot_password(db, payload.email)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    await auth_service.reset_password(db, payload.token, payload.new_password)
