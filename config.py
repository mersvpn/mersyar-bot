# ===== IMPORTS & DEPENDENCIES =====
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
# This should be one of the first things to run.
load_dotenv()

# Initialize logger for this module
LOGGER = logging.getLogger(__name__)


# ===== CONFIGURATION CLASS =====
class Config:
    """
    Loads all configuration from environment variables.
    This class centralizes all configuration logic. It raises ValueError
    for critical missing variables and logs warnings for optional ones.
    """
    # --- Telegram Bot Configuration (Critical) ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        LOGGER.critical("CRITICAL: TELEGRAM_BOT_TOKEN is not set in the .env file.")
        raise ValueError("CRITICAL: TELEGRAM_BOT_TOKEN is not set in the .env file.")

    # --- Marzban Panel Configuration (Critical) ---
    MARZBAN_BASE_URL = os.getenv("MARZBAN_BASE_URL")
    MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME")
    MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")
    if not all([MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD]):
        LOGGER.critical("CRITICAL: Marzban credentials (URL, USERNAME, PASSWORD) are not fully set.")
        raise ValueError("CRITICAL: Marzban credentials (URL, USERNAME, PASSWORD) are not fully set.")

    # --- Admin User IDs (Optional but Recommended) ---
    # This list controls who has access to the administrative parts of the bot.
    try:
        raw_ids = os.getenv("AUTHORIZED_USER_IDS")
        if raw_ids:
            # Split the comma-separated string, strip whitespace from each part,
            # filter out any empty strings, and convert to integer.
            AUTHORIZED_USER_IDS = [int(uid.strip()) for uid in raw_ids.split(',') if uid.strip()]
            if not AUTHORIZED_USER_IDS:
                LOGGER.warning("AUTHORIZED_USER_IDS is defined but empty after parsing. No admin users will be recognized.")
                AUTHORIZED_USER_IDS = []
        else:
            # The variable is not set at all.
            AUTHORIZED_USER_IDS = []
            LOGGER.warning("AUTHORIZED_USER_IDS is not set. No admin users will be recognized.")
    except (ValueError, AttributeError):
        # This catches errors if the string contains non-integer values.
        AUTHORIZED_USER_IDS = []
        LOGGER.error("AUTHORIZED_USER_IDS contains invalid (non-integer) values. No admin users will be recognized.")

    # --- Support Configuration (Optional) ---
    # If set, a "Support" button will be shown on the customer's main menu.
    SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")
    if not SUPPORT_USERNAME:
        LOGGER.warning("SUPPORT_USERNAME is not set. The 'Support' button will not be shown to customers.")


# Create a single, immutable instance of the configuration to be imported by other modules.
# This pattern is known as a "singleton".
config = Config()