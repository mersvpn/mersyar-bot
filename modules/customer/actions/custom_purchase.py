# FILE: modules/customer/actions/custom_purchase.py (نسخه نهایی با دکمه لغو در تمام مراحل)

import logging
import re
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

from database.db_manager import load_pricing_settings, create_pending_invoice
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
MAX_VOLUME_GB = 30
MIN_DURATION_DAYS = 10
MAX_DURATION_DAYS = 60
USERNAME_PATTERN = r"^[a-zA-Z0-9_]{5,20}$"

# --- FIX: Standardize the cancel button and its callback data ---
CANCEL_CALLBACK_DATA = "cancel_custom_plan"
CANCEL_BUTTON = InlineKeyboardButton("✖️ لغو", callback_data=CANCEL_CALLBACK_DATA)


async def start_custom_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    LOGGER.info(f"User {user_id} started the custom plan creation process.")
    
    pricing = await load_pricing_settings()
    if not pricing or pricing.get('price_per_gb') is None or pricing.get('price_per_day') is None:
        LOGGER.warning(f"Attempted to start custom purchase for user {user_id}, but pricing is not fully set.")
        text = "⚠️ متاسفانه امکان ساخت پلن دلخواه در حال حاضر وجود ندارد."
        await query.edit_message_text(text)
        return ConversationHandler.END

    context.user_data['custom_plan'] = {}
    context.user_data['pricing_settings'] = pricing

    text = (
        "💡 *ساخت پلن دلخواه*\n\n"
        "مرحله ۱ از ۳: لطفاً یک **نام کاربری دلخواه** وارد کنید.\n\n"
        "❗️ نام کاربری باید بین `5` تا `20` حرف **انگلیسی** و **اعداد**، بدون فاصله باشد."
    )
    
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    return ASK_USERNAME

async def get_username_and_ask_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    username_input = update.message.text.strip()
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])

    if not re.match(USERNAME_PATTERN, username_input):
        await update.message.reply_text("❌ نام کاربری نامعتبر است. لطفاً دوباره تلاش کنید.", reply_markup=reply_markup)
        return ASK_USERNAME

    username_to_check = normalize_username(username_input)
    existing_user = await get_user_data(username_to_check)
    
    if existing_user and "error" not in existing_user:
        LOGGER.info(f"User {user_id} tried to register with an existing username: '{username_to_check}'")
        await update.message.reply_text(
            "❌ این نام کاربری قبلاً استفاده شده است. لطفاً یک نام دیگر انتخاب کنید.",
            reply_markup=reply_markup
        )
        return ASK_USERNAME

    else:
        LOGGER.info(f"User {user_id} chose an available username: '{username_to_check}'")
        context.user_data['custom_plan']['username'] = username_to_check
        
        user_message = (
            f"✅ نام کاربری `{username_to_check}` با موفقیت انتخاب شد.\n\n"
            "مرحله ۲ از ۳: حجم مورد نظر خود را به **گیگابایت (GB)** وارد کنید.\n\n"
            f"حجم مجاز بین **{MIN_VOLUME_GB}** تا **{MAX_VOLUME_GB}** گیگابایت است."
        )
        await update.message.reply_text(user_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ASK_VOLUME

async def get_volume_and_ask_for_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    volume_text = update.message.text.strip()
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    
    try:
        volume = int(volume_text)
        if not (MIN_VOLUME_GB <= volume <= MAX_VOLUME_GB):
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ حجم نامعتبر است. لطفاً یک عدد بین **{MIN_VOLUME_GB}** تا **{MAX_VOLUME_GB}** وارد کنید.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return ASK_VOLUME

    context.user_data['custom_plan']['volume'] = volume
    LOGGER.info(f"User {user_id} chose volume: {volume} GB.")
    
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
    user_id = update.effective_user.id
    duration_text = update.message.text.strip()
    reply_markup_error = InlineKeyboardMarkup([[CANCEL_BUTTON]])

    try:
        duration = int(duration_text)
        if not (MIN_DURATION_DAYS <= duration <= MAX_DURATION_DAYS):
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ مدت زمان نامعتبر است. لطفاً یک عدد بین **{MIN_DURATION_DAYS}** تا **{MAX_DURATION_DAYS}** وارد کنید.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup_error
        )
        return ASK_DURATION

    context.user_data['custom_plan']['duration'] = duration
    LOGGER.info(f"User {user_id} chose duration: {duration} days.")

    plan = context.user_data['custom_plan']
    username, volume = plan['username'], plan['volume']
    
    pricing = context.user_data['pricing_settings']
    price_per_gb, price_per_day = pricing['price_per_gb'], pricing['price_per_day']
    
    total_price = (volume * price_per_gb) + (duration * price_per_day)
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
    query = update.callback_query
    user_id = query.from_user.id
    plan_details = context.user_data.get('custom_plan')
    
    if not plan_details:
        LOGGER.warning(f"User {user_id} reached generate_invoice without plan details in context.")
        await query.edit_message_text("❌ خطایی رخ داد. اطلاعات پلن یافت نشد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

    price = plan_details.get('price')
    
    LOGGER.info(f"User {user_id} confirmed custom plan: {plan_details}. Creating invoice.")
    await query.answer("... در حال صدور فاکتور")
    
    invoice_id = await create_pending_invoice(user_id, plan_details, price)
    if not invoice_id:
        await query.edit_message_text("❌ خطایی در سیستم رخ داد. لطفاً دوباره تلاش کنید.")
        context.user_data.clear()
        return ConversationHandler.END

    LOGGER.info(f"Pending invoice #{invoice_id} created for user {user_id}.")
    await query.message.delete()
    await send_custom_plan_invoice(update, context, plan_details, invoice_id)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_custom_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles both /cancel command and cancel button clicks."""
    if update.callback_query:
        # Triggered by button
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("فرآیند ساخت پلن دلخواه لغو شد.")
        # We call show_customer_panel to return to the previous inline menu
        await show_customer_panel(update, context)
    else:
        # Triggered by /cancel or /start command
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
        CommandHandler('start', cancel_custom_purchase) # Also cancel on /start
    ],
    conversation_timeout=600
)