# FILE: modules/customer/actions/unlimited_purchase.py (نسخه نهایی و اصلاح شده)

import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters
)
from telegram.constants import ParseMode

# --- Local Imports ---
from database.db_manager import get_active_unlimited_plans, create_pending_invoice, get_unlimited_plan_by_id
from modules.financials.actions.payment import send_custom_plan_invoice
from .panel import show_customer_panel
from modules.marzban.actions.api import get_user_data
from modules.marzban.actions.data_manager import normalize_username

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
ASK_USERNAME, CHOOSE_PLAN, CONFIRM_UNLIMITED_PLAN = range(3)

# --- Constants ---
USERNAME_PATTERN = r"^[a-zA-Z0-9_]{5,20}$"
CANCEL_CALLBACK_DATA = "cancel_unlimited_plan"
CANCEL_BUTTON = InlineKeyboardButton("✖️ لغو", callback_data=CANCEL_CALLBACK_DATA)

# =============================================================================
#  Unlimited Plan Purchase Conversation
# =============================================================================

async def start_unlimited_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation for purchasing an unlimited plan."""
    query = update.callback_query
    await query.answer()
    context.user_data['unlimited_plan'] = {}

    text = (
        "💎 *خرید پلن نامحدود*\n\n"
        "مرحله ۱ از ۲: لطفاً یک **نام کاربری دلخواه** وارد کنید.\n\n"
        "❗️ نام کاربری باید بین `5` تا `20` حرف **انگلیسی** و **اعداد**، بدون فاصله باشد."
    )
    
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    return ASK_USERNAME

async def get_username_and_ask_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets username, validates it, and shows available unlimited plans."""
    username_input = update.message.text.strip()
    reply_markup = InlineKeyboardMarkup([[CANCEL_BUTTON]])

    if not re.match(USERNAME_PATTERN, username_input):
        await update.message.reply_text("❌ نام کاربری نامعتبر است. لطفاً دوباره تلاش کنید.", reply_markup=reply_markup)
        return ASK_USERNAME

    username_to_check = normalize_username(username_input)
    existing_user = await get_user_data(username_to_check)
    
    if existing_user and "error" not in existing_user:
        await update.message.reply_text(
            "❌ این نام کاربری قبلاً استفاده شده است. لطفاً یک نام دیگر انتخاب کنید.",
            reply_markup=reply_markup
        )
        return ASK_USERNAME

    context.user_data['unlimited_plan']['username'] = username_to_check
    
    active_plans = await get_active_unlimited_plans()
    
    if not active_plans:
        await update.message.reply_text("متاسفانه در حال حاضر هیچ پلن نامحدودی برای فروش موجود نیست. لطفاً بعداً تلاش کنید.")
        context.user_data.clear()
        return ConversationHandler.END

    keyboard_rows = []
    for plan in active_plans:
        button_text = f"{plan['plan_name']} - {plan['price']:,} تومان"
        callback_data = f"unlim_select_{plan['id']}"
        keyboard_rows.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard_rows.append([CANCEL_BUTTON])
    
    text = (
        f"✅ نام کاربری `{username_to_check}` انتخاب شد.\n\n"
        "مرحله ۲ از ۲: لطفاً یکی از پلن‌های زیر را انتخاب کنید:"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN)
    return CHOOSE_PLAN

async def select_plan_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows the confirmation message for the selected unlimited plan."""
    query = update.callback_query
    await query.answer()
    
    plan_id = int(query.data.split('_')[-1])
    plan = await get_unlimited_plan_by_id(plan_id)
    
    if not plan or not plan['is_active']:
        await query.edit_message_text("❌ این پلن دیگر در دسترس نیست. لطفاً دوباره تلاش کنید.")
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data['unlimited_plan']['plan_id'] = plan['id']
    context.user_data['unlimited_plan']['price'] = plan['price']
    context.user_data['unlimited_plan']['max_ips'] = plan['max_ips']
    
    username = context.user_data['unlimited_plan']['username']

    text = (
        f"🧾 *پیش‌فاکتور پلن نامحدود*\n\n"
        f"👤 نام کاربری: *{username}*\n"
        f"🔸 نوع پلن: *{plan['plan_name']}*\n"
        f"🔸 تعداد کاربر: *{plan['max_ips']} دستگاه همزمان*\n"
        f"-------------------------------------\n"
        f"💳 مبلغ قابل پرداخت: *{plan['price']:,} تومان*\n\n"
        "آیا اطلاعات فوق را تایید می‌کنید؟"
    )
    keyboard = [[
        InlineKeyboardButton("✅ تایید و دریافت فاکتور", callback_data="unlim_confirm_final"),
        CANCEL_BUTTON
    ]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_UNLIMITED_PLAN

async def generate_unlimited_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates the final invoice for the user."""
    query = update.callback_query
    await query.answer("... در حال صدور فاکتور")
    
    user_id = query.from_user.id
    plan_data = context.user_data.get('unlimited_plan')

    if not plan_data:
        await query.edit_message_text("❌ خطایی رخ داد. اطلاعات پلن یافت نشد.")
        return ConversationHandler.END

    # --- START: MODIFIED SECTION ---
    plan_details_for_db = {
        "plan_type": "unlimited",
        "username": plan_data['username'],
        "plan_id": plan_data['plan_id'],
        "max_ips": plan_data['max_ips'],
        "volume": 999,  # Represents "unlimited"
        "duration": 30,
        "price": plan_data['price']  # <-- FIX: Added the price to the details
    }
    # --- END: MODIFIED SECTION ---
    
    invoice_id = await create_pending_invoice(user_id, plan_details_for_db, plan_data['price'])
    
    if not invoice_id:
        await query.edit_message_text("❌ خطایی در سیستم رخ داد. لطفاً دوباره تلاش کنید.")
        context.user_data.clear()
        return ConversationHandler.END
        
    await query.message.delete()
    # This dictionary is just for display purposes in the invoice message
    invoice_display_details = {
        "volume": "نامحدود",
        "duration": 30,
        "price": plan_data['price']
    }
    await send_custom_plan_invoice(update, context, invoice_display_details, invoice_id)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_unlimited_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the unlimited plan purchase conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("فرآیند خرید پلن نامحدود لغو شد.")
        await show_customer_panel(update, context)
    else:
        await update.message.reply_text("فرآیند خرید پلن نامحدود لغو شد.")
    
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
#  Conversation Handler Definition
# =============================================================================

# --- FIX: Corrected variable name to match what handler.py expects ---
unlimited_purchase_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_unlimited_purchase, pattern='^customer_unlimited_purchase$')],
    states={
        ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username_and_ask_plan)],
        CHOOSE_PLAN: [CallbackQueryHandler(select_plan_and_confirm, pattern=r'^unlim_select_')],
        CONFIRM_UNLIMITED_PLAN: [
            CallbackQueryHandler(generate_unlimited_invoice, pattern='^unlim_confirm_final$')
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_unlimited_purchase, pattern=f'^{CANCEL_CALLBACK_DATA}$'),
        CommandHandler('cancel', cancel_unlimited_purchase),
        CommandHandler('start', cancel_unlimited_purchase)
    ],
    conversation_timeout=600
)