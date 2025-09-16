# FILE: modules/customer/actions/purchase.py (REVISED FOR I18N)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from config import config
from shared.keyboards import get_back_to_main_menu_keyboard, get_customer_shop_keyboard
from shared.translator import _

LOGGER = logging.getLogger(__name__)

CONFIRM_PURCHASE = 0

async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the purchase conversation and presents confirmation buttons.
    """
    keyboard = [
        [InlineKeyboardButton(_("buttons.confirm_purchase_request"), callback_data="confirm_purchase_request")],
        [InlineKeyboardButton(_("buttons.back_to_shop_menu"), callback_data="back_to_shop_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = _("manual_purchase.confirm_request")

    await update.message.reply_text(text=text, reply_markup=reply_markup)
    
    await update.message.reply_text(
        _("manual_purchase.cancellation_prompt"),
        reply_markup=get_back_to_main_menu_keyboard()
    )

    return CONFIRM_PURCHASE

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Confirms the purchase, notifies admin, and ends the conversation.
    """
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    await query.edit_message_text(_("manual_purchase.request_sent_success"))

    if config.AUTHORIZED_USER_IDS:
        safe_full_name = escape_markdown(user.full_name, version=2)
        user_info = f"کاربر {safe_full_name}"
        if user.username:
            safe_username = escape_markdown(user.username, version=2)
            user_info += f" \\(@{safe_username}\\)"
        user_info += f"\nUser ID: `{user.id}`"
        
        message_to_admin = _("manual_purchase.admin_notification", user_info=user_info)

        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("buttons.create_config_for_user"), callback_data=f"create_user_for_{user.id}")]
        ])

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=message_to_admin,
                    reply_markup=admin_keyboard, parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception as e:
                LOGGER.error(f"Failed to send purchase notification to admin {admin_id}: {e}")
    
    return ConversationHandler.END

async def back_to_shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the 'back_to_shop_menu' callback.
    """
    query = update.callback_query
    await query.answer()
    
    await query.message.delete()
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=_("manual_purchase.back_to_shop"),
        reply_markup=get_customer_shop_keyboard()
    )
    
    return ConversationHandler.END

async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if config.SUPPORT_USERNAME:
        clean_username = config.SUPPORT_USERNAME.lstrip('@')
        support_link = f"https://t.me/{clean_username}"
        message = _("manual_purchase.support_prompt", username=clean_username, support_link=support_link)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await update.message.reply_text(_("manual_purchase.support_unavailable"))