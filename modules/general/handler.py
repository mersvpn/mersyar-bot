# ===== IMPORTS & DEPENDENCIES =====
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, Application, ContextTypes
from telegram import Update
from telegram.ext import ContextTypes, Application, TypeHandler
from storage.settings_manager import is_bot_active, get_maintenance_message
from config import config
# --- Local Imports ---
from .actions import (
    start,
    handle_guide_button,
    show_my_id,
    handle_user_linking,
    switch_to_customer_view,
    switch_to_admin_view
)
async def maintenance_mode_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id in config.AUTHORIZED_USER_IDS:
        return
        
    bot_is_active = await is_bot_active()
    if not bot_is_active:
        maintenance_message = await get_maintenance_message()
        if update.message:
            await update.message.reply_text(maintenance_message)
        # Stop further processing of the update
        context.application.drop_update(update)

# --- ROUTER FUNCTION for /start command ---
async def start_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Checks if the /start command has a payload (deep link) and routes
    the user to the appropriate function.
    """
    # context.args is a list of words after the command, e.g., ['link-user123']
    if context.args and context.args[0].startswith('link-'):
        await handle_user_linking(update, context)
    else:
        # If no payload, or an unknown one, just show the normal start menu
        await start(update, context)

# ===== API ROUTES & CONTROLLERS =====
def register(application: Application):
    """Registers handlers for the general (public/shared) module."""

    # --- Command Handlers (group 1, general priority) ---
    # The "start" command points to the router to handle deep links
    application.add_handler(TypeHandler(Update, maintenance_mode_filter), group=-1)
    application.add_handler(CommandHandler("start", start_router), group=1)
    application.add_handler(CommandHandler("help", handle_guide_button), group=1)
    application.add_handler(CommandHandler("myid", show_my_id), group=1)

    # --- Message Handlers for Main Menu Buttons (group 1) ---

    # Regex for the guide button (works for both admin and customer)
    guide_button_regex = '^(📱 دانلود و راهنمای اتصال|ℹ️ راهنما)$'
    application.add_handler(MessageHandler(filters.Regex(guide_button_regex), handle_guide_button), group=1)

    # --- Handlers for switching views for the admin ---
    # These are also group 1 as they are initiated from a shared menu view.
    # The @admin_only decorator inside the function handles security.
    application.add_handler(
        MessageHandler(filters.Regex('^💻 ورود به پنل کاربری$'), switch_to_customer_view),
        group=1
    )
    application.add_handler(
        MessageHandler(filters.Regex('^↩️ بازگشت به پنل ادمین$'), switch_to_admin_view),
        group=1
    )