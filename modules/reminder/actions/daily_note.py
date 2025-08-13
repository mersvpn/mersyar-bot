# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    filters, CommandHandler
)
from telegram.constants import ParseMode

# --- Local Imports ---
from modules.marzban.actions.data_manager import load_settings, save_settings
from shared.callbacks import cancel_conversation
from shared.keyboards import get_settings_and_tools_keyboard
from modules.auth import admin_only_conv

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- CONSTANTS ---
GET_NOTE = 0
DAILY_NOTE_KEY = "daily_admin_note" # Key to store the note in settings.json

# ===== DAILY NOTE CONVERSATION =====

@admin_only_conv
async def start_daily_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to edit the daily note."""
    settings = await load_settings()
    current_note = settings.get(DAILY_NOTE_KEY, "")

    message = (
        "🗒️ **مدیریت یادداشت روزانه**\n\n"
        "این یادداشت در ابتدای گزارش یادآور خودکار روزانه نمایش داده خواهد شد.\n\n"
        "لطفاً متن جدید را وارد کنید. برای حذف یادداشت فعلی، کلمه `حذف` را ارسال نمایید."
    )

    if current_note:
        message += f"\n\n**یادداشت فعلی:**\n`{current_note}`"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    return GET_NOTE

async def save_daily_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves or deletes the daily note and ends the conversation cleanly."""
    note_text = update.message.text.strip()
    settings = await load_settings()
    confirmation_message = ""

    if note_text.lower() in ['حذف', 'delete', 'del']:
        if DAILY_NOTE_KEY in settings:
            del settings[DAILY_NOTE_KEY]
            await save_settings(settings)
            confirmation_message = "✅ یادداشت روزانه با موفقیت حذف شد."
        else:
            confirmation_message = "ℹ️ یادداشت روزانه‌ای برای حذف وجود نداشت."
    else:
        settings[DAILY_NOTE_KEY] = note_text
        await save_settings(settings)
        confirmation_message = "✅ یادداشت روزانه با موفقیت ذخیره/به‌روزرسانی شد."

    await update.message.reply_text(confirmation_message)

    await update.message.reply_text(
        "به منوی «تنظیمات و ابزارها» بازگشتید.",
        reply_markup=get_settings_and_tools_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Build the Conversation Handler ---
daily_note_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^🗒️ یادداشت روز$'), start_daily_note)],
    states={
        GET_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_daily_note)]
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=600
)