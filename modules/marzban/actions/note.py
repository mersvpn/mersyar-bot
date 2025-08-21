# modules/marzban/actions/note.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# --- Local Imports ---
from .constants import NOTE_PROMPT
# Updated to use the new database functions
from .data_manager import load_reminders, save_reminders, normalize_username
from shared.keyboards import get_user_management_keyboard
from modules.auth import admin_only

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== NOTE MANAGEMENT CONVERSATION =====

async def prompt_for_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for a new note for a user, or to delete the existing one."""
    query = update.callback_query
    await query.answer()

    username_raw = query.data.split('_', 1)[1] # note_{username}
    username = normalize_username(username_raw)
    context.user_data['note_username'] = username

    reminders = await load_reminders()
    current_note = reminders.get(username, "")

    username_escaped = escape_markdown(username, version=2)
    message = (
        f"✍️ *مدیریت یادداشت برای کاربر:* `{username_escaped}`\n\n"
        "لطفاً متن یادداشت جدید را ارسال کنید\\.\n"
        "برای حذف یادداشت فعلی، کلمه `حذف` را ارسال کنید\\."
    )
    if current_note:
        current_note_escaped = escape_markdown(current_note, version=2)
        message += f"\n\n🗒️ *یادداشت فعلی:*\n_{current_note_escaped}_"

    await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN_V2)
    return NOTE_PROMPT

async def save_user_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = context.user_data.get('note_username')
    if not username:
        await update.message.reply_text("خطا: نام کاربری یافت نشد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

    note_text = update.message.text
    reminders = await load_reminders()
    
    confirmation_message = ""

    if note_text.strip().lower() in ['حذف', 'delete', 'del']:
        if username in reminders:
            del reminders[username]
            await save_reminders(reminders)
            confirmation_message = f"✅ یادداشت برای کاربر `{username}` با موفقیت حذف شد."
        else:
            confirmation_message = f"ℹ️ کاربر `{username}` یادداشتی نداشت."
    else:
        reminders[username] = note_text
        await save_reminders(reminders)
        confirmation_message = f"✅ یادداشت برای کاربر `{username}` با موفقیت ذخیره شد."
    
    await update.message.reply_text(
        confirmation_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_user_management_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== OTHER NOTE-RELATED ACTIONS =====

@admin_only
async def list_active_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all users with an active manual reminder/note."""
    await update.message.reply_text("در حال دریافت لیست پیگیری‌های فعال...")

    reminders = await load_reminders()
    if not reminders:
        await update.message.reply_text("هیچ پیگیری فعالی ثبت نشده است. ✅")
        return

    message = "📝 **لیست پیگیری‌های فعال شما:**\n\n"
    keyboard_rows = []
    bot_username = context.bot.username

    for username, note in sorted(reminders.items()):
        escaped_note = escape_markdown(note).replace("\n", " ")
        details_link = f"https://t.me/{bot_username}?start=details_{username}"
        message += f"▪️ <a href='{details_link}'><b>{username}</b></a>\n"
        message += f"   └─ 🗒️ <i>{escaped_note}</i>\n\n"
        keyboard_rows.append([InlineKeyboardButton(f"✅ اتمام پیگیری برای: {username}", callback_data=f"del_note_{username}")])

    keyboard_rows.append([InlineKeyboardButton("✖️ بستن", callback_data="close_pagination")])

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def delete_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the callback button to delete a note from the active reminders list."""
    query = update.callback_query
    await query.answer()

    username_to_delete = query.data.split('_', 2)[2] # del_note_{username}
    normalized_user = normalize_username(username_to_delete)

    reminders = await load_reminders()
    if normalized_user in reminders:
        del reminders[normalized_user]
        await save_reminders(reminders)
        await query.edit_message_text(f"✅ پیگیری برای کاربر `{normalized_user}` با موفقیت بسته شد.", parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(f"✖️ یادداشتی برای کاربر `{normalized_user}` یافت نشد.", parse_mode=ParseMode.MARKDOWN)