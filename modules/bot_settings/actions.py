from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from storage.settings_manager import is_bot_active, set_bot_status
from shared.keyboards import get_settings_and_tools_keyboard

MENU_STATE = 0

async def _build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_active = await is_bot_active()
    
    status_text = "روشن ✅" if is_active else "خاموش (حالت تعمیرات) 🔴"
    toggle_text = "خاموش کردن ربات" if is_active else "روشن کردن ربات"
    toggle_data = "bot_status_deactivate" if is_active else "bot_status_activate"

    keyboard = [
        [
            InlineKeyboardButton(status_text, callback_data="noop_status"),
            InlineKeyboardButton("وضعیت ربات 📡", callback_data="noop_title")
        ],
        [InlineKeyboardButton(toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton("🔙 بازگشت به ابزارها", callback_data="bot_status_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_text = "🔧 **تنظیمات ربات**\n\nدر این بخش می‌توانید وضعیت قابلیت‌های اصلی ربات را مدیریت کنید."

    target_message = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await target_message.reply_text(menu_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def start_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _build_menu(update, context)
    return MENU_STATE

async def toggle_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action = query.data
    if action == "bot_status_deactivate":
        await set_bot_status(False)
        await query.answer("ربات در حالت تعمیرات قرار گرفت.", show_alert=True)
    elif action == "bot_status_activate":
        await set_bot_status(True)
        await query.answer("ربات فعال و آنلاین شد.", show_alert=True)
        
    await _build_menu(update, context)
    return MENU_STATE

async def back_to_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.message.delete()
    await query.message.reply_text(
        "به بخش «تنظیمات و ابزارها» خوش آمدید.",
        reply_markup=get_settings_and_tools_keyboard()
    )
    return ConversationHandler.END