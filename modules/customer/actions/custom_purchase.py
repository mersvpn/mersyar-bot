# FILE: modules/customer/actions/custom_purchase.py (نسخه نهایی با موتور قیمت‌گذاری پیشرونده و داینامیک)

import logging
import re
import math
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CommandHandler
)
from telegram.constants import ParseMode

# --- MODIFIED: Import the dynamic pricing loader ---
from database.db_manager import create_pending_invoice, load_pricing_parameters
from modules.financials.actions.payment import send_custom_plan_invoice
from .panel import show_customer_panel
from modules.marzban.actions.api import get_user_data
from modules.marzban.actions.data_manager import normalize_username

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
ASK_USERNAME, ASK_VOLUME, ASK_DURATION, CONFIRM_PLAN = range(4)

# --- Constants ---
MIN_VOLUME_GB = 10
MAX_VOLUME_GB = 120
MIN_DURATION_DAYS = 15
MAX_DURATION_DAYS = 90
USERNAME_PATTERN = r"^[a-zA-Z0-9_]{5,20}$"

# --- REMOVED: All hardcoded pricing constants are now loaded from the DB ---

# --- Standardize the cancel button and its callback data ---
CANCEL_CALLBACK_DATA = "cancel_custom_plan"
CANCEL_BUTTON = InlineKeyboardButton("✖️ لغو", callback_data=CANCEL_CALLBACK_DATA)


async def start_custom_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # --- NEW: Check if pricing is configured before starting ---
    pricing_params = await load_pricing_parameters()
    if not pricing_params.get("base_daily_price") or not pricing_params.get("tiers"):
        await query.edit_message_text("⚠️ متاسفانه امکان ساخت پلن دلخواه در حال حاضر وجود ندارد. (پیکربندی نشده)")
        return ConversationHandler.END

    context.user_data['custom_plan'] = {}
    text = (
        "💡 *ساخت پلن دلخواه*\n\n"
        "مرحله ۱ از ۳: لطفاً یک **نام کاربری دلخواه** وارد کنید.\n\n"
        "❗️ نام کاربری باید بین `5` تا `20` حرف **انگلیسی** و **اعداد**، بدون فاصله باشد."
    )
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    return ASK_USERNAME

