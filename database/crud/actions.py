# --- START OF FILE database/crud/actions.py ---
import logging
from ..engine import get_session
from ..models.user_note import UserNote
from ..models.marzban_link import MarzbanTelegramLink
from ..models.non_renewal_user import NonRenewalUser
from ..models.bot_managed_user import BotManagedUser

LOGGER = logging.getLogger(__name__)


async def cleanup_marzban_user_data(marzban_username: str) -> bool:
    """
    Completely removes all data associated with a Marzban username from the bot's database
    within a single transaction. This includes notes, links, and list entries.
    """
    async with get_session() as session:
        try:
            # Find all related objects to delete
            note = await session.get(UserNote, marzban_username)
            if note:
                await session.delete(note)

            link = await session.get(MarzbanTelegramLink, marzban_username)
            if link:
                await session.delete(link)

            non_renewal = await session.get(NonRenewalUser, marzban_username)
            if non_renewal:
                await session.delete(non_renewal)

            managed_user = await session.get(BotManagedUser, marzban_username)
            if managed_user:
                await session.delete(managed_user)
            
            # Commit all deletions at once
            await session.commit()
            LOGGER.info(f"Successfully cleaned up all data for Marzban user '{marzban_username}'.")
            return True
        except Exception as e:
            await session.rollback()
            LOGGER.error(
                f"Transaction rolled back during cleanup for Marzban user '{marzban_username}': {e}",
                exc_info=True
            )
            return False

# --- END OF FILE database/crud/actions.py ---