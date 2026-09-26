from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.stats import AccountStatsResponse
from app.services.stats_service import get_account_stats

router = APIRouter(tags=["stats"])

@router.get("/overview", response_model=AccountStatsResponse)
async def get_overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AccountStatsResponse:
    return await get_account_stats(db, user)
