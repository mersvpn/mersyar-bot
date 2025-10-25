# --- START OF FILE database/crud/non_renewal_user.py ---
import logging
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.dialects.mysql import insert as mysql_insert

from ..engine import get_session
from ..models.non_renewal_user import NonRenewalUser

LOGGER = logging.getLogger(__name__)


async def get_all_non_renewal_users() -> List[str]:
    """Retrieves a list of all usernames in the non-renewal list."""
    async with get_session() as session:
        stmt = select(NonRenewalUser.marzban_username)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def add_to_non_renewal_list(marzban_username: str) -> bool:
    """Adds a username to the non-renewal list, ignoring if it already exists."""
    stmt = mysql_insert(NonRenewalUser).values(marzban_username=marzban_username).prefix_with("IGNORE")
    
    async with get_session() as session:
        try:
            await session.execute(stmt)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to add '{marzban_username}' to non-renewal list: {e}", exc_info=True)
            return False


async def remove_from_non_renewal_list(marzban_username: str) -> bool:
    """Removes a username from the non-renewal list."""
    async with get_session() as session:
        try:
            stmt = delete(NonRenewalUser).where(NonRenewalUser.marzban_username == marzban_username)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to remove '{marzban_username}' from non-renewal list: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/non_renewal_user.py ---