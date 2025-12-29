from typing import AsyncGenerator
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.database import engine

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Returns a generator that yields an AsyncSession object.This is for fastapi Dependency INJECTION.
    """
    async with AsyncSession(engine) as session:
        yield session

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)