# --- START OF FILE database/crud/marzban_link.py (REVISED) ---

import logging
from typing import List, Optional, Dict
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.marzban_link import MarzbanTelegramLink
from ..models.user import User

LOGGER = logging.getLogger(__name__)

# Renamed from link_user_to_telegram for clarity on create/update behavior
async def create_or_update_link(marzban_username: str, telegram_user_id: int) -> bool:
    """Links a Marzban username to a Telegram user ID, or updates an existing link."""
    async with get_session() as session:
        try:
            existing_link = await session.get(MarzbanTelegramLink, marzban_username)
            if existing_link:
                existing_link.telegram_user_id = telegram_user_id
            else:
                new_link = MarzbanTelegramLink(
                    marzban_username=marzban_username,
                    telegram_user_id=telegram_user_id,
                )
                session.add(new_link)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to link '{marzban_username}' to {telegram_user_id}: {e}", exc_info=True)
            return False

# Renamed from unlink_user_from_telegram for clarity
async def delete_marzban_link(marzban_username: str) -> bool:
    """Removes the link for a given Marzban username."""
    async with get_session() as session:
        try:
            stmt = delete(MarzbanTelegramLink).where(MarzbanTelegramLink.marzban_username == marzban_username)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to delete link for '{marzban_username}': {e}", exc_info=True)
            return False

# Renamed for consistency
async def get_telegram_id_by_marzban_username(marzban_username: str) -> Optional[int]:
    """Retrieves the Telegram user ID linked to a Marzban username."""
    async with get_session() as session:
        link = await session.get(MarzbanTelegramLink, marzban_username)
        return link.telegram_user_id if link else None

async def get_linked_marzban_usernames(telegram_user_id: int) -> List[str]:
    """Retrievis all Marzban usernames linked to a specific Telegram user ID."""
    async with get_session() as session:
        stmt = select(MarzbanTelegramLink.marzban_username).where(
            MarzbanTelegramLink.telegram_user_id == telegram_user_id
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

# --- NEW FUNCTIONS ---

async def set_auto_renew_status(telegram_user_id: int, marzban_username: str, status: bool) -> bool:
    """Sets the auto-renew status for a specific link."""
    async with get_session() as session:
        try:
            stmt = (
                update(MarzbanTelegramLink)
                .where(MarzbanTelegramLink.telegram_user_id == telegram_user_id, MarzbanTelegramLink.marzban_username == marzban_username)
                .values(auto_renew=status)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            LOGGER.error(f"Could not set auto-renew for {marzban_username}: {e}", exc_info=True)
            return False

async def is_auto_renew_enabled(telegram_user_id: int, marzban_username: str) -> bool:
    """Checks if auto-renew is enabled for a specific link."""
    async with get_session() as session:
        stmt = select(MarzbanTelegramLink.auto_renew).where(MarzbanTelegramLink.telegram_user_id == telegram_user_id, MarzbanTelegramLink.marzban_username == marzban_username)
        result = await session.execute(stmt)
        status = result.scalar_one_or_none()
        return status if status is not None else False

async def get_all_marzban_links_map() -> Dict[str, int]:
    """Returns a dictionary mapping marzban_username to telegram_user_id."""
    async with get_session() as session:
        stmt = select(MarzbanTelegramLink.marzban_username, MarzbanTelegramLink.telegram_user_id)
        result = await session.execute(stmt)
        return {row.marzban_username: row.telegram_user_id for row in result.all()}

async def get_all_auto_renew_links() -> List[MarzbanTelegramLink]:
    """Retrieves all links that have auto-renew enabled."""
    async with get_session() as session:
        stmt = select(MarzbanTelegramLink).where(MarzbanTelegramLink.auto_renew == True)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
async def get_links_by_telegram_id(telegram_id: int):
    async with get_session() as session:
        try:
            result = await session.execute(
                 select(MarzbanTelegramLink).where(MarzbanTelegramLink.telegram_user_id == telegram_id)
            )
            return result.scalars().all()
        except Exception as e:
            LOGGER.error(f"Failed to get links by telegram_id {telegram_id}: {e}")
            return []


# --- END OF FILE database/crud/marzban_link.py (REVISED) ---