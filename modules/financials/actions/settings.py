# FILE: modules/financials/actions/settings.py (نسخه نهایی با رفع TypeError و قیمت‌گذاری دو مرحله‌ای)

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters
)
from telegram.constants import ParseMode

# --- Local Imports ---
from database.db_manager import (
    load_financials, save_financials, 
    save_pricing_settings, load_pricing_settings
)
from shared.keyboards import get_financial_settings_keyboard, get_payment_methods_keyboard
from shared.callbacks import cancel_conversation
from modules.auth import admin_only

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- States for Conversations ---
# States for the card info conversation
(
    CARD_MENU,
    EDITING_HOLDER,
    EDITING_CARD
) = range(3)

# States for the pricing conversation
AWAITING_GB_PRICE, AWAITING_DAY_PRICE = range(3, 5)

# =============================================================================
# 1. توابع منوهای اصلی مالی
# =============================================================================

@admin_only
async def show_financial_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    LOGGER.info(f"Admin {user_id} accessed the main financial menu.")
    await update.message.reply_text(
        "💰 *تنظیمات مالی*\n\nلطفا بخش مورد نظر خود را انتخاب کنید:",
        reply_markup=get_financial_settings_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def show_payment_methods_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    LOGGER.info(f"Admin {user_id} accessed the payment methods submenu.")
    text = "💳 *تنظیمات پرداخت*\n\nاز این بخش می‌توانید روش‌های پرداخت را مدیریت کنید."
    keyboard = get_payment_methods_keyboard()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# =============================================================================
# 2. مکالمه تنظیم اطلاعات کارت به کارت
# =============================================================================

async def format_financial_info_message() -> str:
    financials = await load_financials()
    card_holder = financials.get('card_holder', 'تنظیم نشده')
    card_number = financials.get('card_number', 'تنظیم نشده')
    return (
        f"💳 *تنظیمات کارت به کارت*\n\n"
        f"👤 *نام صاحب حساب:*\n`{card_holder}`\n\n"
        f"🔢 *شماره کارت:*\n`{card_number}`\n\n"
        "برای ویرایش هر بخش، روی دکمه مربوطه کلیک کنید."
    )

def build_card_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👤 ویرایش نام", callback_data="fin_edit_holder"),
            InlineKeyboardButton("🔢 ویرایش شماره کارت", callback_data="fin_edit_card")
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_payment_methods")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_card_settings_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    LOGGER.info(f"Admin {user_id} started the card settings conversation.")
    message_text = await format_financial_info_message()
    keyboard = build_card_menu_keyboard()
    await query.answer()
    await query.edit_message_text(text=message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CARD_MENU

async def prompt_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split('_')[-1]
    context.user_data['financial_action'] = action
    prompt_map = {
        'holder': ("لطفاً نام جدید صاحب حساب را وارد کنید:", EDITING_HOLDER),
        'card': ("لطفاً شماره کارت ۱۶ رقمی را وارد کنید (فقط اعداد):", EDITING_CARD),
    }
    if action not in prompt_map:
        LOGGER.warning(f"Invalid action '{action}' in prompt_for_edit.")
        return CARD_MENU
    prompt_text, next_state = prompt_map[action]
    await query.edit_message_text(text=prompt_text)
    return next_state

async def save_financial_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    action = context.user_data.get('financial_action')
    new_value = update.message.text.strip()
    user_id = update.effective_user.id
    if not action:
        LOGGER.error(f"User {user_id} reached save_financial_info with no action in user_data.")
        await update.message.reply_text("خطا: عملیات نامشخص است. لطفاً دوباره تلاش کنید.")
        return await cancel_conversation(update, context)
    financial_data = await load_financials()
    confirmation_text = ""
    if action == 'holder':
        financial_data['card_holder'] = new_value
        confirmation_text = "✅ نام صاحب حساب با موفقیت به‌روز شد."
    elif action == 'card':
        card_number = "".join(filter(str.isdigit, new_value))
        if len(card_number) != 16:
            LOGGER.warning(f"Admin {user_id} entered an invalid card number.")
            await update.message.reply_text("❌ شماره کارت نامعتبر است. باید ۱۶ رقم باشد. لطفاً دوباره وارد کنید.")
            return EDITING_CARD
        financial_data['card_number'] = card_number
        confirmation_text = "✅ شماره کارت با موفقیت به‌روز شد."
    await save_financials(financial_data)
    LOGGER.info(f"Admin {user_id} successfully updated financial setting: {action}.")
    await update.message.reply_text(confirmation_text)
    context.user_data.pop('financial_action', None)
    await show_payment_methods_menu(update, context)
    return ConversationHandler.END

card_settings_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_card_settings_conv, pattern=r'^admin_set_card_info$')],
    states={
        CARD_MENU: [
            CallbackQueryHandler(prompt_for_edit, pattern=r'^fin_edit_'),
            CallbackQueryHandler(show_payment_methods_menu, pattern=r'^back_to_payment_methods$'),
        ],
        EDITING_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
        EDITING_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_financial_info)],
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=300,
    block=False
)

