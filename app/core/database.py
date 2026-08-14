from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

is_sqlite = "sqlite" in settings.ASYNC_DATABASE_URL

if is_sqlite:
    async_engine = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        echo=False,
        future=True
    )
    sync_engine = create_engine(
        settings.SYNC_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    async_engine = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10
    )
    sync_engine = create_engine(
        settings.SYNC_DATABASE_URL,
        echo=False,
        pool_pre_ping=True
    )

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    """FastAPI Async DB session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
