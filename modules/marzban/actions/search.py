# FILE: modules/marzban/actions/search.py (REVISED FOR I18N)
import logging
import math
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from .constants import SEARCH_PROMPT, USERS_PER_PAGE
from .api import get_all_users
from .display import build_users_keyboard
from shared.keyboards import get_user_management_keyboard
from .data_manager import normalize_username

LOGGER = logging.getLogger(__name__)

async def prompt_for_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    await update.message.reply_text(
        _("marzban_search.prompt"),
        reply_markup=ReplyKeyboardRemove()
    )
    return SEARCH_PROMPT

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    search_query = normalize_username(update.message.text)
    context.user_data.pop('last_search_results', None)
    
    await update.message.reply_text(_("marzban_search.searching_for", query=f"«{search_query}»"))

    all_users = await get_all_users()
    if all_users is None:
        await update.message.reply_text(_("marzban_display.panel_connection_error"), reply_markup=get_user_management_keyboard())
        return ConversationHandler.END
    if not all_users:
        await update.message.reply_text(_("marzban_display.no_users_in_panel"), reply_markup=get_user_management_keyboard())
        return ConversationHandler.END

    found_users = sorted(
        [user for user in all_users if user.get('username') and search_query in normalize_username(user['username'])],
        key=lambda u: u['username'].lower()
    )

    if not found_users:
        await update.message.reply_text(
            _("marzban_search.no_users_found", query=f"«{search_query}»"),
            reply_markup=get_user_management_keyboard()
        )
        return ConversationHandler.END

    context.user_data['last_search_results'] = found_users
    
    total_pages = math.ceil(len(found_users) / USERS_PER_PAGE)
    page_users = found_users[:USERS_PER_PAGE]
    
    keyboard = build_users_keyboard(users=page_users, current_page=1, total_pages=total_pages, list_type='search')
    
    await update.message.reply_text(_("marzban_search.search_results_title", query=f"«{search_query}»"), reply_markup=keyboard)
    return ConversationHandler.END