# FILE: modules/bot_settings/data_manager.py (REVISED WITH SYNC FUNCTION and CACHING)

import json
import logging
from typing import Dict, Any

LOGGER = logging.getLogger(__name__)
STATUS_FILE_PATH = "bot_status.json"

# In-memory cache for the bot's status
_status_cache: Dict[str, Any] = {}

def _load_status_sync():
    """
    Synchronously loads status from file into the cache.
    This is called once when the module is first imported.
    """
    global _status_cache
    try:
        with open(STATUS_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                _status_cache = {'is_active': True} # Default for empty file
            else:
                _status_cache = json.loads(content)
        LOGGER.info(f"Bot status cache initialized from {STATUS_FILE_PATH}: {_status_cache}")
    except (FileNotFoundError, json.JSONDecodeError):
        _status_cache = {'is_active': True} # Default if file doesn't exist or is corrupt
        _save_status_sync(_status_cache) # Create the file with default value
        LOGGER.warning(f"{STATUS_FILE_PATH} not found or invalid. Initialized with default: {_status_cache}")

def _save_status_sync(status_data: Dict[str, Any]):
    """Synchronously saves status to the file and updates the cache."""
    global _status_cache
    _status_cache = status_data
    try:
        with open(STATUS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=4)
        LOGGER.info(f"Bot status saved to {STATUS_FILE_PATH}: {status_data}")
    except IOError as e:
        LOGGER.error(f"Could not write to status file {STATUS_FILE_PATH}: {e}")

# --- Initialize the cache as soon as the bot starts ---
_load_status_sync()

async def is_bot_active() -> bool:
    """
    Asynchronously checks if the bot is active using the in-memory cache.
    """
    LOGGER.info("--- Checking bot active status (async) ---")
    is_active = _status_cache.get('is_active', True)
    LOGGER.info(f"is_bot_active check: Key 'is_active' is {is_active}. Returning this value.")
    return is_active

def is_bot_active_sync() -> bool:
    """
    Synchronous version for use in filters. Reads directly from the in-memory cache.
    """
    return _status_cache.get('is_active', True)

async def set_bot_status(is_active: bool):
    """
    Sets the bot's active status. This function is now async-friendly
    but calls the synchronous save function to ensure cache and file are updated.
    """
    new_data = {"is_active": is_active}
    LOGGER.info(f"Request to set bot status. Saving new state to {STATUS_FILE_PATH}: {new_data}")
    _save_status_sync(new_data)