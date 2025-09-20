# FILE: modules/financials/actions/wallet_admin.py (FINAL CORRECTED AND REFACTORED VERSION)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, 
    CallbackQueryHandler, filters
)
from database.db_manager import load_bot_settings, save_bot_settings
from shared.translator import _
# (⭐ FIX 1 ⭐) Import the correct function to return to the parent menu
from .settings import show_financial_menu 

LOGGER = logging.getLogger(__name__)

# States for this specific conversation
EDITING_AMOUNTS = 0

async def show_wallet_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the main wallet settings menu to the admin."""
    # This function is now also the entry point for the parent conversation state
    query = update.callback_query
    # Check if we are coming from a query or being called directly
    if query:
        await query.answer()

    settings = await load_bot_settings()
    amounts = settings.get("wallet_predefined_amounts", [50000, 100000, 250000, 500000])
    
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
    
    # Use the correct message object to edit
    target_message = query.message if query else update.effective_message
    await target_message.edit_text(text=text, reply_markup=reply_markup)
    
    # Return a generic state for the parent conversation if needed, or just a known state
    return -1 # This indicates it's a menu, not a specific state in a sub-conversation

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
    """
    Saves the new amounts and returns to the previous menu cleanly.
    It now sends a new message instead of trying to edit a deleted one.
    """
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

    await save_bot_settings({"wallet_predefined_amounts": new_amounts})
    
    # (⭐ FIX ⭐) First, clean up the old messages.
    try:
        # Delete the user's reply ("خالی")
        await update.message.delete()
        # Delete the bot's prompt ("Please enter amounts...")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id - 1)
    except Exception:
        pass

    # (⭐ FIX ⭐) Now, send a NEW message with the updated wallet menu.
    # We call the function, but since it's designed to edit, we need a slight change in how we call it.
    # We will send a placeholder message and then edit it. This is a robust pattern.
    placeholder_message = await context.bot.send_message(chat_id=update.effective_chat.id, text="...")
    
    # Create a mock update that points to this new placeholder message
    class MockQuery:
        def __init__(self, message):
            self.message = message
        async def answer(self): pass
    
    mock_update = Update(update.update_id, callback_query=MockQuery(placeholder_message))

    # Now call the menu function with the mock update pointing to the new message
    await show_wallet_settings_menu(mock_update, context)
    
    return ConversationHandler.END

async def back_to_wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Callback for the 'cancel_edit_amounts' button. Ends the sub-conversation
    and shows the main wallet settings menu.
    """
    await show_wallet_settings_menu(update, context)
    return ConversationHandler.END

# --- Conversation Handler Definition ---
edit_amounts_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_for_new_amounts, pattern='^wallet_edit_amounts$')],
    states={
        EDITING_AMOUNTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_amounts)
        ]
    },
    # (⭐ FIX 3 ⭐) The cancel button is now handled by a dedicated fallback.
    fallbacks=[
        CallbackQueryHandler(back_to_wallet_menu, pattern='^cancel_edit_amounts$')
    ],
    # No need for map_to_parent if it's a standalone conversation
)