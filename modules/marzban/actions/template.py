# FILE: modules/marzban/actions/template.py (REVISED FOR I18N)
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from .constants import SET_TEMPLATE_USER_PROMPT
from .data_manager import load_template_config, save_template_config, normalize_username
from shared.keyboards import get_settings_and_tools_keyboard
from .api import get_user_data

LOGGER = logging.getLogger(__name__)

async def set_template_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    template_config = await load_template_config()
    current_template = template_config.get("template_username", _("marzban_template.not_set"))
    LOGGER.info(f"[Template] Entering template setup. Current: '{current_template}'")

    message = _("marzban_template.title")
    message += _("marzban_template.description")
    message += _("marzban_template.current_template", template=f"`{current_template}`")
    message += _("marzban_template.prompt")

    await update.message.reply_text(
        message, reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN
    )
    return SET_TEMPLATE_USER_PROMPT

async def set_template_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    username = normalize_username(update.message.text.strip())
    await update.message.reply_text(_("marzban_template.checking_user", username=f"`{username}`"))

    user_data = await get_user_data(username)
    if not user_data:
        await update.message.reply_text(_("marzban_template.user_not_found", username=f"`{username}`"))
        return SET_TEMPLATE_USER_PROMPT

    proxies = user_data.get("proxies")
    inbounds = user_data.get("inbounds")
    if not proxies or not inbounds:
        await update.message.reply_text(_("marzban_template.validation_error", username=f"`{username}`"))
        return SET_TEMPLATE_USER_PROMPT

    template_config = {"template_username": username, "proxies": proxies, "inbounds": inbounds}
    LOGGER.info(f"[Template] Saving new template config: {template_config}")
    await save_template_config(template_config)

    confirmation_message = _("marzban_template.success_title")
    confirmation_message += _("marzban_template.success_username", username=f"`{username}`")
    confirmation_message += _("marzban_template.success_inbounds", count=f"`{len(inbounds)}`")
    confirmation_message += _("marzban_template.success_proxies", count=f"`{len(proxies)}`")
    confirmation_message += _("marzban_template.success_footer")

    await update.message.reply_text(
        confirmation_message, reply_markup=get_settings_and_tools_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END