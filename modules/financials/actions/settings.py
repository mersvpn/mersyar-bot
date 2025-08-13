# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters
)
from telegram.constants import ParseMode

# --- Local Imports ---
from modules.marzban.actions.data_manager import load_financials, save_financials
from .helpers import format_financial_info_message, build_financial_menu_keyboard
from modules.general.actions import start as back_to_main_menu
from modules.auth import admin_only_conv

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- CONSTANTS: Conversation States ---
(
    MENU,
    EDITING_HOLDER,
    EDITING_CARD,
    EDITING_TEXT
) = range(4)

# ===== CONVERSATION HANDLER FUNCTIONS =====

async def start_financial_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the financial settings conversation. Displays the menu."""
    message_text = await format_financial_info_message()
    keyboard = build_financial_menu_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    return MENU

async def prompt_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the new value for the selected field."""
    query = update.callback_query
    await query.answer()

    action = query.data.split('_')[-1] # fin_edit_{action}
    context.user_data['financial_action'] = action

    prompt_text = ""
    next_state = -1
    if action == 'holder':
        prompt_text = "لطفاً نام جدید صاحب حساب را وارد کنید:"
        next_state = EDITING_HOLDER
    elif action == 'card':
        prompt_text = "لطفاً شماره کارت ۱۶ رقمی را وارد کنید (فقط اعداد):"
        next_state = EDITING_CARD
    elif action == 'text':
        prompt_text = "لطفاً متن دلخواه جدید (راهنمای پرداخت) را وارد کنید:"
        next_state = EDITING_TEXT
    else:
        # Invalid action, return to menu
        return MENU

    await query.edit_message_text(text=prompt_text)
    return next_state

async def save_financial_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new information and returns to the main financial menu."""
    action = context.user_data.get('financial_action')
    new_value = update.message.text.strip()

    if not action:
        await update.message.reply_text("خطا: عملیات نامشخص است. لطفاً دوباره تلاش کنید.")
        return await start_financial_settings(update, context)

    financial_data = await load_financials()
    confirmation_text = ""

    if action == 'holder':
        financial_data['account_holder'] = new_value
        confirmation_text = "✅ نام صاحب حساب با موفقیت به‌روز شد."
    elif action == 'card':
        # Remove any non-digit characters
        card_number = "".join(filter(str.isdigit, new_value))
        if len(card_number) != 16:
            await update.message.reply_text("❌ شماره کارت نامعتبر است. باید ۱۶ رقم باشد. لطفاً دوباره وارد کنید.")
            return EDITING_CARD
        financial_data['card_number'] = card_number
        confirmation_text = "✅ شماره کارت با موفقیت به‌روز شد."
    elif action == 'text':
        financial_data['extra_text'] = new_value
        confirmation_text = "✅ متن دلخواه با موفقیت به‌روز شد."

    await save_financials(financial_data)
    await update.message.reply_text(confirmation_text)

    # Clean up and show the updated menu
    context.user_data.pop('financial_action', None)
    return await start_financial_settings(update, context)


# --- EXPORTED CONVERSATION HANDLER ---
financial_conv = ConversationHandler(
    # Secure the entry point with the admin decorator
    entry_points=[MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), admin_only_conv(start_financial_settings))],
    states={
        MENU: [
            CallbackQueryHandler(prompt_for_edit, pattern=r'^fin_edit_'),
            # The 'back to main menu' is handled by the general handler now
        ],
        EDITING_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
        EDITING_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
        EDITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
    },
    fallbacks=[
        CallbackQueryHandler(back_to_main_menu, pattern=r'^back_to_main_menu$'),
        CommandHandler('start', back_to_main_menu)
    ],
    conversation_timeout=300
)