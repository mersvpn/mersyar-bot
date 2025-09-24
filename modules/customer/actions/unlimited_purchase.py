# FILE: modules/customer/actions/unlimited_purchase.py (COMPLETE AND FINAL VERSION)

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
# Import the new, centralized rerouting function
from modules.general.actions import end_conv_and_reroute
from shared.callbacks import end_conversation_and_show_menu

LOGGER = logging.getLogger(__name__)

# --- Conversation States and Constants ---
ASK_USERNAME, CHOOSE_PLAN, CONFIRM_UNLIMITED_PLAN = range(3)
USERNAME_PATTERN = r"^[a-zA-Z0-9_]{5,20}$"
CANCEL_CALLBACK_DATA = "cancel_unlimited_plan"
CANCEL_BUTTON = InlineKeyboardButton("✖️ لغو و بازگشت به فروشگاه", callback_data=CANCEL_CALLBACK_DATA)


# --- Core Conversation Functions (Unchanged) ---

async def start_unlimited_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    text = (
        "💎 *خرید پلن نامحدود*\n\n"
        "مرحله ۱ از ۲: لطفاً یک **نام کاربری دلخواه** وارد کنید.\n\n"
        "❗️ نام کاربری باید بین `5` تا `20` حرف **انگلیسی** و **اعداد**، بدون فاصله باشد."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_to_main_menu_keyboard())
    return ASK_USERNAME

async def get_username_and_ask_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username_input = update.message.text.strip()
    if not re.match(USERNAME_PATTERN, username_input):
        await update.message.reply_text("❌ نام کاربری نامعتبر است. لطفاً دوباره تلاش کنید.")
        return ASK_USERNAME

    username_to_check = normalize_username(username_input)
    existing_user = await get_user_data(username_to_check)
    if existing_user and "error" not in existing_user:
        await update.message.reply_text("❌ این نام کاربری قبلاً استفاده شده است.")
        return ASK_USERNAME

    context.user_data['unlimited_plan'] = {'username': username_to_check}
    active_plans = await get_active_unlimited_plans()
    if not active_plans:
        await update.message.reply_text("متاسفانه در حال حاضر هیچ پلن نامحدودی برای فروش موجود نیست.", reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    keyboard_rows = [[InlineKeyboardButton(f"{p['plan_name']} - {p['price']:,} تومان", callback_data=f"unlim_select_{p['id']}")] for p in active_plans]
    keyboard_rows.append([CANCEL_BUTTON])
    
    text = (f"✅ نام کاربری `{username_to_check}` انتخاب شد.\n\n"
            "مرحله ۲ از ۲: لطفاً یکی از پلن‌های زیر را انتخاب کنید:")
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN)
    return CHOOSE_PLAN

async def select_plan_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    plan_id = int(query.data.split('_')[-1])
    plan = await get_unlimited_plan_by_id(plan_id)
    if not plan or not plan['is_active']:
        await query.edit_message_text("❌ این پلن دیگر در دسترس نیست.", reply_markup=None)
        return ConversationHandler.END

    context.user_data['unlimited_plan'].update({'plan_id': plan['id'], 'price': plan['price'], 'max_ips': plan['max_ips']})
    username = context.user_data['unlimited_plan']['username']

    text = (f"🧾 *پیش‌فاکتور پلن نامحدود*\n\n"
            f"👤 نام کاربری: *{username}*\n🔸 نوع پلن: *{plan['plan_name']}*\n"
            f"🔸 تعداد کاربر: *{plan['max_ips']} دستگاه همزمان*\n"
            f"-------------------------------------\n"
            f"💳 مبلغ قابل پرداخت: *{plan['price']:,} تومان*\n\n"
            "آیا اطلاعات فوق را تایید می‌کنید?")
    keyboard = [[InlineKeyboardButton("✅ تایید و دریافت فاکتور", callback_data="unlim_confirm_final"), CANCEL_BUTTON]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_UNLIMITED_PLAN

async def generate_unlimited_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("... در حال صدور فاکتور")
    
    user_id = query.from_user.id
    plan_data = context.user_data.get('unlimited_plan')
    if not plan_data:
        await query.edit_message_text("❌ خطایی رخ داد. اطلاعات پلن یافت نشد.")
        return ConversationHandler.END

    plan_details_for_db = {
        "invoice_type": "NEW_USER_UNLIMITED", # <-- CHANGE THIS
        "username": plan_data['username'], 
        "plan_id": plan_data['plan_id'], 
        "max_ips": plan_data['max_ips'], 
        "volume": 0,  # <-- Set to 0 for unlimited
        "duration": 30, # This can be made dynamic later if needed
        "price": plan_data['price']
    }
    
    invoice_id = await create_pending_invoice(user_id, plan_details_for_db, plan_data['price'])
    if not invoice_id:
        await query.edit_message_text("❌ خطایی در سیستم رخ داد.")
        return ConversationHandler.END
        
    await query.message.delete()
    invoice_display_details = {"volume": "نامحدود", "duration": 30, "price": plan_data['price']}
    await send_custom_plan_invoice(update, context, invoice_display_details, invoice_id)
    return ConversationHandler.END

async def cancel_unlimited_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from modules.customer.actions.panel import show_customer_panel
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("فرآیند خرید پلن نامحدود لغو شد.", reply_markup=None)
    await show_customer_panel(query, context)
    return ConversationHandler.END


# --- Regex to match ALL main menu buttons ---
MAIN_MENU_REGEX = r'^(🛍️فــــــــــروشـــــــــــگاه|📊ســــــــرویس‌های من|📱 راهــــــــــنمای اتصال|🔙 بازگشت به منوی اصلی)$'
# --- Filter to IGNORE all main menu buttons, for use in states ---
IGNORE_MAIN_MENU_FILTER = filters.TEXT & ~filters.COMMAND & ~filters.Regex(MAIN_MENU_REGEX)


# --- THE FINAL, CORRECTED CONVERSATION HANDLER ---
unlimited_purchase_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^💎 اشتراک با حجم نامحدود$'), start_unlimited_purchase)],
    states={
        # This handler will now IGNORE main menu buttons, allowing fallbacks to catch them
        ASK_USERNAME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, get_username_and_ask_plan)],
        # CallbackQueryHandlers are not affected by text messages, so they are safe
        CHOOSE_PLAN: [CallbackQueryHandler(select_plan_and_confirm, pattern=r'^unlim_select_')],
        CONFIRM_UNLIMITED_PLAN: [CallbackQueryHandler(generate_unlimited_invoice, pattern='^unlim_confirm_final$')],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_unlimited_purchase, pattern=f'^{CANCEL_CALLBACK_DATA}$'),
        
        # This single handler now catches ALL main menu buttons and routes correctly
        MessageHandler(filters.Regex(MAIN_MENU_REGEX), end_conv_and_reroute),
    ],
    conversation_timeout=600,
)