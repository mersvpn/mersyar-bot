# FILE: modules/marzban/actions/search.py (نسخه اصلاح شده با ذخیره نتایج و صفحه‌بندی)
import logging
import math
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from .constants import SEARCH_PROMPT, USERS_PER_PAGE # وارد کردن ثابت صفحه‌بندی
from .api import get_all_users
from .display import build_users_keyboard
from shared.keyboards import get_user_management_keyboard
from .data_manager import normalize_username

LOGGER = logging.getLogger(__name__)

async def prompt_for_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the search query."""
    await update.message.reply_text(
        "لطفاً قسمتی از نام کاربری مورد نظر را برای جستجو وارد کنید:\n(برای لغو /cancel)",
        reply_markup=ReplyKeyboardRemove()
    )
    return SEARCH_PROMPT

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Searches for users, paginates the results, and stores them in context."""
    search_query = normalize_username(update.message.text)
    # پاک کردن نتایج جستجوی قبلی
    context.user_data.pop('last_search_results', None)
    
    await update.message.reply_text(f"در حال جستجو برای «{search_query}»...")

    all_users = await get_all_users()
    if all_users is None:
        await update.message.reply_text("❌ خطا در ارتباط با پنل.", reply_markup=get_user_management_keyboard())
        return ConversationHandler.END
    if not all_users:
        await update.message.reply_text("هیچ کاربری در پنل یافت نشد.", reply_markup=get_user_management_keyboard())
        return ConversationHandler.END

    found_users = sorted(
        [
            user for user in all_users
            if user.get('username') and search_query in normalize_username(user['username'])
        ],
        key=lambda u: u['username'].lower()
    )

    if not found_users:
        await update.message.reply_text(
            f"هیچ کاربری با نام مشابه «{search_query}» یافت نشد.",
            reply_markup=get_user_management_keyboard()
        )
        return ConversationHandler.END

    # --- ذخیره کردن نتایج کامل جستجو در context ---
    context.user_data['last_search_results'] = found_users
    
    # --- منطق جدید برای صفحه‌بندی نتایج جستجو ---
    total_users = len(found_users)
    total_pages = math.ceil(total_users / USERS_PER_PAGE)
    current_page = 1
    
    # نمایش فقط کاربران صفحه اول
    page_users = found_users[:USERS_PER_PAGE]
    
    keyboard = build_users_keyboard(
        users=page_users,
        current_page=current_page,
        total_pages=total_pages,
        list_type='search' # مهم: نوع لیست را 'search' تعیین می‌کنیم
    )
    
    await update.message.reply_text(f"🔎 نتایج جستجو برای «{search_query}»:", reply_markup=keyboard)

    return ConversationHandler.END