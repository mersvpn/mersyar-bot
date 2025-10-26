# --- START OF FILE bot.py (REVISED) ---
import logging
import logging.handlers
import sys
import os
import asyncio
from modules.broadcaster import handler as broadcaster_handler
from modules.reminder.actions.jobs import cleanup_expired_test_accounts
from modules.financials import handler as financials_handler
from modules.payment import handler as payment_handler
from modules.user_info import handler as user_info_handler
from database.crud import user as crud_user

from shared.translator import init_translator


init_translator()

import argparse

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters,TypeHandler

from config import config
from modules.marzban.actions import api as marzban_api
# --- MODIFIED IMPORTS ---
from database import engine as db_engine
# --- ------------------ ---

LOG_FILE = "bot.log"
LOGGER = logging.getLogger(__name__)

def setup_logging():
    if logging.getLogger().hasHandlers(): return
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    LOGGER.info("Logging configured successfully.")

async def debug_update_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        user_info = f"User(ID:{update.effective_user.id}, Name:'{update.effective_user.full_name}')"
    else:
        user_info = "User:N/A (Channel or System Update)"

    if update.message and update.message.text:
        text = update.message.text
        char_codes = [ord(c) for c in text]
        LOGGER.info(f"[DEBUG_LOGGER] Message from {user_info} | Text: '{text}' | CharCodes: {char_codes}")
    
    elif update.callback_query:
        data = update.callback_query.data
        LOGGER.info(f"[DEBUG_LOGGER] Callback from {user_info} | Data: '{data}'")
    
    else:
        LOGGER.info(f"[DEBUG_LOGGER] Received an unhandled update type from {user_info}")

async def heartbeat(context: ContextTypes.DEFAULT_TYPE):
    LOGGER.info("❤️ Heartbeat: Bot is alive and the JobQueue is running.")

async def update_user_activity(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(update, Update) and update.effective_user:
        user_id = update.effective_user.id
        try:
            await crud_user.update_last_activity(user_id)
        except Exception as e:
            LOGGER.error(f"Failed to update last activity for {user_id}: {e}")


async def post_init(application: Application):
    await db_engine.init_db()
    # await db_manager.create_pool() # This is now removed
    await marzban_api.init_marzban_credentials()

    from modules.general import handler as general_handler
    from modules.marzban import handler as marzban_handler
    from modules.customer import handler as customer_handler
    from modules.bot_settings import handler as bot_settings_handler
    from modules.reminder import handler as reminder_handler
    from modules.guides import handler as guides_handler
    general_handler.register(application)
    marzban_handler.register(application)
    customer_handler.register(application)
    bot_settings_handler.register(application)
    reminder_handler.register(application)
    guides_handler.register(application)
    financials_handler.register(application)
    payment_handler.register(application)
    broadcaster_handler.register(application)
    user_info_handler.register(application)
    application.add_handler(TypeHandler(Update, update_user_activity), group=-1)


async def post_shutdown(application: Application):
    LOGGER.info("Shutdown signal received. Closing resources...")
    await marzban_api.close_client()
    LOGGER.info("HTTPX client closed gracefully.")
    # await db_manager.close_pool() # This is now removed
    LOGGER.info("Database pool (legacy) is no longer used.")
    await db_engine.close_db()
    LOGGER.info("Database engine (SQLAlchemy) closed gracefully.")

def main() -> None:
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Mersyar Telegram Bot")
    parser.add_argument("--port", type=int, help="Port to run the webhook on.")
    args = parser.parse_args()

    LOGGER.info("===================================")
    LOGGER.info("🚀 Starting bot...")

    from modules.bot_settings import handler as bot_settings_handler
    from modules.general import handler as general_handler
    from modules.customer import handler as customer_handler
    from modules.marzban import handler as marzban_handler
    from modules.reminder import handler as reminder_handler
    from modules.financials import handler as financials_handler
    from modules.stats import handler as stats_handler
    from modules.guides import handler as guides_handler

    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, debug_update_logger), group=-1)
    application.add_handler(CallbackQueryHandler(debug_update_logger), group=-1)
    LOGGER.info("Universal debug logger has been activated.")
    
    broadcaster_handler.register(application)
    marzban_handler.register(application)
    
    general_handler.register(application)
    financials_handler.register(application)
    reminder_handler.register(application)
    customer_handler.register(application)
    bot_settings_handler.register(application)
    stats_handler.register(application)
    guides_handler.register(application)
    payment_handler.register(application)
    
    if application.job_queue:
        application.job_queue.run_repeating(heartbeat, interval=3600, first=10, name="heartbeat")
        application.job_queue.run_repeating(cleanup_expired_test_accounts, interval=3600, first=60, name="cleanup_test_accounts")
        LOGGER.info("❤️ Heartbeat and Test Account Cleanup jobs scheduled to run every hour.")

    BOT_DOMAIN = os.getenv("BOT_DOMAIN")
    WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
    
    if args.port:
        PORT = args.port
        LOGGER.info(f"Port {PORT} received from command-line argument.")
    else:
        PORT = int(os.getenv("BOT_PORT", 8081))
        LOGGER.info(f"Port {PORT} loaded from environment or default.")

    if not all([BOT_DOMAIN, WEBHOOK_SECRET_TOKEN]):
        LOGGER.info("BOT_DOMAIN or WEBHOOK_SECRET_TOKEN not found. Starting in polling mode.")
        application.run_polling()
    else:
        webhook_url = f"https://{BOT_DOMAIN}/{WEBHOOK_SECRET_TOKEN}"
        LOGGER.info(f"Starting in webhook mode on port {PORT}. URL: {webhook_url}")
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=WEBHOOK_SECRET_TOKEN, webhook_url=webhook_url, secret_token=WEBHOOK_SECRET_TOKEN)

if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.basicConfig()
        logging.getLogger(__name__).critical("A critical error occurred in the main execution block.", exc_info=True)

# --- END OF FILE bot.py (REVISED) ---