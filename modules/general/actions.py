# FILE: modules/general/actions.py (MODIFIED FOR FORCED JOIN)

import logging
from telegram import Update, User
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database import db_manager
from config import config
# (✨ MODIFIED) Import path is corrected and new decorator is added
from shared.auth import is_admin, admin_only, ensure_channel_membership
import html

from shared.log_channel import log_new_user_joined
from shared.translator import _
from shared.keyboards import (
    get_customer_main_menu_keyboard,
    get_admin_main_menu_keyboard,
    get_customer_view_for_admin_keyboard
)
from modules.marzban.actions.data_manager import link_user_to_telegram, normalize_username
from modules.marzban.actions.api import get_user_data

LOGGER = logging.getLogger(__name__)


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = ""):
    user = update.effective_user
    
    if not message_text:
        message_text = _("general.welcome", first_name=html.escape(user.first_name))

    if user.id in config.AUTHORIZED_USER_IDS and not context.user_data.get('is_admin_in_customer_view'):
        reply_markup = get_admin_main_menu_keyboard() 
        message_text += _("general.admin_dashboard_active")
    else:
        if context.user_data.get('is_admin_in_customer_view'):
            reply_markup = await get_customer_view_for_admin_keyboard()
        else:
            reply_markup = await get_customer_main_menu_keyboard(update.effective_user.id)
        message_text += _("general.customer_dashboard_prompt")

    target_message = update.effective_message
    if update.callback_query:
        # If it's a callback, we might need to delete the old message and send a new one.
        try:
            # Check if the message is the one that prompted the join, and edit it.
            if target_message and target_message.text and "باید در کانال زیر عضو شوید" in target_message.text:
                 await target_message.edit_text(message_text, reply_markup=reply_markup)
                 return
            else: # Otherwise, delete and send new
                await target_message.delete()
        except Exception: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup)
    else:
        await target_message.reply_text(message_text, reply_markup=reply_markup)


# (✨ MODIFIED) The decorator is applied to the start function
@ensure_channel_membership
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        is_new_user = await db_manager.add_or_update_user(user)
        if is_new_user:
            await log_new_user_joined(context.bot, user)
    except Exception as e:
        log_message = _("errors.db_user_save_failed", user_id=user.id, error=e)
        LOGGER.error(log_message)
        
    await send_main_menu(update, context)


@admin_only
async def switch_to_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['is_admin_in_customer_view'] = True
    await update.message.reply_text(
        _("general.views.switched_to_customer"),
        reply_markup=await get_customer_view_for_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def switch_to_admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop('is_admin_in_customer_view', None)
    await update.message.reply_text(
        _("general.views.switched_to_admin"),
        reply_markup=get_admin_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    
async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message_text = _("general.your_telegram_id", user_id=user_id)
    await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)


async def end_conv_and_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from modules.customer.actions import panel, service, guide
    text = update.message.text
    LOGGER.info(f"--- Main menu override for user {update.effective_user.id} by '{text}'. Ending conversation and rerouting. ---")

    shop_button_text = _("keyboards.customer_main_menu.shop")
    services_button_text = _("keyboards.customer_main_menu.my_services")
    guide_button_text = _("keyboards.customer_main_menu.connection_guide")

    if text == shop_button_text:
        await panel.show_customer_panel(update, context)
    elif text == services_button_text:
        await service.handle_my_service(update, context)
    elif text == guide_button_text:
        await guide.show_guides_to_customer(update, context)
    else:
        # Fallback to the main start function
        await start(update, context)

    context.user_data.clear()
    return ConversationHandler.END


async def notify_admins_on_link(context: ContextTypes.DEFAULT_TYPE, customer: User, marzban_username: str):
    message = _(
        "general.linking_admin_notification", 
        customer_name=html.escape(customer.full_name), 
        customer_id=customer.id, 
        username=html.escape(marzban_username)
    )
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode=ParseMode.HTML)
        except Exception as e:
            LOGGER.error(f"Failed to send linking notification to admin {admin_id}: {e}")

# (✨ MODIFIED) This function now always calls start() at the end to ensure the decorator runs
async def handle_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    # First, handle the potential linking process
    if args and len(args) > 0 and args[0].startswith("link-"):
        marzban_username_raw = args[0].split('-', 1)[1]
        marzban_username_normalized = normalize_username(marzban_username_raw)
        telegram_user_id = user.id
        LOGGER.info(f"User {telegram_user_id} started bot with deep link for Marzban user '{marzban_username_raw}'.")
        
        marzban_user_data = await get_user_data(marzban_username_normalized)
        if not marzban_user_data or "error" in marzban_user_data:
            await update.message.reply_text(_("marzban.linking.user_not_found"))
        else:
            success = await link_user_to_telegram(marzban_username_normalized, telegram_user_id)
            if success:
                safe_username = html.escape(marzban_username_raw)
                await update.message.reply_text(_("marzban.linking.link_successful", username=safe_username), parse_mode=ParseMode.HTML)
                await notify_admins_on_link(context, user, marzban_username_raw)
            else:
                await update.message.reply_text(_("marzban.linking.link_error"))

    # ALWAYS call the start function at the end. The decorator on start() will handle the join check.
    await start(update, context)