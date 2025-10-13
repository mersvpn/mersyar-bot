# --- START OF FILE database/engine.py (REVISED FOR WINDOWS) ---
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .db_config import db_config

LOGGER = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Initializes the database engine and session maker."""
    global _engine, _async_session_maker

    if not db_config.is_configured():
        LOGGER.warning("Database is not configured. Skipping SQLAlchemy engine creation.")
        return

    if _engine:
        LOGGER.info("Database engine is already initialized.")
        return

    db_url = (
        f"mysql+aiomysql://{db_config.DB_USER}:{db_config.DB_PASSWORD}@" # <--- تغییر اصلی اینجاست
        f"{db_config.DB_HOST}/{db_config.DB_NAME}?charset=utf8mb4"
    )

    try:
        _engine = create_async_engine(
            db_url,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
        )

        _async_session_maker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        LOGGER.info("SQLAlchemy async engine and session maker created successfully.")
    except Exception as e:
        LOGGER.critical(f"Failed to create SQLAlchemy engine: {e}", exc_info=True)
        _engine = None
        _async_session_maker = None


async def close_db() -> None:
    """Closes the database engine connections."""
    global _engine
    if _engine:
        LOGGER.info("Closing SQLAlchemy engine connections.")
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session."""
    if _async_session_maker is None:
        raise ConnectionError("Database session maker is not initialized. Call init_db() first.")

    async with _async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# --- END OF FILE database/engine.py (REVISED FOR WINDOWS) ---