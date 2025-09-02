import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- This is the key fix ---
# Explicitly find and load the .env file from the project's root directory.
# This makes the bot's startup independent of where the script is run from.
try:
    # This finds the root directory of the project (where bot.py is)
    project_root = Path(__file__).parent.parent.resolve()
    dotenv_path = project_root / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # Fallback for environments where the structure might be different
        load_dotenv()
except Exception:
    # Generic fallback if path resolution fails for any reason
    load_dotenv()
# --- End of fix ---


LOGGER = logging.getLogger(__name__)

class Config:
    # --- Telegram Bot Configuration (Critical for startup) ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        LOGGER.critical("CRITICAL: TELEGRAM_BOT_TOKEN is not set in the .env file.")
        raise ValueError("CRITICAL: TELEGRAM_BOT_TOKEN is not set in the .env file.")

    # --- Admin User IDs (Recommended) ---
    try:
        raw_ids = os.getenv("AUTHORIZED_USER_IDS")
        AUTHORIZED_USER_IDS = [int(uid.strip()) for uid in raw_ids.split(',') if uid.strip()] if raw_ids else []
        if not AUTHORIZED_USER_IDS:
            LOGGER.warning("AUTHORIZED_USER_IDS is not set or is empty. No admin users will be recognized.")
    except (ValueError, AttributeError):
        AUTHORIZED_USER_IDS = []
        LOGGER.error("AUTHORIZED_USER_IDS contains invalid values. No admin users will be recognized.")

    # --- Support Configuration (Optional) ---
    SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")
    if not SUPPORT_USERNAME:
        LOGGER.info("SUPPORT_USERNAME is not set. 'Support' button will not be shown.")

config = Config()