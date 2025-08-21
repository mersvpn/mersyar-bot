# ===== IMPORTS & DEPENDENCIES =====
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# --- Local Imports ---
from .api import get_user_data
# CORRECTED: Import keyboards from the new shared location
from shared.keyboards import get_user_management_keyboard
from .data_manager import normalize_username

# --- Define conversation states ---
PROMPT_USERNAME_FOR_LINK = 0

# ===== LINKING CONVERSATION FUNCTIONS =====

async def start_linking_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the admin to start creating a linking URL."""
    await update.message.reply_text(
        "🔗 **ایجاد لینک اتصال برای کاربر**\n\n"
        "لطفاً `username` دقیق کاربری که در پنل مرزبان وجود دارد را وارد کنید تا یک لینک اتصال برای او ساخته شود.\n\n"
        "(برای لغو /cancel)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN
    )
    return PROMPT_USERNAME_FOR_LINK

async def generate_linking_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks if the username exists in Marzban and generates the deep link."""
    marzban_username_raw = update.message.text.strip()
    marzban_username = normalize_username(marzban_username_raw)

    await update.message.reply_text(f"در حال بررسی کاربر «{marzban_username}» در پنل مرزبان...")
    user_data = await get_user_data(marzban_username)
    if not user_data:
        await update.message.reply_text(
            f"❌ کاربری با نام `{marzban_username}` در پنل یافت نشد.\n\n"
            "لطفاً نام کاربری را به درستی وارد کنید یا برای لغو /cancel را بزنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return PROMPT_USERNAME_FOR_LINK

    bot_username = context.bot.username
    # The username in the link does not need to be normalized, but the one we check does.
    linking_url = f"https://t.me/{bot_username}?start=link-{marzban_username_raw}"

    message = (
        f"✅ **لینک اتصال با موفقیت ساخته شد!**\n\n"
        f"🔗 **کاربر:** `{marzban_username}`\n\n"
        "👇 لطفاً لینک زیر را برای مشتری ارسال کنید. به محض کلیک، حسابش متصل خواهد شد.\n\n"
        f"`{linking_url}`"
    )

    await update.message.reply_text(
        message,
        reply_markup=get_user_management_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

    return ConversationHandler.END