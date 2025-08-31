# FILE: modules/general/handler.py (نسخه نهایی و پاک‌سازی شده)

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    ApplicationHandlerStop,
    filters
)
from modules.bot_settings.data_manager import is_bot_active
from config import config

from .actions import (
    start, show_my_id, handle_user_linking, 
    switch_to_customer_view, switch_to_admin_view
)
# --- وارد کردن منطق جدید ---
from modules.customer.actions.guide import show_guides_to_customer

MAINTENANCE_MESSAGE = (
    "**🛠 ربات در حال تعمیر و به‌روزرسانی است**\n\n"
    "در حال حاضر امکان پاسخگویی وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید.\n\n"
    "از شکیبایی شما سپاسگزاریم."
)

async def maintenance_gatekeeper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user and user.id in config.AUTHORIZED_USER_IDS:
        return
    if not await is_bot_active():
        if update.message:
            await update.message.reply_text(MAINTENANCE_MESSAGE, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.answer("ربات در حال تعمیر است.", show_alert=True)
        raise ApplicationHandlerStop

async def start_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.marzban.actions.display import handle_deep_link_details
    if context.args:
        if context.args[0].startswith('link-'):
            await handle_user_linking(update, context)
        elif context.args[0].startswith('details_'):
            await handle_deep_link_details(update, context)
        else:
            await start(update, context)
    else:
        await start(update, context)

def register(application: Application):
    application.add_handler(TypeHandler(Update, maintenance_gatekeeper), group=-1)

    application.add_handler(CommandHandler("start", start_router), group=1)
    application.add_handler(CommandHandler("myid", show_my_id), group=1)

    # --- هندلرهای اصلاح شده ---
    # هندلر "تنظیمات آموزش" حذف شد چون به ماژول guides منتقل شده است
    application.add_handler(MessageHandler(filters.Regex('^📱 دانلود و راهنمای اتصال$'), show_guides_to_customer), group=1)
    application.add_handler(MessageHandler(filters.Regex('^💻 ورود به پنل کاربری$'), switch_to_customer_view), group=1)
    application.add_handler(MessageHandler(filters.Regex('^↩️ بازگشت به پنل ادمین$'), switch_to_admin_view), group=1)