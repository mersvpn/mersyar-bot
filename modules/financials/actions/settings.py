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

from modules.marzban.actions.data_manager import load_financials, save_financials
from .helpers import format_financial_info_message, build_financial_menu_keyboard
from modules.general.actions import start as back_to_main_menu
from modules.auth import admin_only_conv

LOGGER = logging.getLogger(__name__)

(
    MENU,
    EDITING_HOLDER,
    EDITING_CARD,
    EDITING_TEXT
) = range(4)

async def start_financial_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = await format_financial_info_message()
    keyboard = build_financial_menu_keyboard()
    
    target_message = update.message or update.callback_query.message
    context.user_data['financial_menu_message'] = target_message

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await target_message.reply_text(
            text=message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    return MENU

async def prompt_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action = query.data.split('_')[-1]
    context.user_data['financial_action'] = action
    
    prompt_map = {
        'holder': ("لطفاً نام جدید صاحب حساب را وارد کنید:", EDITING_HOLDER),
        'card': ("لطفاً شماره کارت ۱۶ رقمی را وارد کنید (فقط اعداد):", EDITING_CARD),
        'text': ("لطفاً متن دلخواه جدید (راهنمای پرداخت) را وارد کنید:", EDITING_TEXT),
    }

    if action not in prompt_map:
        return MENU
        
    prompt_text, next_state = prompt_map[action]
    await query.edit_message_text(text=prompt_text)
    return next_state

async def save_financial_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    action = context.user_data.get('financial_action')
    new_value = update.message.text.strip()
    
    if not action:
        await update.message.reply_text("خطا: عملیات نامشخص است.")
        return await main_menu_fallback(update, context)

    financial_data = await load_financials()
    confirmation_text = ""

    # --- FIX: Changed 'account_holder' to 'card_holder' to match database ---
    if action == 'holder':
        financial_data['card_holder'] = new_value
        confirmation_text = "✅ نام صاحب حساب با موفقیت به‌روز شد."
    # --------------------------------------------------------------------
    elif action == 'card':
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

    context.user_data.pop('financial_action', None)
    
    original_message = context.user_data.pop('financial_menu_message', update.message)
    class FakeUpdate:
        def __init__(self, message):
            self.message = message
    
    await start_financial_settings(FakeUpdate(original_message), context)
    return ConversationHandler.END # End the conversation after saving

async def main_menu_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await back_to_main_menu(update, context)
    return ConversationHandler.END

financial_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), admin_only_conv(start_financial_settings))],
    states={
        MENU: [
            CallbackQueryHandler(prompt_for_edit, pattern=r'^fin_edit_'),
            CallbackQueryHandler(main_menu_fallback, pattern=r'^back_to_main_menu$'),
        ],
        EDITING_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
        EDITING_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
        EDITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
    },
    fallbacks=[CommandHandler('start', main_menu_fallback)],
    conversation_timeout=300,
    per_message=False
)