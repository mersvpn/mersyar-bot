# --- START OF FILE database/crud/admin_daily_note.py ---
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.admin_daily_note import AdminDailyNote

LOGGER = logging.getLogger(__name__)


async def get_all_daily_notes() -> List[AdminDailyNote]:
    """Retrieves all admin daily notes, sorted by title."""
    async with get_session() as session:
        stmt = select(AdminDailyNote).order_by(AdminDailyNote.title.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_daily_note_by_id(note_id: str) -> Optional[AdminDailyNote]:
    """Retrieves a single daily note by its primary key (UUID)."""
    async with get_session() as session:
        return await session.get(AdminDailyNote, note_id)


async def add_daily_note(note_data: Dict[str, Any]) -> Optional[AdminDailyNote]:
    """Adds a new daily note to the database."""
    async with get_session() as session:
        try:
            new_note = AdminDailyNote(**note_data)
            session.add(new_note)
            await session.commit()
            await session.refresh(new_note)
            return new_note
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to add daily note: {e}", exc_info=True)
            return None


async def update_daily_note(note_id: str, update_data: Dict[str, Any]) -> bool:
    """Updates an existing daily note."""
    async with get_session() as session:
        try:
            stmt = update(AdminDailyNote).where(AdminDailyNote.id == note_id).values(**update_data)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to update daily note {note_id}: {e}", exc_info=True)
            return False


async def delete_daily_note_by_id(note_id: str) -> bool:
    """Deletes a daily note from the database."""
    async with get_session() as session:
        try:
            stmt = delete(AdminDailyNote).where(AdminDailyNote.id == note_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to delete daily note {note_id}: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/admin_daily_note.py ---