async def get_username_and_ask_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function remains unchanged
    username_input = update.message.text.strip()
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    if not re.match(USERNAME_PATTERN, username_input):
        await update.message.reply_text("❌ نام کاربری نامعتبر است. لطفاً دوباره تلاش کنید.", reply_markup=reply_markup)
        return ASK_USERNAME
    username_to_check = normalize_username(username_input)
    existing_user = await get_user_data(username_to_check)
    if existing_user and "error" not in existing_user:
        await update.message.reply_text("❌ این نام کاربری قبلاً استفاده شده است.", reply_markup=reply_markup)
        return ASK_USERNAME
    context.user_data['custom_plan']['username'] = username_to_check
    user_message = (
        f"✅ نام کاربری `{username_to_check}` انتخاب شد.\n\n"
        "مرحله ۲ از ۳: حجم مورد نظر خود را به **گیگابایت (GB)** وارد کنید.\n\n"
        f"حجم مجاز بین **{MIN_VOLUME_GB}** تا **{MAX_VOLUME_GB}** گیگابایت است."
    )
    await update.message.reply_text(user_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    return ASK_VOLUME

async def get_volume_and_ask_for_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function remains unchanged
    volume_text = update.message.text.strip()
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    try:
        volume = int(volume_text)
        if not (MIN_VOLUME_GB <= volume <= MAX_VOLUME_GB):
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ حجم نامعتبر. لطفاً عددی بین **{MIN_VOLUME_GB}** تا **{MAX_VOLUME_GB}** وارد کنید.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )
        return ASK_VOLUME
    context.user_data['custom_plan']['volume'] = volume
    username = context.user_data['custom_plan']['username']
    text = (
        f"✅ نام کاربری: `{username}`\n"
        f"✅ حجم: `{volume}` گیگابایت\n\n"
        "مرحله ۳ از ۳: مدت زمان اشتراک را به **روز** وارد کنید.\n\n"
        f"مدت زمان مجاز بین **{MIN_DURATION_DAYS}** تا **{MAX_DURATION_DAYS}** روز است."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    return ASK_DURATION

async def get_duration_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    duration_text = update.message.text.strip()
    reply_markup_error = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    try:
        duration = int(duration_text)
        if not (MIN_DURATION_DAYS <= duration <= MAX_DURATION_DAYS):
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ مدت نامعتبر. لطفاً عددی بین **{MIN_DURATION_DAYS}** تا **{MAX_DURATION_DAYS}** وارد کنید.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup_error
        )
        return ASK_DURATION

    context.user_data['custom_plan']['duration'] = duration
    plan = context.user_data['custom_plan']
    username, volume = plan['username'], plan['volume']
    
    # --- START: DYNAMIC & PROGRESSIVE PRICING ENGINE ---
    
    pricing_params = await load_pricing_parameters()
    base_daily_price = pricing_params.get("base_daily_price")
    tiers = pricing_params.get("tiers", [])

    if not base_daily_price or not tiers:
        await update.message.reply_text("❌ خطای پیکربندی: قیمت‌گذاری به درستی تنظیم نشده است.")
        return ConversationHandler.END

    base_fee = duration * base_daily_price
    
    data_fee = 0
    remaining_volume = volume
    last_tier_limit = 0

    # Sort tiers by volume limit to ensure correct calculation order
    for tier in sorted(tiers, key=lambda x: x['volume_limit_gb']):
        tier_limit = tier['volume_limit_gb']
        tier_price = tier['price_per_gb']
        
        volume_in_this_tier = max(0, min(remaining_volume, tier_limit - last_tier_limit))
        
        data_fee += volume_in_this_tier * tier_price
        remaining_volume -= volume_in_this_tier
        last_tier_limit = tier_limit

        if remaining_volume <= 0:
            break
    
    if remaining_volume > 0 and tiers:
        # Use the price of the highest tier for any remaining volume
        last_tier_price = sorted(tiers, key=lambda x: x['volume_limit_gb'])[-1]['price_per_gb']
        data_fee += remaining_volume * last_tier_price

    raw_price = base_fee + data_fee
    
    # --- NEW: Round the final price to the nearest 5000 ---
    total_price = round(raw_price / 5000) * 5000
    # --- END: NEW PRICING ENGINE ---
    
    context.user_data['custom_plan']['price'] = total_price

    text = (
        f"🧾 *پیش‌فاکتور پلن دلخواه شما*\n\n"
        f"👤 نام کاربری: *{username}*\n"
        f"🔸 حجم: *{volume} گیگابایت*\n"
        f"🔸 مدت: *{duration} روز*\n"
        f"-------------------------------------\n"
        f"💳 مبلغ قابل پرداخت: *{total_price:,.0f} تومان*\n\n"
        "آیا اطلاعات فوق را تایید می‌کنید؟"
    )
    keyboard = [[
        InlineKeyboardButton("✅ تایید و دریافت فاکتور", callback_data="confirm_custom_plan"),
        CANCEL_BUTTON
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_PLAN


async def generate_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function remains unchanged
    query = update.callback_query
    user_id = query.from_user.id
    plan_details = context.user_data.get('custom_plan')
    if not plan_details:
        await query.edit_message_text("❌ خطایی رخ داد. اطلاعات پلن یافت نشد.")
        return ConversationHandler.END
    price = plan_details.get('price')
    await query.answer("... در حال صدور فاکتور")
    invoice_id = await create_pending_invoice(user_id, plan_details, price)
    if not invoice_id:
        await query.edit_message_text("❌ خطایی در سیستم رخ داد. لطفاً دوباره تلاش کنید.")
        context.user_data.clear()
        return ConversationHandler.END
    await query.message.delete()
    await send_custom_plan_invoice(update, context, plan_details, invoice_id)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_custom_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function remains unchanged
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("فرآیند ساخت پلن دلخواه لغو شد.")
        await show_customer_panel(update, context)
    else:
        await update.message.reply_text("فرآیند ساخت پلن دلخواه لغو شد.")
    context.user_data.clear()
    return ConversationHandler.END

custom_purchase_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_custom_purchase, pattern='^customer_custom_purchase$')],
    states={
        ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username_and_ask_volume)],
        ASK_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_volume_and_ask_for_duration)],
        ASK_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration_and_confirm)],
        CONFIRM_PLAN: [
            CallbackQueryHandler(generate_invoice, pattern='^confirm_custom_plan$'),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_custom_purchase, pattern=f'^{CANCEL_CALLBACK_DATA}$'),
        CommandHandler('cancel', cancel_custom_purchase),
        CommandHandler('start', cancel_custom_purchase)
    ],
    conversation_timeout=600
)