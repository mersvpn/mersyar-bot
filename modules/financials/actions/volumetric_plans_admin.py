# FILE: modules/financials/actions/volumetric_plans_admin.py (NEW FILE)

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

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
from database.db_manager import (
    load_pricing_parameters,
    save_base_daily_price,
    add_pricing_tier,
    delete_pricing_tier,
    get_pricing_tier_by_id,
    update_pricing_tier  # <-- This function is now imported
)
from .settings import show_plan_management_menu
from shared.callbacks import cancel_conversation
# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
GET_BASE_PRICE = 0
GET_TIER_NAME, GET_TIER_LIMIT, GET_TIER_PRICE, CONFIRM_TIER_ADD = range(1, 5)

# =============================================================================
# 1. Main Menu and Display Logic
# =============================================================================

async def manage_volumetric_plans_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays the main menu for managing volumetric pricing parameters with a two-row-per-item layout.
    """
    query = update.callback_query
    await query.answer()

    pricing_params = await load_pricing_parameters()
    base_price = pricing_params.get('base_daily_price')
    tiers = pricing_params.get('tiers', [])

    text = "💡 *مدیریت پلن‌های حجمی*\n\n"
    keyboard_rows = []

    # --- Section 1: Base Price ---
    base_price_str = f"`{base_price:,}` تومان" if base_price is not None else "`تنظیم نشده`"
    text += f"⚙️ *هزینه پایه:*\nروزانه: {base_price_str}\n\n"
    keyboard_rows.append(
        [InlineKeyboardButton("✏️ ویرایش قیمت پایه روزانه", callback_data="vol_edit_base_price")]
    )
    keyboard_rows.append(
        [InlineKeyboardButton(" ", callback_data="noop")] # Visual spacer
    )

    # --- Section 2: Pricing Tiers ---
    text += "梯 *پلکان‌های قیمتی:*"
    if not tiers:
        text += "\n_هیچ پلکانی تعریف نشده است._"
    else:
        for tier in tiers:
            tier_text = f"📊 تا {tier['volume_limit_gb']} گیگ: {tier['price_per_gb']:,} تومان/گیگ"
            keyboard_rows.append([
                InlineKeyboardButton(tier_text, callback_data=f"vol_noop_{tier['id']}")
            ])
            
            action_buttons = [
                # --- MODIFIED: Activated the edit button ---
                InlineKeyboardButton("✏️ ویرایش", callback_data=f"vol_edit_tier_{tier['id']}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"vol_delete_tier_{tier['id']}")
            ]
            keyboard_rows.append(action_buttons)
    
    # --- Section 3: General Actions ---
    keyboard_rows.append(
        [InlineKeyboardButton(" ", callback_data="noop")] # Another visual spacer
    )
    keyboard_rows.append([InlineKeyboardButton("➕ افزودن پلکان جدید", callback_data="vol_add_tier")])
    keyboard_rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_plan_management")])
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
# =============================================================================
# 2. Edit Base Daily Price Conversation
# =============================================================================

async def prompt_for_base_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = "✏️ لطفاً **هزینه پایه روزانه** جدید را به تومان وارد کنید (فقط عدد)."
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_BASE_PRICE

async def save_new_base_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    price_text = update.message.text.strip()
    try:
        price = int(price_text)
        if price < 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فقط یک عدد مثبت وارد کنید.")
        return GET_BASE_PRICE
    
    await save_base_daily_price(price)
    await update.message.reply_text(f"✅ هزینه پایه روزانه با موفقیت به `{price:,}` تومان تغییر کرد.")
    
    # Create a dummy query to refresh the main menu
    dummy_query = type('Query', (), {'answer': (lambda: None), 'edit_message_text': update.message.reply_text})()
    dummy_update = type('Update', (), {'callback_query': dummy_query})()
    await manage_volumetric_plans_menu(dummy_update, context)

    return ConversationHandler.END

# =============================================================================
# 3. Add New Pricing Tier Conversation
# =============================================================================

async def start_add_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['new_tier'] = {}
    text = "➕ *افزودن پلکان جدید*\n\nمرحله ۱ از ۳: لطفاً **نام پلکان** را وارد کنید (مثلاً: پلن پایه)."
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_TIER_NAME

async def get_tier_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_tier']['name'] = update.message.text.strip()
    text = "مرحله ۲ از ۳: **سقف حجم (GB)** این پلکان را وارد کنید (مثلاً `30`)."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_TIER_LIMIT

async def get_tier_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    limit_text = update.message.text.strip()
    try:
        limit = int(limit_text)
        if limit <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ سقف حجم نامعتبر. لطفاً یک عدد صحیح و مثبت وارد کنید.")
        return GET_TIER_LIMIT
    
    context.user_data['new_tier']['limit'] = limit
    text = "مرحله ۳ از ۳: **قیمت به ازای هر گیگابایت** در این پلکان را به تومان وارد کنید."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_TIER_PRICE

async def get_tier_price_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    price_text = update.message.text.strip()
    try:
        price = int(price_text)
        if price < 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ قیمت نامعتبر. لطفاً یک عدد مثبت وارد کنید.")
        return GET_TIER_PRICE

    context.user_data['new_tier']['price'] = price
    tier_data = context.user_data['new_tier']

    text = (
        f"📋 *تایید اطلاعات پلکان جدید*\n\n"
        f"▫️ نام: *{tier_data['name']}*\n"
        f"▫️ تا سقف: *{tier_data['limit']}* گیگابایت\n"
        f"▫️ قیمت هر گیگ: *{tier_data['price']:,}* تومان\n\n"
        "آیا اطلاعات فوق را تایید می‌کنید؟"
    )
    keyboard = [[
        InlineKeyboardButton("✅ بله، ذخیره کن", callback_data="vol_confirm_add"),
        InlineKeyboardButton("❌ خیر، لغو کن", callback_data="vol_cancel_add")
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_TIER_ADD

async def save_new_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("در حال ذخیره...")
    tier_data = context.user_data.pop('new_tier', {})
    
    await add_pricing_tier(
        tier_name=tier_data['name'],
        volume_limit_gb=tier_data['limit'],
        price_per_gb=tier_data['price']
    )
    await query.edit_message_text("✅ پلکان جدید با موفقیت اضافه شد.")
    await manage_volumetric_plans_menu(update, context)
    return ConversationHandler.END

async def cancel_add_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop('new_tier', None)
    await query.edit_message_text("عملیات افزودن پلکان لغو شد.")
    await manage_volumetric_plans_menu(update, context)
    return ConversationHandler.END

# =============================================================================
# 4. Delete Tier Handlers
# =============================================================================

async def confirm_delete_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tier_id = int(query.data.split('_')[-1])
    tier = await get_pricing_tier_by_id(tier_id)
    if not tier:
        await query.answer("❌ پلکان یافت نشد!", show_alert=True)
        return

    text = f"⚠️ آیا از حذف پلکان '{tier['tier_name']}' مطمئن هستید؟"
    keyboard = [[
        InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"vol_do_delete_tier_{tier_id}"),
        InlineKeyboardButton("❌ خیر", callback_data="admin_manage_volumetric")
    ]]
    await query.answer()
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # =============================================================================
# 4. Edit Pricing Tier Conversation (NEW SECTION)
# =============================================================================

# Define new states for the edit conversation to avoid conflicts
EDIT_TIER_NAME, EDIT_TIER_LIMIT, EDIT_TIER_PRICE, CONFIRM_TIER_EDIT = range(5, 9)

async def start_edit_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to edit an existing pricing tier."""
    query = update.callback_query
    tier_id = int(query.data.split('_')[-1])
    
    tier = await get_pricing_tier_by_id(tier_id)
    if not tier:
        await query.answer("❌ پلکان یافت نشد!", show_alert=True)
        return ConversationHandler.END

    context.user_data['edit_tier'] = tier
    
    await query.answer()
    text = (
        f"✏️ *ویرایش پلکان: {tier['tier_name']}*\n\n"
        f"مقدار فعلی: `{tier['tier_name']}`\n\n"
        "مرحله ۱ از ۳: لطفاً **نام جدید** را وارد کنید (یا برای رد شدن /skip را ارسال کنید)."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return EDIT_TIER_NAME

async def get_new_tier_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the new name or skips, then asks for the new volume limit."""
    new_name = update.message.text.strip()
    if new_name.lower() != '/skip':
        context.user_data['edit_tier']['tier_name'] = new_name
    
    tier = context.user_data['edit_tier']
    text = (
        f"مقدار فعلی: `{tier['volume_limit_gb']}` گیگابایت\n\n"
        "مرحله ۲ از ۳: لطفاً **سقف حجم (GB) جدید** را وارد کنید (یا برای رد شدن /skip)."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return EDIT_TIER_LIMIT

async def get_new_tier_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the new volume limit or skips, then asks for the new price."""
    new_limit_text = update.message.text.strip()
    if new_limit_text.lower() != '/skip':
        try:
            new_limit = int(new_limit_text)
            if new_limit <= 0: raise ValueError
            context.user_data['edit_tier']['volume_limit_gb'] = new_limit
        except (ValueError, TypeError):
            await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح و مثبت وارد کنید.")
            return EDIT_TIER_LIMIT
            
    tier = context.user_data['edit_tier']
    text = (
        f"مقدار فعلی: `{tier['price_per_gb']:,}` تومان\n\n"
        "مرحله ۳ از ۳: لطفاً **قیمت جدید به ازای هر گیگ** را وارد کنید (یا برای رد شدن /skip)."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return EDIT_TIER_PRICE

async def get_new_tier_price_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the new price or skips, then shows the final confirmation."""
    new_price_text = update.message.text.strip()
    if new_price_text.lower() != '/skip':
        try:
            new_price = int(new_price_text)
            if new_price < 0: raise ValueError
            context.user_data['edit_tier']['price_per_gb'] = new_price
        except (ValueError, TypeError):
            await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد مثبت وارد کنید.")
            return EDIT_TIER_PRICE

    tier_data = context.user_data['edit_tier']
    text = (
        f"📋 *تایید اطلاعات ویرایش شده*\n\n"
        f"▫️ نام: *{tier_data['tier_name']}*\n"
        f"▫️ سقف حجم: *{tier_data['volume_limit_gb']}* گیگابایت\n"
        f"▫️ قیمت هر گیگ: *{tier_data['price_per_gb']:,}* تومان\n\n"
        "آیا تغییرات را تایید می‌کنید؟"
    )
    keyboard = [[
        InlineKeyboardButton("✅ بله، ذخیره کن", callback_data="vol_confirm_edit"),
        InlineKeyboardButton("❌ خیر، لغو کن", callback_data="vol_cancel_edit")
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_TIER_EDIT

async def save_edited_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the edited tier to the DB."""
    query = update.callback_query
    await query.answer("در حال ذخیره تغییرات...")
    tier_data = context.user_data.pop('edit_tier', {})
    
    if not tier_data:
        await query.edit_message_text("❌ خطا: اطلاعات پلکان یافت نشد.")
        return ConversationHandler.END

    await update_pricing_tier(
        tier_id=tier_data['id'],
        tier_name=tier_data['tier_name'],
        volume_limit_gb=tier_data['volume_limit_gb'],
        price_per_gb=tier_data['price_per_gb']
    )
    await query.edit_message_text("✅ پلکان با موفقیت ویرایش شد.")
    await manage_volumetric_plans_menu(update, context)
    return ConversationHandler.END

async def cancel_edit_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the edit tier conversation."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop('edit_tier', None)
    await query.edit_message_text("عملیات ویرایش پلکان لغو شد.")
    await manage_volumetric_plans_menu(update, context)
    return ConversationHandler.END

# =============================================================================
# Renumber the section below to 5, and add the new ConversationHandler
# =============================================================================

async def execute_delete_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tier_id = int(query.data.split('_')[-1])
    await query.answer("... در حال حذف")
    await delete_pricing_tier(tier_id)
    await query.edit_message_text("✅ پلکان با موفقیت حذف شد.")
    await manage_volumetric_plans_menu(update, context)

# =============================================================================
# 5. Conversation Handler Definitions
# =============================================================================

edit_base_price_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_for_base_price, pattern='^vol_edit_base_price$')],
    states={GET_BASE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_base_price)]},
    fallbacks=[CommandHandler('cancel', cancel_conversation)]
)

add_tier_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_tier, pattern='^vol_add_tier$')],
    states={
        GET_TIER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tier_name)],
        GET_TIER_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tier_limit)],
        GET_TIER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tier_price_and_confirm)],
        CONFIRM_TIER_ADD: [
            CallbackQueryHandler(save_new_tier, pattern='^vol_confirm_add$'),
            CallbackQueryHandler(cancel_add_tier, pattern='^vol_cancel_add$')
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=600
)

edit_tier_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_tier, pattern=r'^vol_edit_tier_')],
    states={
        EDIT_TIER_NAME: [
            CommandHandler('skip', get_new_tier_name),
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_tier_name)
        ],
        EDIT_TIER_LIMIT: [
            CommandHandler('skip', get_new_tier_limit),
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_tier_limit)
        ],
        EDIT_TIER_PRICE: [
            CommandHandler('skip', get_new_tier_price_and_confirm),
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_tier_price_and_confirm)
        ],
        CONFIRM_TIER_EDIT: [
            CallbackQueryHandler(save_edited_tier, pattern='^vol_confirm_edit$'),
            CallbackQueryHandler(cancel_edit_tier, pattern='^vol_cancel_edit$')
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=600
)