# =============================================================================
# 3. مکالمه تنظیم قیمت‌گذاری دلخواه (بازطراحی شده)
# =============================================================================

@admin_only
async def start_pricing_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    LOGGER.info(f"Admin {user_id} started the pricing settings conversation.")
    context.user_data['pricing'] = {}

    prices = await load_pricing_settings()
    price_gb = prices.get('price_per_gb')
    price_day = prices.get('price_per_day')
    
    current_gb_text = f"`{price_gb:,}` تومان" if price_gb is not None else "`تنظیم نشده`"
    current_day_text = f"`{price_day:,}` تومان" if price_day is not None else "`تنظیم نشده`"

    message_text = (
        f"💰 *تنظیم قیمت‌گذاری پلن دلخواه*\n\n"
        f"▫️ قیمت فعلی به ازای هر گیگابایت: {current_gb_text}\n"
        f"▫️ قیمت فعلی به ازای هر روز: {current_day_text}\n\n"
        "مرحله ۱ از ۲: لطفاً **قیمت جدید به ازای هر گیگابایت** را وارد کنید (فقط عدد و به تومان).\n"
        "برای لغو /cancel را ارسال کنید."
    )
    await update.message.reply_text(text=message_text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_GB_PRICE

@admin_only
async def get_gb_price_and_ask_for_day_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    price_text = update.message.text.strip()
    
    try:
        price_per_gb = int(price_text)
        if price_per_gb < 0: raise ValueError("Price must be non-negative.")
    except (ValueError, TypeError):
        LOGGER.warning(f"Admin {user_id} entered an invalid GB price: '{price_text}'.")
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط یک عدد مثبت یا صفر وارد کنید.")
        return AWAITING_GB_PRICE

    context.user_data['pricing']['price_per_gb'] = price_per_gb
    LOGGER.info(f"Admin {user_id} entered price_per_gb: {price_per_gb}")
    
    message_text = (
        f"✅ قیمت هر گیگابایت: `{price_per_gb:,}` تومان\n\n"
        "مرحله ۲ از ۲: لطفاً **قیمت جدید به ازای هر روز** را وارد کنید (فقط عدد و به تومان)."
    )
    await update.message.reply_text(text=message_text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_DAY_PRICE

@admin_only
async def save_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    price_text = update.message.text.strip()

    try:
        price_per_day = int(price_text)
        if price_per_day < 0: raise ValueError("Price must be non-negative.")
    except (ValueError, TypeError):
        LOGGER.warning(f"Admin {user_id} entered an invalid DAY price: '{price_text}'.")
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط یک عدد مثبت یا صفر وارد کنید.")
        return AWAITING_DAY_PRICE

    price_per_gb = context.user_data['pricing']['price_per_gb']
    
    success = await save_pricing_settings(price_per_gb, price_per_day)
    
    if success:
        LOGGER.info(f"Admin {user_id} successfully set prices: GB={price_per_gb}, DAY={price_per_day}.")
        await update.message.reply_text(
            f"✅ قیمت‌های جدید با موفقیت تنظیم شد:\n"
            f"▫️ هر گیگابایت: `{price_per_gb:,}` تومان\n"
            f"▫️ هر روز: `{price_per_day:,}` تومان",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        LOGGER.error(f"Failed to save pricing for admin {user_id}.")
        await update.message.reply_text("❌ خطایی در ذخیره اطلاعات رخ داد. لطفاً دوباره تلاش کنید.")

    context.user_data.pop('pricing', None)
    await show_financial_menu(update, context)
    return ConversationHandler.END

pricing_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^💰 تنظیم قیمت‌گذاری دلخواه$'), start_pricing_conv)],
    states={
        AWAITING_GB_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gb_price_and_ask_for_day_price)],
        AWAITING_DAY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_prices)],
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=300
)