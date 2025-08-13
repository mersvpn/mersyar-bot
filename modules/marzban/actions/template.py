# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# ... (imports) ...
# --- Local Imports ---
from .constants import SET_TEMPLATE_USER_PROMPT
from .data_manager import load_template_config, save_template_config, normalize_username
# CORRECTED: Import keyboards from the new shared location
from shared.keyboards import get_settings_and_tools_keyboard
from .api import get_user_data

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== TEMPLATE USER CONFIGURATION CONVERSATION =====

async def set_template_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to set a template user."""
    template_config = await load_template_config()
    current_template = template_config.get("template_username", "هنوز تنظیم نشده")

    LOGGER.info(f"[Template] Entering template setup. Current: '{current_template}'")

    await update.message.reply_text(
        f"⚙️ **تنظیم کاربر الگو**\n\n"
        "این قابلیت تنظیمات `proxies` و `inbounds` یک کاربر موجود را به عنوان الگو برای ساخت کاربران جدید ذخیره می‌کند.\n\n"
        f"**الگوی فعلی:** `{current_template}`\n\n"
        "لطفاً **نام کاربری دقیق** کاربر الگو را ارسال کنید.\n\n"
        "(برای لغو /cancel را ارسال کنید)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN
    )
    return SET_TEMPLATE_USER_PROMPT

async def set_template_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetches the user, validates it, and saves its config as the template."""
    username_raw = update.message.text.strip()
    username = normalize_username(username_raw)

    await update.message.reply_text(f"در حال بررسی و دریافت اطلاعات کاربر `{username}` از پنل...")

    user_data = await get_user_data(username)

    if not user_data:
        await update.message.reply_text(f"❌ کاربر `{username}` در پنل یافت نشد. لطفاً نام کاربری را به درستی وارد کنید.")
        return SET_TEMPLATE_USER_PROMPT

    proxies = user_data.get("proxies")
    inbounds = user_data.get("inbounds")

    if not proxies or not inbounds:
        await update.message.reply_text(
            f"❌ **خطای اعتبارسنجی** ❌\n"
            f"کاربر `{username}` اطلاعات `proxies` یا `inbounds` معتبری ندارد و نمی‌تواند الگو باشد."
        )
        return SET_TEMPLATE_USER_PROMPT

    template_config = {
        "template_username": username,
        "proxies": proxies,
        "inbounds": inbounds
    }

    LOGGER.info(f"[Template] Saving new template config: {template_config}")
    await save_template_config(template_config)

    confirmation_message = (
        f"✅ **الگو با موفقیت تنظیم شد!**\n\n"
        f"▫️ **نام کاربری الگو:** `{username}`\n"
        f"▫️ **تعداد Inbounds کپی شده:** `{len(inbounds)}`\n"
        f"▫️ **تعداد Proxies کپی شده:** `{len(proxies)}`\n\n"
        "از این پس، کاربران جدید با این مشخصات ساخته خواهند شد."
    )

    await update.message.reply_text(
        confirmation_message,
        reply_markup=get_settings_and_tools_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END