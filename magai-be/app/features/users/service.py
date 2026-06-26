from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User


async def get_or_create_user(db: AsyncSession, email: str) -> User:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(email=email)
    db.add(user)
    await db.flush()
    return user
