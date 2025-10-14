# --- START OF FILE modules/financials/actions/wallet_admin.py (REVISED) ---

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, 
    CallbackQueryHandler, filters
)
# --- MODIFIED IMPORTS ---
from database.crud import bot_setting as crud_bot_setting
# --- ------------------ ---
from shared.translator import _
from .settings import show_financial_menu 

LOGGER = logging.getLogger(__name__)

EDITING_AMOUNTS = 0

async def show_wallet_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the main wallet settings menu to the admin."""
    query = update.callback_query
    if query:
        await query.answer()

    settings = await crud_bot_setting.load_bot_settings()
    
    amounts_db = settings.get('wallet_predefined_amounts') if settings else None
    amounts = amounts_db if amounts_db is not None else [50000, 100000, 250000, 500000]
    
    amounts_str = ", ".join([f"{a:,}" for a in amounts]) if amounts else _("financials_settings.not_set", default="تنظیم نشده")

    text = _("financials_settings.wallet_settings_title")
    text += _("financials_settings.wallet_settings_amounts_label", amounts=amounts_str)
    
    keyboard = [
        [
            InlineKeyboardButton(_("financials_settings.button_balance_management"), callback_data="admin_manage_balance"),
            InlineKeyboardButton(_("financials_settings.button_edit_amounts"), callback_data="wallet_edit_amounts")
        ],
        [InlineKeyboardButton(_("financials_settings.button_back_to_financial_menu"), callback_data="back_to_financial_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    target_message = query.message if query else update.effective_message
    if query:
        await target_message.edit_text(text=text, reply_markup=reply_markup)
    else: # If called directly, send a new message
        await target_message.reply_text(text=text, reply_markup=reply_markup)
    
    return -1

async def prompt_for_new_amounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin to enter the new predefined amounts."""
    query = update.callback_query
    await query.answer()
    
    text = _("financials_settings.prompt_edit_amounts")
    
    keyboard = [
        [InlineKeyboardButton(_("financials_settings.button_cancel_edit"), callback_data="cancel_edit_amounts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return EDITING_AMOUNTS

async def save_new_amounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new amounts and returns to the previous menu cleanly."""
    raw_text = update.message.text.strip().lower()
    
    if raw_text in ['خالی', 'none', 'empty', 'null']:
        new_amounts = []
    else:
        try:
            separators = [',', ' ', '\n']
            for sep in separators:
                raw_text = raw_text.replace(sep, ',')
            new_amounts = sorted([int(x.strip()) for x in raw_text.split(',') if x.strip().isdigit()])
            if not new_amounts and raw_text:
                raise ValueError("No valid numbers found")
        except ValueError:
            await update.message.reply_text(_("financials_settings.invalid_amounts_format"))
            return EDITING_AMOUNTS

    await crud_bot_setting.save_bot_settings({'wallet_predefined_amounts': new_amounts})
    
    try:
        await update.message.delete()
        if 'prompt_message_id' in context.user_data:
             await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data.pop('prompt_message_id'))
    except Exception:
        pass

    placeholder_message = await context.bot.send_message(chat_id=update.effective_chat.id, text="...")
    
    class MockQuery:
        def __init__(self, message):
            self.message = message
        async def answer(self): pass
    
    mock_update = Update(update.update_id, callback_query=MockQuery(placeholder_message))
    await show_wallet_settings_menu(mock_update, context)
    
    return ConversationHandler.END

async def back_to_wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback for the 'cancel_edit_amounts' button."""
    await show_wallet_settings_menu(update, context)
    return ConversationHandler.END

edit_amounts_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_for_new_amounts, pattern='^wallet_edit_amounts$')],
    states={
        EDITING_AMOUNTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_amounts)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(back_to_wallet_menu, pattern='^cancel_edit_amounts$')
    ],
)

# --- END OF FILE modules/financials/actions/wallet_admin.py (REVISED) ---