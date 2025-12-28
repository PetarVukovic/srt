from sqlmodel import create_engine,SQLModel
from app.core.config import get_settings
from app.db.models import __all__
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    str(get_settings().database_url),
    echo=True,
)
import asyncio

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(create_db_and_tables())