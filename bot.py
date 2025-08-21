import logging
import logging.handlers
import sys
import os
import asyncio
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from config import config
from modules.bot_settings import handler as bot_settings_handler
from modules.general import handler as general_handler
from modules.customer import handler as customer_handler
from modules.marzban import handler as marzban_handler
from modules.reminder import handler as reminder_handler
from modules.financials import handler as financials_handler
from modules.marzban.actions import api as marzban_api
from database import db_manager

LOG_FILE = "bot.log"
LOGGER = logging.getLogger(__name__)

def setup_logging():
    if logging.getLogger().hasHandlers():
        return
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    LOGGER.info("Logging configured successfully.")

async def heartbeat(context: ContextTypes.DEFAULT_TYPE):
    LOGGER.info("❤️ Heartbeat: Bot is alive and the JobQueue is running.")

async def post_init(application: Application):
    await db_manager.create_pool()

async def post_shutdown(application: Application):
    LOGGER.info("Shutdown signal received. Closing resources...")
    await marzban_api.close_client()
    LOGGER.info("HTTPX client closed gracefully.")
    await db_manager.close_pool()
    LOGGER.info("Database pool closed gracefully.")

def main() -> None:
    setup_logging()
    LOGGER.info("===================================")
    LOGGER.info("🚀 Starting bot...")

    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    general_handler.register(application)
    marzban_handler.register(application)
    financials_handler.register(application)
    reminder_handler.register(application)
    customer_handler.register(application)
    bot_settings_handler.register(application)
    
    if application.job_queue:
        application.job_queue.run_repeating(heartbeat, interval=3600, first=10, name="heartbeat")
        LOGGER.info("❤️ Heartbeat job scheduled to run every hour.")
    else:
        LOGGER.warning("JobQueue is not available. Heartbeat job not scheduled.")

    BOT_DOMAIN = os.getenv("BOT_DOMAIN")
    WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
    PORT = 8080 

    if not all([BOT_DOMAIN, WEBHOOK_SECRET_TOKEN]):
        LOGGER.critical("CRITICAL: Webhook variables not set. Starting in Polling mode as a fallback...")
        application.run_polling()
    else:
        webhook_url = f"https://{BOT_DOMAIN}/{WEBHOOK_SECRET_TOKEN}"
        LOGGER.info(f"Starting bot in Webhook mode. URL: {webhook_url}, Port: {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=WEBHOOK_SECRET_TOKEN,
            webhook_url=webhook_url,
            secret_token=WEBHOOK_SECRET_TOKEN
        )

if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.basicConfig()
        logging.getLogger(__name__).critical(
            "A critical error occurred in the main execution block.",
            exc_info=True
        )