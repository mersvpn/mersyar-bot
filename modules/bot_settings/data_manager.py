# FILE: modules/bot_settings/data_manager.py (CLEANED UP VERSION)

import json
import aiofiles
import logging

LOGGER = logging.getLogger(__name__)
STATUS_FILE_PATH = "bot_status.json"

async def _load_status_data():
    """Helper function to load data from the status JSON file."""
    LOGGER.debug(f"Attempting to load status from {STATUS_FILE_PATH}")
    try:
        async with aiofiles.open(STATUS_FILE_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            # Handle empty file case
            if not content.strip():
                raise json.JSONDecodeError("File is empty", content, 0)
            LOGGER.debug(f"Raw content from file: '{content}'")
            data = json.loads(content)
            LOGGER.debug(f"Successfully parsed JSON data: {data}")
            return data
    except FileNotFoundError:
        LOGGER.warning(f"{STATUS_FILE_PATH} not found. Creating with default active status.")
        # Directly call set_bot_status to create a clean file
        await set_bot_status(True)
        return {"is_active": True}
    except (json.JSONDecodeError, Exception) as e:
        LOGGER.error(f"Error reading or parsing {STATUS_FILE_PATH}: {e}. Resetting to default.")
        await set_bot_status(True)
        return {"is_active": True}

async def is_bot_active() -> bool:
    """
    Checks if the bot is currently in active mode.
    Returns True if active, False if in maintenance mode.
    """
    LOGGER.info("--- Checking bot active status ---")
    data = await _load_status_data()
    # Explicitly check for the correct key 'is_active'
    is_active_status = data.get("is_active", True)
    LOGGER.info(f"is_bot_active check: Key 'is_active' is {is_active_status}. Returning this value.")
    return is_active_status

async def set_bot_status(is_active: bool):
    """
    Sets the bot's status and saves it to the file, ensuring a clean state.
    This function now directly handles writing to the file.
    """
    new_data = {"is_active": is_active}
    LOGGER.info(f"Request to set bot status. Saving new state to {STATUS_FILE_PATH}: {new_data}")
    try:
        async with aiofiles.open(STATUS_FILE_PATH, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(new_data, indent=4))
    except Exception as e:
        LOGGER.error(f"Failed to write to {STATUS_FILE_PATH}: {e}")