# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- Local Imports ---
from config import config
# CORRECTED: Import keyboards from the new shared location
from shared.keyboards import (
    get_customer_main_menu_keyboard,
    get_admin_main_menu_keyboard,
    get_customer_view_for_admin_keyboard
)
from modules.marzban.actions.data_manager import load_users_map, save_users_map, normalize_username
from modules.auth import admin_only

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== CORE BUSINESS LOGIC =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Greets the user and shows the appropriate main menu (admin or customer).
    Can be called directly or as a fallback from other handlers.
    """
    user = update.effective_user
    welcome_message = f"سلام {user.first_name} عزیز!\nبه ربات ما خوش آمدید."

    if user.id in config.AUTHORIZED_USER_IDS:
        reply_markup = get_admin_main_menu_keyboard()
        welcome_message += "\n\nداشبورد مدیریتی برای شما فعال است."
    else:
        reply_markup = get_customer_main_menu_keyboard()
        welcome_message += "\n\nبرای شروع، می‌توانید از دکمه‌های زیر استفاده کنید."

    if update.callback_query:
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass # Message might have been deleted already
        await context.bot.send_message(chat_id=user.id, text=welcome_message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def handle_guide_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the appropriate guide text for admins or customers."""
    user = update.effective_user
    if user.id in config.AUTHORIZED_USER_IDS:
        guide_text = (
            "** راهنمای ادمین **\n\n"
            "**👤 مدیریت کاربران**: دسترسی به داشبورد کامل برای مدیریت کاربران مرزبان.\n\n"
            "**⚙️ تنظیمات و ابزارها**: مدیریت یادآورها، کاربر الگو و ایجاد لینک اتصال.\n\n"
            "**💻 ورود به پنل کاربری**: شبیه‌سازی محیط ربات از دید یک مشتری عادی."
        )
    else:
        guide_text = (
            "**📱 راهنمای دانلود و اتصال**\n\n"
            "برای استفاده از سرویس، یکی از کلاینت‌های زیر را متناسب با سیستم عامل خود نصب کنید:\n\n"
            "1️⃣ **Android (V2RayNG)**: [Google Play](https://play.google.com/store/apps/details?id=com.v2ray.ang)\n"
            "2️⃣ **iOS (Streisand)**: [App Store](https://apps.apple.com/us/app/streisand/id6450534064)\n"
            "3️⃣ **Windows (V2RayN)**: [GitHub](https://github.com/2dust/v2rayN/releases)\n\n"
            "**نحوه اتصال:**\n"
            "پس از خرید، از بخش «📊 سرویس من» لینک اشتراک را کپی و در کلاینت خود وارد کنید."
        )
    await update.message.reply_text(
        guide_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the user their Telegram ID."""
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram User ID is:\n`{user_id}`", parse_mode=ParseMode.MARKDOWN)

# ===== VIEW SWITCHING LOGIC FOR ADMINS =====

@admin_only
async def switch_to_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switches the admin's keyboard to the customer panel."""
    await update.message.reply_text(
        "✅ شما اکنون در **نمای کاربری** هستید.",
        reply_markup=get_customer_view_for_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def switch_to_admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switches the admin's keyboard back to the admin panel."""
    await update.message.reply_text(
        "✅ شما به **پنل ادمین** بازگشتید.",
        reply_markup=get_admin_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# ===== USER LINKING LOGIC (DEEP LINK) =====

async def handle_user_linking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles deep links like t.me/bot?start=link-someuser"""
    user = update.effective_user
    try:
        marzban_username_raw = context.args[0].split('-', 1)[1]
        marzban_username = normalize_username(marzban_username_raw)
    except IndexError:
        await update.message.reply_text("لینک اتصال نامعتبر است.")
        await start(update, context) # Show default menu
        return

    users_map = await load_users_map()
    if marzban_username in users_map and users_map[marzban_username] != user.id:
        await update.message.reply_text(
            f"❌ **خطا** ❌\n\n"
            f"سرویس `{marzban_username}` قبلاً به یک حساب تلگرام دیگر متصل شده است.\n"
            "برای راهنمایی با پشتیبانی تماس بگیرید."
        )
        return

    users_map[marzban_username] = user.id
    await save_users_map(users_map)

    await update.message.reply_text(
        f"✅ حساب شما با موفقیت به سرویس `{marzban_username}` متصل شد!\n\n"
        "اکنون می‌توانید از دکمه «📊 سرویس من» برای مدیریت اشتراک خود استفاده کنید.",
        parse_mode=ParseMode.MARKDOWN
    )

    admin_message = (
        f"✅ **اتصال موفق** ✅\n\n"
        f"کاربر مرزبان `{marzban_username}` به پروفایل تلگرام زیر متصل شد:\n\n"
        f"👤 **کاربر:** {user.full_name}\n"
        f"🆔 **Telegram ID:** `{user.id}`"
    )
    if user.username:
        admin_message += f"\nUsername: @{user.username}"

    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            LOGGER.error(f"Failed to send linking notification to admin {admin_id}: {e}", exc_info=True)

    await start(update, context)