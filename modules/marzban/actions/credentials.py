# FILE: modules/marzban/actions/credentials.py (REVISED FOR I18N)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters
from telegram.constants import ParseMode

from shared.translator import _
from .data_manager import load_marzban_credentials, save_marzban_credentials
from .api import get_marzban_token
from modules.general.actions import end_conversation_and_show_menu

LOGGER = logging.getLogger(__name__)
GET_URL, GET_USERNAME, GET_PASSWORD, CONFIRM = range(4)

async def start_set_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    creds = await load_marzban_credentials()
    not_set_str = _("marzban_credentials.not_set")
    
    current_info = _("marzban_credentials.current_settings_title")
    current_info += f"{_('marzban_credentials.url_label')} `{creds.get('base_url', not_set_str)}`\n"
    current_info += f"{_('marzban_credentials.username_label')} `{creds.get('username', not_set_str)}`\n"
    current_info += f"{_('marzban_credentials.password_label')} `{'*' * 8 if creds.get('password') else not_set_str}`\n\n---"
    
    await update.message.reply_text(
        f"{current_info}" + _("marzban_credentials.step1_ask_url"),
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_creds'] = {}
    return GET_URL

async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(_("marzban_credentials.invalid_url"))
        return GET_URL
    context.user_data['new_creds']['base_url'] = url.rstrip('/')
    await update.message.reply_text(_("marzban_credentials.url_saved"))
    return GET_USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_creds']['username'] = update.message.text.strip()
    await update.message.reply_text(_("marzban_credentials.username_saved"))
    return GET_PASSWORD

async def get_password_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_creds']['password'] = update.message.text.strip()
    creds = context.user_data['new_creds']
    
    summary = _("marzban_credentials.confirm_prompt")
    summary += f"{_('marzban_credentials.url_label')} `{creds['base_url']}`\n"
    summary += f"{_('marzban_credentials.username_label')} `{creds['username']}`\n"
    summary += f"{_('marzban_credentials.password_label')} `{'*' * len(creds['password'])}`"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("marzban_credentials.button_save_and_test"), callback_data="creds_save")],
        [InlineKeyboardButton(_("marzban_credentials.button_cancel"), callback_data="creds_cancel")]
    ])
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    return CONFIRM

async def save_and_test_creds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    new_creds = context.user_data.get('new_creds')
    if not new_creds:
        await query.edit_message_text(_("marzban_credentials.creds_not_found_error"))
        return await end_conversation_and_show_menu(update, context)
    
    await save_marzban_credentials(new_creds)
    await query.edit_message_text(_("marzban_credentials.creds_saved_testing"))
    
    token = await get_marzban_token()
    if token:
        await query.message.reply_text(_("marzban_credentials.connection_successful"), parse_mode=ParseMode.MARKDOWN)
    else:
        await query.message.reply_text(_("marzban_credentials.connection_failed"), parse_mode=ParseMode.MARKDOWN)
    
    context.user_data.clear()
    return ConversationHandler.END

credential_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(f'^{_("keyboards.settings_and_tools.marzban_panel_management")}$'), start_set_credentials)],
    states={
        GET_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_url)],
        GET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
        GET_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password_and_confirm)],
        CONFIRM: [
            CallbackQueryHandler(save_and_test_creds, pattern='^creds_save$'),
            CallbackQueryHandler(end_conversation_and_show_menu, pattern='^creds_cancel$'),
        ]
    },
    fallbacks=[CommandHandler('cancel', end_conversation_and_show_menu)],
    conversation_timeout=600
)