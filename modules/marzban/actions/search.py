# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

# --- Local Imports ---
from .constants import SEARCH_PROMPT
from .api import get_all_users
from .display import build_users_keyboard
from shared.keyboards import get_user_management_keyboard
from .data_manager import normalize_username

# --- Setup ---
LOGGER = logging.getLogger(__name__)

# ===== SEARCH CONVERSATION =====

async def prompt_for_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the search query."""
    await update.message.reply_text(
        "لطفاً قسمتی از نام کاربری مورد نظر را برای جستجو وارد کنید:\n(برای لغو /cancel)",
        reply_markup=ReplyKeyboardRemove()
    )
    return SEARCH_PROMPT

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Searches for users matching the query and displays the results."""
    search_query = normalize_username(update.message.text)
    await update.message.reply_text(f"در حال جستجو برای «{search_query}»...")

    all_users = await get_all_users()
    if all_users is None:
        await update.message.reply_text("❌ خطا در ارتباط با پنل.", reply_markup=get_user_management_keyboard())
        return ConversationHandler.END
    if not all_users:
        await update.message.reply_text("هیچ کاربری در پنل یافت نشد.", reply_markup=get_user_management_keyboard())
        return ConversationHandler.END

    found_users = [
        user for user in all_users
        if user.get('username') and search_query in normalize_username(user['username'])
    ]

    if not found_users:
        await update.message.reply_text(
            f"هیچ کاربری با نام مشابه «{search_query}» یافت نشد.",
            reply_markup=get_user_management_keyboard()
        )
        return ConversationHandler.END

    context.bot_data['user_list_search'] = found_users
    context.user_data['current_page'] = 1
    keyboard = build_users_keyboard(found_users, current_page=1, list_type='search')
    await update.message.reply_text(f"🔎 نتایج جستجو برای «{search_query}»:", reply_markup=keyboard)

    return ConversationHandler.END