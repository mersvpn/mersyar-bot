# --- START OF FILE modules/marzban/actions/data_manager.py ---
import logging
from typing import Dict

from config import config
from database.crud import (
    marzban_link as crud_marzban_link,
    bot_managed_user as crud_managed_user,
    actions as crud_actions
)

LOGGER = logging.getLogger(__name__)


def normalize_username(username: str) -> str:
    """Converts a username to a standardized format (lowercase)."""
    return username.lower()


async def is_user_admin(user_id: int) -> bool:
    """Checks if a user ID belongs to an admin."""
    return user_id in config.AUTHORIZED_USER_IDS


async def link_user_to_telegram(marzban_username: str, telegram_user_id: int) -> bool:
    """Wrapper for crud_marzban_link.create_or_update_link."""
    return await crud_marzban_link.create_or_update_link(
        normalize_username(marzban_username), telegram_user_id
    )


async def add_user_to_managed_list(marzban_username: str) -> bool:
    """Wrapper for crud_managed_user.add_to_managed_list."""
    return await crud_managed_user.add_to_managed_list(
        normalize_username(marzban_username)
    )


async def cleanup_marzban_user_data(marzban_username: str) -> bool:
    """
    Wrapper for the transactional cleanup function in crud.actions.
    Removes all data for a Marzban user from the bot's database.
    """
    return await crud_actions.cleanup_marzban_user_data(
        normalize_username(marzban_username)
    )


async def load_users_map() -> Dict[str, int]:
    """
    Loads a dictionary mapping Marzban usernames to Telegram user IDs.
    Uses the optimized function from the crud layer.
    """
    return await crud_marzban_link.get_all_marzban_links_map()

# --- END OF FILE modules/marzban/actions/data_manager.py ---