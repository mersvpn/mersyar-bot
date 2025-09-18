# FILE: modules/customer/actions/wallet.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database import db_manager
from shared.translator import _
from modules.general.actions import send_main_menu

LOGGER = logging.getLogger(__name__)

CALLBACK_CHARGE_WALLET = "wallet_charge_start"
CALLBACK_WALLET_HISTORY = "coming_soon"
CALLBACK_WALLET_CLOSE = "wallet_close"

# This is now the official state value for the main panel display
DISPLAY_PANEL = 0

async def show_wallet_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text, reply_markup = await _get_wallet_panel_content(user_id=update.effective_user.id)
    
    sent_message = await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['wallet_panel_message'] = sent_message
    
    return DISPLAY_PANEL

async def show_wallet_panel_as_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, reply_markup = await _get_wallet_panel_content(user_id=query.from_user.id)
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def _get_wallet_panel_content(user_id: int):
    balance = await db_manager.get_user_wallet_balance(user_id)
    balance = balance if balance is not None else 0.00
    formatted_balance = f"{int(balance):,}"

    text = f"*{_('wallet.panel_title')}*\n\n"
    text += _("wallet.current_balance", balance=formatted_balance) + "\n"
    text += _("wallet.panel_description")

    keyboard = [
        [InlineKeyboardButton(_("wallet.button_charge"), callback_data=CALLBACK_CHARGE_WALLET)],
        [InlineKeyboardButton(_("wallet.button_history"), callback_data=CALLBACK_WALLET_HISTORY)],
        [InlineKeyboardButton(_("wallet.button_close"), callback_data=CALLBACK_WALLET_CLOSE)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return text, reply_markup

async def close_wallet_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    
    await send_main_menu(update, context)
    context.user_data.pop('wallet_panel_message', None)
    return ConversationHandler.END