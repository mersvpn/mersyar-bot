# config.py
# (کد کامل و جایگزین)

import os
import logging
from dotenv import load_dotenv

load_dotenv()
LOGGER = logging.getLogger(__name__)

class Config:
    # --- Telegram Bot Configuration (Critical for startup) ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        LOGGER.critical("CRITICAL: TELEGRAM_BOT_TOKEN is not set in the .env file.")
        raise ValueError("CRITICAL: TELEGRAM_BOT_TOKEN is not set in the .env file.")

    # --- Marzban Panel Configuration (Now managed dynamically, not from .env) ---
    # The following variables are no longer loaded from .env at startup.
    # They will be loaded from marzban_credentials.json by the API functions.
    # MARZBAN_BASE_URL = os.getenv("MARZBAN_BASE_URL")
    # MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME")
    # MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")

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