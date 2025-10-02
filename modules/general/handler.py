# FILE: modules/general/handler.py (MODIFIED FOR FORCED JOIN)

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
    ApplicationHandlerStop,
    CallbackQueryHandler  # (✨ NEW) Import CallbackQueryHandler
)

from modules.bot_settings.data_manager import is_bot_active
from config import config

from .actions import (
    start, 
    show_my_id, 
    switch_to_admin_view,
    handle_deep_link  
)
# (✨ MODIFIED) Corrected the import path for auth
from shared.auth import admin_only


MAINTENANCE_MESSAGE = (
    "**🛠 ربات در حال تعمیر و به‌روزرسانی است**\n\n"
    "در حال حاضر امکان پاسخگویی وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید.\n\n"
    "از شکیبایی شما سپاسگزاریم."
)

async def maintenance_gatekeeper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_bot_active():
        user = update.effective_user
        if user and user.id in config.AUTHORIZED_USER_IDS:
            return

        if update.message:
            await update.message.reply_markdown(MAINTENANCE_MESSAGE)
        raise ApplicationHandlerStop

def register(application: Application):
    # This handler runs before all others to check for maintenance mode.
    application.add_handler(TypeHandler(Update, maintenance_gatekeeper), group=-1)
    
    # --- CORE COMMANDS ---
    application.add_handler(CommandHandler("start", handle_deep_link), group=1)
    application.add_handler(CommandHandler("myid", show_my_id), group=1)
    
    # (✨ NEW) This handler listens for the "I have joined" button click
    # It simply re-runs the start command, which will trigger the decorator again.
    application.add_handler(CallbackQueryHandler(start, pattern=r'^check_join_status$'), group=1)

    # --- ADMIN-SPECIFIC HANDLERS ---
    # This handler is ONLY for the "Back to Admin Panel" button, which is exclusive to admins.
    application.add_handler(MessageHandler(
        filters.Regex('^↩️ بازگشت به پنل ادمین$') & filters.User(user_id=config.AUTHORIZED_USER_IDS), 
        switch_to_admin_view
    ), group=1)
    
    # NOTE: All customer-facing buttons ('Shop', 'My Services', etc.) are now correctly
    # registered in the customer module's handler to avoid conflicts and ensure
    # conversations work reliably. This file is now clean and focused.