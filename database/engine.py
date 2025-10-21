# FILE: database/engine.py (FINAL, CORRECTED VERSION FOR YOUR STRUCTURE)

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# --- START OF CHANGES ---
# 1. Import the new function instead of the old class instance
from .db_config import get_database_url
# --- END OF CHANGES ---

LOGGER = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Initializes the database engine and session maker."""
    global _engine, _async_session_maker

    if _engine:
        LOGGER.info("Database engine is already initialized.")
        return

    try:
        # --- START OF CHANGES ---
        # 2. Call the function to get the database URL
        db_url = get_database_url()
        # --- END OF CHANGES ---

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
    
    except ValueError as ve:
        # This will catch the error from get_database_url if .env is not configured
        LOGGER.warning(f"Skipping SQLAlchemy engine creation: {ve}")
        _engine = None
        _async_session_maker = None
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
        # Re-try initialization if the first attempt (at startup) failed
        await init_db()
        if _async_session_maker is None:
            raise ConnectionError("Database session maker is not initialized and failed to re-initialize.")

    async with _async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()