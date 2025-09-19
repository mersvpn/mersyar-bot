# FILE: modules/financials/actions/wallet_admin.py (FINAL CORRECTED VERSION)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, 
    CallbackQueryHandler, filters
)
from database.db_manager import load_bot_settings, save_bot_settings
from shared.translator import _
from .settings import show_financial_menu

LOGGER = logging.getLogger(__name__)

MENU, EDITING_AMOUNTS = range(2)


async def show_wallet_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the main wallet settings menu to the admin with a 2-column layout."""
    query = update.callback_query
    await query.answer()

    settings = await load_bot_settings()
    amounts = settings.get("wallet_predefined_amounts", [50000, 100000, 250000, 500000])
    
    amounts_str = ", ".join([f"{a:,}" for a in amounts]) if amounts else _("financials_settings.not_set", default="تنظیم نشده")

    text = _("financials_settings.wallet_settings_title")
    text += _("financials_settings.wallet_settings_amounts_label", amounts=amounts_str)
    
    # --- NEW 2-COLUMN LAYOUT ---
    keyboard = [
        [
            InlineKeyboardButton(_("financials_settings.button_balance_management"), callback_data="admin_manage_balance"),
            InlineKeyboardButton(_("financials_settings.button_edit_amounts"), callback_data="wallet_edit_amounts")
        ],
        [InlineKeyboardButton(_("financials_settings.button_back_to_financial_menu"), callback_data="back_to_financial_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # --- END OF NEW LAYOUT ---

    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return MENU


async def prompt_for_new_amounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin to enter the new predefined amounts."""
    query = update.callback_query
    await query.answer()
    
    text = _("financials_settings.prompt_edit_amounts")
    
    # --- NEW: Add a cancel button ---
    keyboard = [
        [InlineKeyboardButton(_("financials_settings.button_cancel_edit"), callback_data="cancel_edit_amounts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # --- END OF NEW ---

    await query.edit_message_text(text=text, reply_markup=reply_markup) # Pass the new keyboard
    return EDITING_AMOUNTS

async def save_new_amounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_text = update.message.text.strip().lower()
    
    if raw_text in ['خالی', 'none', 'empty']:
        new_amounts = []
    else:
        try:
            new_amounts = sorted([int(x.strip()) for x in raw_text.split(',') if x.strip().isdigit()])
            if not new_amounts:
                raise ValueError("No valid numbers found")
        except ValueError:
            await update.message.reply_text(_("financials_settings.invalid_amounts_format"))
            return EDITING_AMOUNTS

    await save_bot_settings({"wallet_predefined_amounts": new_amounts})
    await update.message.reply_text(_("financials_settings.amounts_updated_success"))
    
    class MockQuery:
        async def answer(self): pass
        message = update.message

    mock_update = Update(update.update_id, callback_query=MockQuery())
    await show_financial_menu(mock_update, context)
    
    return ConversationHandler.END

# --- Conversation Handler Definition ---
edit_amounts_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_for_new_amounts, pattern='^wallet_edit_amounts$')],
    states={
        EDITING_AMOUNTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_amounts),
            # --- NEW: Handle the cancel button click ---
            CallbackQueryHandler(show_wallet_settings_menu, pattern='^cancel_edit_amounts$')
        ]
    },
    fallbacks=[CallbackQueryHandler(show_financial_menu, pattern='^back_to_financial_settings$')],
    map_to_parent={
        ConversationHandler.END: -1,
        # --- NEW: Map the state back to the menu ---
        MENU: MENU 
    }
)