"""Profile routes — GET/PATCH /api/v1/users/me."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User as DBUser
from app.schemas.user import User as UserSchema
from app.schemas.user import UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def get_me(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    return user_service.get_profile(current_user)


@router.patch("/me", response_model=UserSchema)
async def update_me(
    payload: UserUpdate,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DBUser:
    return await user_service.update_profile(db, current_user, payload)
