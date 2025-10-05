# FILE: modules/customer/actions/custom_purchase.py (REVISED FOR I18N)

import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

from . import panel, service, guide
from database.db_manager import create_pending_invoice, load_pricing_parameters
from modules.payment.actions.creation import send_custom_plan_invoice
from shared.keyboards import get_back_to_main_menu_keyboard, get_customer_shop_keyboard
from modules.marzban.actions.api import get_user_data
from modules.marzban.actions.data_manager import normalize_username
from shared.translator import _

LOGGER = logging.getLogger(__name__)

ASK_USERNAME, ASK_VOLUME, ASK_DURATION, CONFIRM_PLAN = range(4)
MIN_VOLUME_GB, MAX_VOLUME_GB = 10, 120
MIN_DURATION_DAYS, MAX_DURATION_DAYS = 15, 90
USERNAME_PATTERN = r"^[a-zA-Z0-9_]{5,20}$"
CANCEL_CALLBACK_DATA = "cancel_custom_plan"
CANCEL_BUTTON = InlineKeyboardButton(_("buttons.cancel_custom_plan"), callback_data=CANCEL_CALLBACK_DATA)


async def start_custom_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pricing_params = await load_pricing_parameters()
    
    # (✨ FIX) Determine the target message/chat
    chat_id = update.effective_chat.id
    target_message = update.callback_query.message if update.callback_query else update.message

    if not pricing_params.get("base_daily_price") or not pricing_params.get("tiers"):
        error_text = _("custom_purchase.not_configured")
        if update.callback_query:
            await update.callback_query.answer(error_text, show_alert=True)
        else:
            await target_message.reply_text(error_text, reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END
        
    context.user_data.clear()
    text = _("custom_purchase.step1_ask_username")
    
    # (✨ FIX) Respond based on the type of update
    if update.callback_query:
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_main_menu_keyboard())
    else:
        await target_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_main_menu_keyboard())

    return ASK_USERNAME

async def get_username_and_ask_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username_input = update.message.text.strip()
    if not re.match(USERNAME_PATTERN, username_input):
        await update.message.reply_text(_("custom_purchase.username_invalid"))
        return ASK_USERNAME
    username_to_check = normalize_username(username_input)
    existing_user = await get_user_data(username_to_check)
    if existing_user and "error" not in existing_user:
        await update.message.reply_text(_("custom_purchase.username_taken"))
        return ASK_USERNAME
    context.user_data['custom_plan'] = {'username': username_to_check}
    user_message = _("custom_purchase.step2_ask_volume", username=f"`{username_to_check}`", min_volume=MIN_VOLUME_GB, max_volume=MAX_VOLUME_GB)
    await update.message.reply_text(user_message, parse_mode=ParseMode.MARKDOWN)
    return ASK_VOLUME

async def get_volume_and_ask_for_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    volume_text = update.message.text.strip()
    try:
        volume = int(volume_text)
        if not (MIN_VOLUME_GB <= volume <= MAX_VOLUME_GB): raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("custom_purchase.volume_invalid", min_volume=MIN_VOLUME_GB, max_volume=MAX_VOLUME_GB), parse_mode=ParseMode.MARKDOWN)
        return ASK_VOLUME
    context.user_data['custom_plan']['volume'] = volume
    plan_data = context.user_data['custom_plan']
    text = _("custom_purchase.step3_ask_duration", username=f"`{plan_data['username']}`", volume=f"`{plan_data['volume']}`", min_duration=MIN_DURATION_DAYS, max_duration=MAX_DURATION_DAYS)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return ASK_DURATION

