# --- START OF FILE database/crud/user_note.py (REVISED) ---
import logging
from decimal import Decimal
from typing import Optional, List # <--- List را اضافه کنید

from sqlalchemy import delete # <--- delete را اضافه کنید
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # <--- select را اضافه کنید

from ..engine import get_session
from ..models.user_note import UserNote

LOGGER = logging.getLogger(__name__)


async def get_user_note(marzban_username: str) -> Optional[UserNote]:
    """Retrieves subscription details for a specific marzban user."""
    async with get_session() as session:
        return await session.get(UserNote, marzban_username)


async def create_or_update_user_note(
    marzban_username: str,
    price: Optional[Decimal] = None,
    duration: Optional[int] = None,
    data_limit_gb: Optional[int] = None,
    note: Optional[str] = None,
    is_test_account: Optional[bool] = None,  # <--- این خط اضافه شده
) -> Optional[UserNote]:
    """
    Creates a new user note or updates an existing one with new details.
    Pass a value to a parameter to update it.
    """
    async with get_session() as session:
        try:
            db_note = await session.get(UserNote, marzban_username)

            if not db_note:
                db_note = UserNote(username=marzban_username)
                session.add(db_note)

            if price is not None:
                db_note.subscription_price = price
            if duration is not None:
                db_note.subscription_duration = duration
            if data_limit_gb is not None:
                db_note.subscription_data_limit_gb = data_limit_gb
            if note is not None:
                db_note.note = note
            if is_test_account is not None:  # <--- این سه خط اضافه شده
                db_note.is_test_account = is_test_account

            await session.commit()
            await session.refresh(db_note)
            return db_note
        except Exception as e:
            LOGGER.error(f"Could not create or update user note for '{marzban_username}': {e}", exc_info=True)
            return None

# --- تابع جدید ---
async def delete_user_note(marzban_username: str) -> bool:
    """Deletes a user note completely by marzban_username."""
    async with get_session() as session:
        try:
            stmt = delete(UserNote).where(UserNote.username == marzban_username)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            LOGGER.error(f"Could not delete user note for '{marzban_username}': {e}", exc_info=True)
            return False


async def get_all_users_with_notes() -> List[UserNote]:
    """Retrieves all user notes from the database."""
    async with get_session() as session:
        stmt = select(UserNote)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
async def get_all_test_accounts() -> List[UserNote]:
    """Retrieves all user notes that are marked as test accounts."""
    async with get_session() as session:
        stmt = select(UserNote).where(UserNote.is_test_account == True)
        result = await session.execute(stmt)
        return list(result.scalars().all())

# --- END OF FILE database/crud/user_note.py (REVISED) ---