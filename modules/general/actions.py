# FILE: modules/general/actions.py (FINAL VERSION - NAMESPACE CORRECTED)

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database import db_manager
from config import config
from modules.auth import is_admin, admin_only
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

# =============================================================================
#  Central helper function for displaying the main menu
# =============================================================================

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = ""):
    user = update.effective_user
    
    if not message_text:
        # --- FIX: Added 'general.' namespace ---
        message_text = _("general.welcome", first_name=user.first_name)

    if user.id in config.AUTHORIZED_USER_IDS and not context.user_data.get('is_admin_in_customer_view'):
        reply_markup = get_admin_main_menu_keyboard() 
        # --- FIX: Added 'general.' namespace ---
        message_text += _("general.admin_dashboard_active")
    else:
        if context.user_data.get('is_admin_in_customer_view'):
            reply_markup = await get_customer_view_for_admin_keyboard()
        else:
            reply_markup = await get_customer_main_menu_keyboard(update.effective_user.id)
        # --- FIX: Added 'general.' namespace ---
        message_text += _("general.customer_dashboard_prompt")

    target_message = update.effective_message
    if update.callback_query:
        try:
            await target_message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup)
    else:
        await target_message.reply_text(message_text, reply_markup=reply_markup)

# =============================================================================
#  Core Action Functions
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        is_new_user = await db_manager.add_or_update_user(user)
        if is_new_user:
            await log_new_user_joined(context.bot, user)
    except Exception as e:
        # --- FIX: Added 'errors.' namespace ---
        log_message = _("errors.db_user_save_failed", user_id=user.id, error=e)
        LOGGER.error(log_message)
        
    await send_main_menu(update, context)


@admin_only
async def switch_to_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['is_admin_in_customer_view'] = True
    # --- FIX: Added 'general.' namespace ---
    await update.message.reply_text(
        _("general.views.switched_to_customer"),
        reply_markup=await get_customer_view_for_admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def switch_to_admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop('is_admin_in_customer_view', None)
    # --- FIX: Added 'general.' namespace ---
    await update.message.reply_text(
        _("general.views.switched_to_admin"),
        reply_markup=get_admin_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    
async def handle_user_linking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass

async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    # --- FIX: Added 'general.' namespace ---
    message_text = _("general.your_telegram_id", user_id=user_id)
    await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)

# =============================================================================
#  Reusable Conversation Ending Functions
# =============================================================================

async def end_conversation_and_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    LOGGER.info(f"--- Fallback triggered for user {update.effective_user.id}. Ending conversation. ---")
    context.user_data.clear()
    # --- FIX: Added 'general.' namespace ---
    await send_main_menu(update, context, message_text=_("general.operation_cancelled"))
    return ConversationHandler.END


async def end_conv_and_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from modules.customer.actions import panel, service, guide
    from shared.translator import _

    text = update.message.text
    LOGGER.info(f"--- Main menu override for user {update.effective_user.id} by '{text}'. Ending conversation and rerouting. ---")

    # --- FIX: All keys now use the 'keyboards.' namespace ---
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
        await start(update, context)

    return ConversationHandler.END

async def handle_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    if args and len(args) > 0 and args[0].startswith("link-"):
        marzban_username_raw = args[0].split('-', 1)[1]
        marzban_username_normalized = normalize_username(marzban_username_raw)
        telegram_user_id = user.id
        LOGGER.info(f"User {telegram_user_id} started bot with deep link for Marzban user '{marzban_username_raw}'.")
        marzban_user_data = await get_user_data(marzban_username_normalized)
        if not marzban_user_data or "error" in marzban_user_data:
            # --- FIX: Added 'marzban.' namespace ---
            await update.message.reply_text(_("marzban.linking.user_not_found"))
            await start(update, context)
            return
        success = await link_user_to_telegram(marzban_username_normalized, telegram_user_id)
        # کد جدید
        if success:
            safe_username = html.escape(marzban_username_raw)
            await update.message.reply_text(_("marzban.linking.link_successful", username=safe_username), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(_("marzban.linking.link_error"))
        await start(update, context)
    else:
        await start(update, context)

async def admin_fallback_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from modules.marzban.handler import show_user_management_menu
    from modules.financials.handler import show_settings_and_tools_menu
    
    user = update.effective_user
    text = update.message.text
    LOGGER.info(f"--- [Admin Fallback] Admin {user.id} triggered reroute with '{text}'. Ending conversation. ---")
    context.user_data.clear()
    
    # --- NOTE: This part is not using the translator, so no changes needed here. ---
    if 'مدیریت کاربران' in text:
        await show_user_management_menu(update, context)
    elif 'تنظیمات و ابزارها' in text:
        await show_settings_and_tools_menu(update, context)
    else: 
        await start(update, context)
    
    return ConversationHandler.END