async def get_duration_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    duration_text = update.message.text.strip()
    try:
        duration = int(duration_text)
        if not (MIN_DURATION_DAYS <= duration <= MAX_DURATION_DAYS): raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("custom_purchase.duration_invalid", min_duration=MIN_DURATION_DAYS, max_duration=MAX_DURATION_DAYS), parse_mode=ParseMode.MARKDOWN)
        return ASK_DURATION
    context.user_data['custom_plan']['duration'] = duration
    plan = context.user_data['custom_plan']
    
    # Pricing logic remains unchanged
    pricing_params = await load_pricing_parameters()
    base_daily_price = pricing_params.get("base_daily_price", 0)
    tiers = pricing_params.get("tiers", [])
    base_fee = duration * base_daily_price
    data_fee = 0
    remaining_volume = plan['volume']
    last_tier_limit = 0
    for tier in sorted(tiers, key=lambda x: x['volume_limit_gb']):
        tier_limit, tier_price = tier['volume_limit_gb'], tier['price_per_gb']
        volume_in_this_tier = max(0, min(remaining_volume, tier_limit - last_tier_limit))
        data_fee += volume_in_this_tier * tier_price
        remaining_volume -= volume_in_this_tier
        last_tier_limit = tier_limit
        if remaining_volume <= 0: break
    if remaining_volume > 0 and tiers:
        last_tier_price = sorted(tiers, key=lambda x: x['volume_limit_gb'])[-1]['price_per_gb']
        data_fee += remaining_volume * last_tier_price
    raw_price = base_fee + data_fee
    total_price = round(raw_price / 5000) * 5000
    context.user_data['custom_plan']['price'] = total_price
    
    text = _("custom_purchase.invoice_preview", 
             username=plan['username'], 
             volume=plan['volume'], 
             duration=plan['duration'], 
             price=total_price)
    
    keyboard = [[InlineKeyboardButton(_("buttons.confirm_and_get_invoice"), callback_data="confirm_custom_plan"), CANCEL_BUTTON]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_PLAN

async def generate_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(_("customer_service.generating_invoice"))
    user_id = query.from_user.id
    plan_details = context.user_data.get('custom_plan')
    plan_details['invoice_type'] = 'NEW_USER_CUSTOM'
    if not plan_details:
        await query.edit_message_text(_("errors.plan_info_not_found"))
        return ConversationHandler.END
    price = plan_details.get('price')
    invoice_id = await create_pending_invoice(user_id, plan_details, price)
    if not invoice_id:
        await query.edit_message_text(_("customer_service.system_error_retry"))
        context.user_data.clear()
        return ConversationHandler.END
    await query.message.delete()
    await send_custom_plan_invoice(update, context, plan_details, invoice_id)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_custom_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("custom_purchase.plan_cancelled"), reply_markup=None)
    context.user_data.clear()

    # (✨ BUG FIX) Create a more complete DummyUpdate object with 'effective_chat'.
    class DummyUpdate:
        def __init__(self, original_update):
            self.message = original_update.effective_message
            self.effective_chat = original_update.effective_chat
            self.callback_query = None
            
    await panel.show_customer_panel(DummyUpdate(update), context)
    return ConversationHandler.END

# The rerouting logic and handlers remain the same, as they rely on button texts
# which are now being translated correctly via keyboards.py.

async def end_conv_and_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    LOGGER.info(f"--- Main menu fallback triggered by '{text}'. Ending conversation. ---")
    
    shop_button = _("keyboards.customer_main_menu.shop")
    service_button = _("keyboards.customer_main_menu.my_services")
    guide_button = _("keyboards.customer_main_menu.connection_guide")

    if shop_button in text:
        await panel.show_customer_panel(update, context)
    elif service_button in text:
        await service.handle_my_service(update, context)
    elif guide_button in text:
        await guide.handle_customer_guide(update, context)
    
    return ConversationHandler.END

# Dynamically create the regex from translated button texts
MAIN_MENU_REGEX = f'^({_("keyboards.customer_main_menu.shop")}|{_("keyboards.customer_main_menu.my_services")}|{_("keyboards.customer_main_menu.connection_guide")}|{_("keyboards.general.back_to_main_menu")})$'

IGNORE_MAIN_MENU_FILTER = filters.TEXT & ~filters.COMMAND & ~filters.Regex(MAIN_MENU_REGEX)

custom_purchase_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(f'^{_("keyboards.customer_shop.custom_volume_plan")}$'), start_custom_purchase)],
    states={
        ASK_USERNAME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, get_username_and_ask_volume)],
        ASK_VOLUME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, get_volume_and_ask_for_duration)],
        ASK_DURATION: [MessageHandler(IGNORE_MAIN_MENU_FILTER, get_duration_and_confirm)],
        CONFIRM_PLAN: [CallbackQueryHandler(generate_invoice, pattern='^confirm_custom_plan$')],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_custom_purchase, pattern=f'^{CANCEL_CALLBACK_DATA}$'),
        MessageHandler(filters.Regex(MAIN_MENU_REGEX), end_conv_and_reroute),
    ],
    conversation_timeout=600,
)