# FILE: modules/customer/actions/renewal.py (FIXED WITH LAZY IMPORT)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import config
# --- START OF FIX: The global import from db_manager is removed to prevent circular dependency ---
# from database.db_manager import add_to_non_renewal_list
from modules.marzban.actions.data_manager import normalize_username
# --- END OF FIX ---

LOGGER = logging.getLogger(__name__)

# ==================== REPLACE THIS FUNCTION in modules/customer/actions/renewal.py ====================
async def handle_renewal_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # وارد کردن تابع escape_markdown
    from telegram.helpers import escape_markdown

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    marzban_username = query.data.split('_')[-1]
    normalized_user = normalize_username(marzban_username)

    if config.AUTHORIZED_USER_IDS:
        # --- بخش اصلاح شده برای جلوگیری از خطای ParseMode ---
        # Escape کردن نام و نام کاربری برای جلوگیری از خطا
        safe_full_name = escape_markdown(user.full_name, version=2)
        user_info = f"کاربر {safe_full_name}"
        if user.username:
            safe_username = escape_markdown(user.username, version=2)
            user_info += f" \(@{safe_username}\)"
        user_info += f"\nUser ID: `{user.id}`"

        message_to_admin = (
            f"🔔 *درخواست تمدید اشتراک* 🔔\n\n"
            f"{user_info}\n"
            f"نام کاربری در پنل: `{normalized_user}`\n\n"
            "این کاربر قصد تمدید اشتراک خود را دارد\."
        )

        # --- دکمه‌های جدید برای ادمین ---
        # ساخت لینک مستقیم برای مشاهده جزئیات کاربر
        bot_username = context.bot.username
        details_url = f"https://t.me/{bot_username}?start=details_{normalized_user}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔄 تمدید هوشمند برای {normalized_user}", callback_data=f"renew_{normalized_user}")],
            [InlineKeyboardButton("👤 مشاهده جزئیات کاربر", url=details_url)]
        ])

        num_sent = 0
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=message_to_admin,
                    reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2
                )
                num_sent += 1
            except Exception as e:
                LOGGER.error(f"Failed to send renewal notification to admin {admin_id} for user {normalized_user}: {e}")
        
        if num_sent > 0:
            confirmation_text = "✅ درخواست تمدید شما با موفقیت برای پشتیبانی ارسال شد."
        else:
            # این پیام حالا فقط زمانی نمایش داده می‌شود که ربات نتواند به هیچ ادمینی پیام دهد
            confirmation_text = "❌ مشکلی در ارسال درخواست به پشتیبانی رخ داد. لطفاً بعداً دوباره تلاش کنید."
            
        await query.edit_message_text(text=confirmation_text, reply_markup=None)
        
    # این خط مکالمه را به درستی پایان می‌دهد
    return ConversationHandler.END
# =======================================================================================================

async def handle_do_not_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles 'Do Not Renew' button click, adding the user to the non-renewal table in the database.
    """
    # --- START OF FIX: Import is moved inside the function that needs it ---
    from database.db_manager import add_to_non_renewal_list
    # --- END OF FIX ---

    query = update.callback_query
    await query.answer()

    marzban_username = query.data.split('_')[-1]
    normalized_user = normalize_username(marzban_username)
    user = update.effective_user

    LOGGER.info(f"User {user.id} ({normalized_user}) opted out of renewal reminders.")

    # Use the database function
    await add_to_non_renewal_list(normalized_user)

    await query.edit_message_text(
        "✅ درخواست شما ثبت شد.\n\n"
        "دیگر پیام یادآور تمدید برای این اشتراک دریافت نخواهید کرد."
    )

    # Notify admins about this action
    if config.AUTHORIZED_USER_IDS:
        user_info = f"کاربر {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"

        message_to_admin = (
            f"ℹ️ **اطلاع‌رسانی عدم تمدید** ℹ️\n\n"
            f"{user_info}\n"
            f"نام کاربری در پنل: `{normalized_user}`\n\n"
            "این کاربر اعلام کرد که **تمایلی به تمدید ندارد**."
        )

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=message_to_admin, parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send 'do not renew' notification to admin {admin_id}: {e}")