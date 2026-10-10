from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.db_url, echo=False)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    from database import models  # noqa: F401
    from database.seed import seed

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionMaker() as session:
        await seed(session)
