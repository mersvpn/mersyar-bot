# FILE: modules/customer/actions/unlimited_purchase.py (REVISED FOR I18N AND STABILITY)

import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode

from database.db_manager import get_active_unlimited_plans, create_pending_invoice, get_unlimited_plan_by_id
from modules.payment.actions.creation import send_custom_plan_invoice
from shared.keyboards import get_back_to_main_menu_keyboard, get_customer_shop_keyboard
from modules.marzban.actions.api import get_user_data
from modules.marzban.actions.data_manager import normalize_username
from modules.general.actions import end_conv_and_reroute
from shared.translator import _

LOGGER = logging.getLogger(__name__)

# --- Conversation States and Constants ---
ASK_USERNAME, CHOOSE_PLAN, CONFIRM_UNLIMITED_PLAN = range(3)
USERNAME_PATTERN = r"^[a-zA-Z0-9_]{5,20}$"
CANCEL_CALLBACK_DATA = "cancel_unlimited_plan"

# --- Helper function for dynamic cancel button ---
def _get_cancel_button() -> InlineKeyboardButton:
    """Creates a cancel button with translated text."""
    # (✨ TRANSLATION FIX) Use the full, correct key from keyboards.json
    return InlineKeyboardButton(_("inline_keyboards.buttons.cancel_and_back_to_shop"), callback_data=CANCEL_CALLBACK_DATA)


# FILE: modules/customer/actions/unlimited_purchase.py

async def start_unlimited_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- DIAGNOSTIC LOG START ---
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    trigger_type = "CallbackQuery" if update.callback_query else "Message"
    trigger_data = update.callback_query.data if update.callback_query else update.message.text
    
    LOGGER.info(f"[DIAGNOSTIC] Customer's 'start_unlimited_purchase' triggered for user {user_id}. Type: {trigger_type}, Data: '{trigger_data}'")
    # --- DIAGNOSTIC LOG END ---
    
    context.user_data.clear()
    text = _("unlimited_purchase.step1_ask_username")
    
    chat_id = update.effective_chat.id
    target_message = update.callback_query.message if update.callback_query else update.message

    if update.callback_query:
        await update.callback_query.answer()
        
        # (✨ BUG FIX) Wrap message deletion in a try-except block to prevent crashes.
        try:
            await target_message.delete()
        except Exception as e:
            LOGGER.warning(f"Could not delete the source message for deeplink purchase: {e}")
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=get_back_to_main_menu_keyboard()
        )
    else:
        await target_message.reply_text(
            text=text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=get_back_to_main_menu_keyboard()
        )

    return ASK_USERNAME

