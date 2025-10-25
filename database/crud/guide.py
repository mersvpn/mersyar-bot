# --- START OF FILE database/crud/guide.py (REVISED LOGIC) ---
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import select, delete
from ..engine import get_session
from ..models.guide import Guide

LOGGER = logging.getLogger(__name__)


async def get_all_guides() -> List[Guide]:
    """Retrieves all guides from the database, sorted by title."""
    async with get_session() as session:
        stmt = select(Guide).order_by(Guide.title.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_guide_by_key(guide_key: str) -> Optional[Guide]:
    """Retrieves a single guide by its primary key (guide_key)."""
    async with get_session() as session:
        return await session.get(Guide, guide_key)


async def add_or_update_guide(guide_data: Dict[str, Any]) -> bool:
    """
    Adds a new guide or updates an existing one based on guide_key.
    This version uses a safer read-then-update approach.
    """
    guide_key = guide_data.get('guide_key')
    if not guide_key:
        LOGGER.error("Cannot save guide without a 'guide_key'.")
        return False

    async with get_session() as session:
        try:
            # Step 1: Try to get the existing guide
            db_guide = await session.get(Guide, guide_key)

            if db_guide:
                # Step 2a: If it exists, update its attributes
                for key, value in guide_data.items():
                    if hasattr(db_guide, key):
                        setattr(db_guide, key, value)
            else:
                # Step 2b: If it doesn't exist, create a new one
                db_guide = Guide(**guide_data)
                session.add(db_guide)
            
            # Step 3: Commit the changes
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to add or update guide '{guide_key}': {e}", exc_info=True)
            return False


async def delete_guide(guide_key: str) -> bool:
    """Deletes a guide from the database by its key."""
    async with get_session() as session:
        try:
            stmt = delete(Guide).where(Guide.guide_key == guide_key)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to delete guide '{guide_key}': {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/guide.py (REVISED LOGIC) ---