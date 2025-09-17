# FILE: modules/bot_settings/actions.py (REVISED FOR I18N and BEST PRACTICES)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, error
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from shared.keyboards import get_settings_and_tools_keyboard, get_helper_tools_keyboard
from .data_manager import is_bot_active, set_bot_status

LOGGER = logging.getLogger(__name__)

MENU_STATE = 0
SET_CHANNEL_ID = 1

async def show_helper_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    await update.message.reply_text(_("bot_settings.helper_tools_menu_title"), reply_markup=get_helper_tools_keyboard())

async def back_to_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    await update.message.reply_text(_("bot_settings.back_to_settings_menu"), reply_markup=get_settings_and_tools_keyboard())

async def prompt_for_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    from database.db_manager import load_bot_settings
    
    bot_settings = await load_bot_settings()
    current_channel_id = bot_settings.get('log_channel_id', _("marzban_credentials.not_set"))
    
    text = _("bot_settings.current_log_channel_id", id=f"`{current_channel_id}`")
    text += _("bot_settings.prompt_for_channel_id")
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return SET_CHANNEL_ID

async def process_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    from database.db_manager import save_bot_settings
    
    channel_id = update.message.text.strip()
    if not (channel_id.startswith('@') or channel_id.startswith('-100')):
        await update.message.reply_text(_("bot_settings.invalid_channel_id"))
        return SET_CHANNEL_ID
        
    await save_bot_settings({'log_channel_id': channel_id})
    await update.message.reply_text(
        _("bot_settings.channel_id_updated", id=f"`{channel_id}`"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_settings_and_tools_keyboard()
    )
    return ConversationHandler.END

async def _build_and_send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from shared.translator import _
    from database.db_manager import load_bot_settings
    
    query = update.callback_query
    
    bot_settings = await load_bot_settings()
    is_active_status = await is_bot_active()
    
    maintenance_btn_text = _("bot_settings.status_on") if is_active_status else _("bot_settings.status_off_maintenance")
    maintenance_callback = "toggle_maintenance_disable" if is_active_status else "toggle_maintenance_enable"

    log_channel_is_enabled = bot_settings.get('is_log_channel_enabled', False)
    log_channel_btn_text = _("bot_settings.status_active") if log_channel_is_enabled else _("bot_settings.status_inactive")
    log_channel_callback = "toggle_log_channel_disable" if log_channel_is_enabled else "toggle_log_channel_enable"
    
    keyboard = [
        [
            InlineKeyboardButton(maintenance_btn_text, callback_data=maintenance_callback),
            InlineKeyboardButton(_("bot_settings.label_bot_status"), callback_data="noop")
        ],
        [
            InlineKeyboardButton(log_channel_btn_text, callback_data=log_channel_callback),
            InlineKeyboardButton(_("bot_settings.label_log_channel"), callback_data="noop")
        ],
        [InlineKeyboardButton(_("bot_settings.button_back_to_tools"), callback_data="bot_status_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_text = _("bot_settings.menu_title")

    target_message = query.message if query else update.message
    if query:
        await query.answer()
        try:
            await query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except error.BadRequest as e:
            if "Message is not modified" not in str(e): LOGGER.error(f"Error editing bot settings menu: {e}")
    else:
        if update.message: await update.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

async def start_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _build_and_send_menu(update, context)
    return MENU_STATE

async def toggle_maintenance_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    new_status_is_active = (query.data == "toggle_maintenance_enable")
    await set_bot_status(new_status_is_active)
    
    feedback = _("bot_settings.feedback_bot_enabled") if new_status_is_active else _("bot_settings.feedback_bot_disabled")
    await query.answer(feedback, show_alert=True)
    await _build_and_send_menu(update, context)
    return MENU_STATE

async def toggle_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    from database.db_manager import save_bot_settings
    
    query = update.callback_query
    new_status = (query.data == "toggle_log_channel_enable")
    await save_bot_settings({"is_log_channel_enabled": new_status})
    
    feedback = _("bot_settings.feedback_log_channel_enabled") if new_status else _("bot_settings.feedback_log_channel_disabled")
    await query.answer(feedback, show_alert=True)
    await _build_and_send_menu(update, context)
    return MENU_STATE

async def back_to_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    
    chat_id = update.effective_chat.id
    if query:
        await query.answer()
        try: await query.message.delete()
        except Exception: pass
    elif update.message:
        try: await update.message.delete()
        except Exception: pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=_("bot_settings.back_to_settings_menu"),
        reply_markup=get_settings_and_tools_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END