async def get_username_and_ask_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username_input = update.message.text.strip()
    if not re.match(USERNAME_PATTERN, username_input):
        # (✨ I18N) Use translator
        await update.message.reply_text(_("custom_purchase.username_invalid"))
        return ASK_USERNAME

    username_to_check = normalize_username(username_input)
    existing_user = await get_user_data(username_to_check)
    if existing_user and "error" not in existing_user:
        # (✨ I18N) Use translator
        await update.message.reply_text(_("custom_purchase.username_taken"))
        return ASK_USERNAME

    context.user_data['unlimited_plan'] = {'username': username_to_check}
    active_plans = await get_active_unlimited_plans()
    if not active_plans:
        # (✨ I18N) Use translator
        await update.message.reply_text(_("unlimited_purchase.no_plans_available"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    keyboard_rows = [
        # (✨ I18N) Use translator for button text format
        [InlineKeyboardButton(_("unlimited_purchase.plan_button_format", name=p['plan_name'], price=f"{p['price']:,}"), callback_data=f"unlim_select_{p['id']}")] 
        for p in active_plans
    ]
    keyboard_rows.append([_get_cancel_button()])
    
    # (✨ I18N) Use translator
    text = _("unlimited_purchase.step2_ask_plan", username=f"`{username_to_check}`")
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN)
    return CHOOSE_PLAN

async def select_plan_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    plan_id = int(query.data.split('_')[-1])
    plan = await get_unlimited_plan_by_id(plan_id)
    if not plan or not plan['is_active']:
        # (✨ I18N) Use translator
        await query.edit_message_text(_("unlimited_purchase.plan_not_available"), reply_markup=None)
        return ConversationHandler.END

    context.user_data['unlimited_plan'].update({'plan_id': plan['id'], 'price': plan['price'], 'max_ips': plan['max_ips']})
    username = context.user_data['unlimited_plan']['username']

    # (✨ I18N) Use translator for the invoice preview
    text = _("unlimited_purchase.invoice_preview",
             username=username,
             plan_name=plan['plan_name'],
             max_ips=plan['max_ips'],
             price=f"{plan['price']:,}")
             
    keyboard = [
        # (✨ I18N) Use translator for button text
        [InlineKeyboardButton(_("buttons.confirm_and_get_invoice"), callback_data="unlim_confirm_final")],
        [_get_cancel_button()]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_UNLIMITED_PLAN

async def generate_unlimited_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # (✨ I18N) Use translator
    await query.answer(_("customer_service.generating_invoice"))
    
    user_id = query.from_user.id
    plan_data = context.user_data.get('unlimited_plan')
    if not plan_data:
        # (✨ I18N) Use translator
        await query.edit_message_text(_("errors.plan_info_not_found"))
        return ConversationHandler.END

    plan_details_for_db = {
        "invoice_type": "NEW_USER_UNLIMITED",
        "username": plan_data['username'], 
        "plan_id": plan_data['plan_id'], 
        "max_ips": plan_data['max_ips'], 
        "volume": 0,
        "duration": 30,
        "price": plan_data['price']
    }
    
    invoice_id = await create_pending_invoice(user_id, plan_details_for_db, plan_data['price'])
    if not invoice_id:
        # (✨ I18N) Use translator
        await query.edit_message_text(_("customer_service.system_error_retry"))
        return ConversationHandler.END
        
    await query.message.delete()
    # (✨ I18N) Use translator for "unlimited" text
    invoice_display_details = {"volume": _("general.unlimited"), "duration": 30, "price": plan_data['price']}
    await send_custom_plan_invoice(update, context, invoice_display_details, invoice_id)
    context.user_data.clear()
    return ConversationHandler.END

# FILE: modules/customer/actions/unlimited_purchase.py

async def cancel_unlimited_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (REWRITTEN) Cancels the conversation and safely returns the user to the shop menu.
    """
    from .panel import show_customer_panel
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(_("unlimited_purchase.purchase_cancelled"), reply_markup=None)
    context.user_data.clear()
    
    # (✨ BUG FIX) Create a more complete DummyUpdate object with 'effective_chat'.
    class DummyUpdate:
        def __init__(self, original_update):
            self.message = original_update.effective_message
            self.effective_chat = original_update.effective_chat
            self.callback_query = None

    # Pass the original update object to get all necessary attributes
    await show_customer_panel(DummyUpdate(update), context)
    
    return ConversationHandler.END

# Dynamically create regex from translated button texts
MAIN_MENU_REGEX = f'^({_("keyboards.customer_main_menu.shop")}|{_("keyboards.customer_main_menu.my_services")}|{_("keyboards.customer_main_menu.connection_guide")}|{_("keyboards.general.back_to_main_menu")})$'
IGNORE_MAIN_MENU_FILTER = filters.TEXT & ~filters.COMMAND & ~filters.Regex(MAIN_MENU_REGEX)


unlimited_purchase_conv = ConversationHandler(
    # (✨ I18N) Entry point now uses translated button text
    entry_points=[MessageHandler(filters.Regex(f'^{_("keyboards.customer_shop.unlimited_volume_plan")}$'), start_unlimited_purchase)],
    states={
        ASK_USERNAME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, get_username_and_ask_plan)],
        CHOOSE_PLAN: [CallbackQueryHandler(select_plan_and_confirm, pattern=r'^unlim_select_')],
        CONFIRM_UNLIMITED_PLAN: [CallbackQueryHandler(generate_unlimited_invoice, pattern=r'^unlim_confirm_final$')],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_unlimited_purchase, pattern=f'^{CANCEL_CALLBACK_DATA}$'),
        MessageHandler(filters.Regex(MAIN_MENU_REGEX), end_conv_and_reroute),
    ],
    conversation_timeout=600,
)