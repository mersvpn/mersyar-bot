# ===== IMPORTS & DEPENDENCIES =====
import logging
import logging.handlers
import sys
import asyncio
from telegram.ext import Application, ApplicationBuilder, ContextTypes

# --- Local Imports ---
from config import config

# Import module registers
from modules.general import handler as general_handler
from modules.customer import handler as customer_handler
from modules.marzban import handler as marzban_handler
from modules.reminder import handler as reminder_handler
from modules.financials import handler as financials_handler

# Import the API client to close it gracefully
from modules.marzban.actions import api as marzban_api

# --- CONSTANTS ---
LOG_FILE = "bot.log"
LOGGER = logging.getLogger(__name__)

# ===== LOGGING SETUP =====
def setup_logging():
    """Configures the logging for the entire application."""
    # Prevent setting up logging more than once
    if logging.getLogger().hasHandlers():
        return

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File handler for logging to a rotating file
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler for logging to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Set httpx logger to a higher level to avoid spam
    logging.getLogger("httpx").setLevel(logging.WARNING)

    LOGGER.info("Logging configured successfully.")

# ===== CORE BOT FUNCTIONS =====
async def heartbeat(context: ContextTypes.DEFAULT_TYPE):
    """A simple job that logs a message to confirm the bot is alive."""
    LOGGER.info("❤️ Heartbeat: Bot is alive and the JobQueue is running.")

async def post_shutdown(application: Application):
    """
    This function is called by Application.run_polling() upon shutdown.
    It's the ideal place to close resources like the httpx client.
    """
    LOGGER.info("Shutdown signal received. Closing resources...")
    await marzban_api.close_client()
    LOGGER.info("HTTPX client closed gracefully.")

# ===== INITIALIZATION & STARTUP =====
def main() -> None:
    """The main entry point of the bot."""
    setup_logging()

    LOGGER.info("===================================")
    LOGGER.info("🚀 Starting bot...")

    # --- CORRECTED: ApplicationBuilder manages the JobQueue ---
    # We no longer need to instantiate JobQueue manually.
    # The `post_shutdown` function is registered here.
    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .post_shutdown(post_shutdown)
        .build()
    )

    # --- Handler Registration ---
    # Register handlers from different modules. The `group` parameter helps control execution order.
    # Lower group numbers run first.
    # Group 0: Admin-only handlers, highest priority.
    # Group 1: General/Customer handlers, lower priority.

    LOGGER.info("Registering marzban handlers (Admin-Only, Priority 0)...")
    marzban_handler.register(application)

    LOGGER.info("Registering financials handlers (Admin-Only, Priority 0)...")
    financials_handler.register(application)

    # --- CORRECTED: Reminder handler now only needs the application object ---
    LOGGER.info("Registering reminder handlers (Admin-Only, Priority 0)...")
    reminder_handler.register(application)

    LOGGER.info("Registering general handlers (Public, Priority 1)...")
    general_handler.register(application)

    LOGGER.info("Registering customer handlers (Public, Priority 1)...")
    customer_handler.register(application)


    # --- Job Scheduling ---
    # Schedule the heartbeat job to confirm the bot is running.
    if application.job_queue:
        application.job_queue.run_repeating(heartbeat, interval=3600, first=10, name="heartbeat")
        LOGGER.info("❤️ Heartbeat job scheduled to run every hour.")
    else:
        LOGGER.warning("JobQueue is not available. Heartbeat job not scheduled.")

    # Start the bot
    LOGGER.info("All handlers registered. Starting polling...")
    application.run_polling()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # This will catch critical startup errors, e.g., if the token is invalid.
        # It ensures that even if `setup_logging` fails or runs after an error, the crash is logged.
        logging.basicConfig() # Ensure logger is configured for this one-off message
        logging.getLogger(__name__).critical(
            "A critical error occurred in the main execution block, causing the bot to stop.",
            exc_info=True
        )