# FILE: modules/financials/actions/settings.py (نسخه بازطراحی شده با پنل مدیریت پلن)

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
from database.db_manager import load_financials, save_financials
# --- MODIFIED: Updated keyboard imports and removed unused ones ---
from shared.keyboards import get_financial_settings_keyboard, get_payment_methods_keyboard, get_plan_management_keyboard
from shared.callbacks import cancel_conversation
from modules.auth import admin_only
from database.db_manager import load_financials, save_financials, load_bot_settings, save_bot_settings

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- States for Conversations ---
# States for the card info conversation
(
    CARD_MENU,
    EDITING_HOLDER,
    EDITING_CARD
) = range(3)

# States for the plan name settings conversation (NEW)
(
    PLAN_NAME_MENU,
    EDITING_VOLUMETRIC_NAME,
    EDITING_UNLIMITED_NAME
) = range(3, 6)

# =============================================================================
# 1. توابع منوهای اصلی مالی
# =============================================================================

@admin_only
async def show_financial_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    منوی اصلی تنظیمات مالی را نمایش می‌دهد.
    """
    user_id = update.effective_user.id
    LOGGER.info(f"Admin {user_id} accessed the main financial menu.")
    
    text = "💰 *تنظیمات مالی*\n\nلطفا بخش مورد نظر خود را انتخاب کنید:"
    keyboard = get_financial_settings_keyboard()

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        # To avoid TelegramError: MESSAGE_NOT_MODIFIED, check if the message is the same
        if query.message.text != "به منوی تنظیمات مالی بازگشتید.":
            await query.edit_message_text(text="به منوی تنظیمات مالی بازگشتید.")
        
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

@admin_only
async def show_payment_methods_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    LOGGER.info(f"Admin {user_id} accessed the payment methods submenu.")
    text = "💳 *تنظیمات پرداخت*\n\nاز این بخش می‌توانید روش‌های پرداخت را مدیریت کنید."
    keyboard = get_payment_methods_keyboard()
    
    # Check if triggered by a ReplyKeyboardButton or an InlineKeyboardButton
    target_message = update.message or (update.callback_query.message if update.callback_query else None)
    if not target_message: return

    # If it's a callback, we can edit the message
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        # If it's a regular message, we send a new message with the inline keyboard
        await target_message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# --- NEW FUNCTION ---
@admin_only
async def show_plan_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays the plan management menu (Unlimited / Volumetric).
    Handles both message and callback query triggers intelligently.
    """
    user_id = update.effective_user.id
    LOGGER.info(f"Admin {user_id} accessed the plan management menu.")
    
    text = "📊 *مدیریت پلن‌های فروش*\n\nلطفا نوع پلن‌هایی که قصد مدیریت آن‌ها را دارید، انتخاب کنید:"
    keyboard = get_plan_management_keyboard()
    
    if update.callback_query:
        # If triggered by an inline button (like "Back"), edit the message.
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # If triggered by a message (ReplyKeyboardButton), send a new message.
        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
# =============================================================================
# 2. مکالمه تنظیم اطلاعات کارت به کارت (بدون تغییر)
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
        return CARD_MENU
    prompt_text, next_state = prompt_map[action]
    await query.edit_message_text(text=prompt_text)
    return next_state

async def save_financial_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    action = context.user_data.get('financial_action')
    new_value = update.message.text.strip()
    user_id = update.effective_user.id
    if not action:
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
            await update.message.reply_text("❌ شماره کارت نامعتبر است. باید ۱۶ رقم باشد. لطفاً دوباره وارد کنید.")
            return EDITING_CARD
        financial_data['card_number'] = card_number
        confirmation_text = "✅ شماره کارت با موفقیت به‌روز شد."
    await save_financials(financial_data)
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
# 3. مکالمه تنظیم نام پلن‌های فروش (NEW SECTION)
# =============================================================================

async def show_plan_name_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the menu for editing plan button names."""
    query = update.callback_query
    await query.answer()

    settings = await load_bot_settings()
    vol_name = settings.get("volumetric_plan_button_text", "📊 پلن حجمی")
    unl_name = settings.get("unlimited_plan_button_text", "💎 پلن نامحدود")

    text = (
        "✏️ *تنظیم نام پلن‌ها*\n\n"
        "از این بخش می‌توانید نام دکمه‌هایی که به مشتری نمایش داده می‌شود را تغییر دهید.\n\n"
        f"▫️ نام فعلی پلن حجمی: `{vol_name}`\n"
        f"▫️ نام فعلی پلن نامحدود: `{unl_name}`"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 ویرایش نام پلن حجمی", callback_data="set_name_volumetric"),
            InlineKeyboardButton("💎 ویرایش نام پلن نامحدود", callback_data="set_name_unlimited")
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_plan_management")]
    ]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    return PLAN_NAME_MENU

async def prompt_for_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin to enter the new name for the selected button."""
    query = update.callback_query
    action = query.data.split('_')[-1] # 'volumetric' or 'unlimited'
    context.user_data['plan_name_to_edit'] = action
    
    if action == 'volumetric':
        prompt_text = "لطفاً نام جدید دکمه **پلن حجمی** را وارد کنید (می‌توانید از ایموجی هم استفاده کنید):"
        next_state = EDITING_VOLUMETRIC_NAME
    else:
        prompt_text = "لطفاً نام جدید دکمه **پلن نامحدود** را وارد کنید (می‌توانید از ایموجی هم استفاده کنید):"
        next_state = EDITING_UNLIMITED_NAME
        
    await query.answer()
    await query.edit_message_text(text=prompt_text, parse_mode=ParseMode.MARKDOWN)
    return next_state

async def save_new_plan_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new button name and cleanly exits the conversation."""
    new_name = update.message.text.strip()
    action = context.user_data.pop('plan_name_to_edit', None)

    if not action:
        await update.message.reply_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        return await cancel_conversation(update, context)

    if action == 'volumetric':
        key_to_save = "volumetric_plan_button_text"
    else:
        key_to_save = "unlimited_plan_button_text"

    await save_bot_settings({key_to_save: new_name})
    
    await update.message.reply_text(f"✅ نام دکمه با موفقیت به «{new_name}» تغییر یافت.")
    
    # --- FIX: Re-create and send the previous menu manually to ensure a clean exit ---
    menu_text = "📊 *مدیریت پلن‌های فروش*\n\nلطفا نوع پلن‌هایی که قصد مدیریت آن‌ها را دارید، انتخاب کنید:"
    menu_keyboard = get_plan_management_keyboard()
    
    await update.message.reply_text(
        text=menu_text,
        reply_markup=menu_keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    return ConversationHandler.END
plan_name_settings_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(show_plan_name_settings_menu, pattern='^admin_set_plan_names$')],
    states={
        PLAN_NAME_MENU: [
            CallbackQueryHandler(prompt_for_new_name, pattern=r'^set_name_'),
            CallbackQueryHandler(show_plan_management_menu, pattern=r'^back_to_plan_management$')
        ],
        EDITING_VOLUMETRIC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_plan_name)],
        EDITING_UNLIMITED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_plan_name)],
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=300
)