from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.features.users.schemas import UserCreateRequest, UserResponse
from app.features.users.service import get_or_create_user
from app.platform.db.session import get_async_session

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserResponse)
async def create_user(
    payload: UserCreateRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user = await get_or_create_user(db, payload.email)
    return UserResponse(id=str(user.id), email=user.email)
