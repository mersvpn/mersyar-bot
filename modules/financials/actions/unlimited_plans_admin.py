# FILE: modules/financials/actions/unlimited_plans_admin.py (NEW FILE)

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
    get_all_unlimited_plans,
    add_unlimited_plan,
    delete_unlimited_plan,
    get_unlimited_plan_by_id,
    update_unlimited_plan
)
from .settings import show_plan_management_menu
from shared.callbacks import cancel_conversation

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- Conversation States for Adding a New Plan ---
GET_NAME, GET_PRICE, GET_IPS, GET_SORT_ORDER, CONFIRM_ADD = range(5)

# =============================================================================
# 1. Main Menu and List Display
# =============================================================================

async def manage_unlimited_plans_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays the main menu for managing unlimited plans.
    It fetches all plans from the DB and builds an interactive list.
    """
    query = update.callback_query
    await query.answer()

    all_plans = await get_all_unlimited_plans()
    
    text = "💎 *مدیریت پلن‌های نامحدود*\n\n"
    keyboard_rows = []

    if not all_plans:
        text += "هیچ پلنی یافت نشد. برای شروع یک پلن جدید اضافه کنید."
    else:
        text += "لیست پلن‌های تعریف شده:"
        for plan in all_plans:
            status_icon = "✅" if plan['is_active'] else "❌"
            plan_text = f"{status_icon} {plan['plan_name']} - {plan['price']:,} تومان - {plan['max_ips']} کاربر"
            
            # Buttons for each plan
            plan_buttons = [
                # InlineKeyboardButton("✏️ ویرایش", callback_data=f"unlimplan_edit_{plan['id']}"), # Coming Soon
                InlineKeyboardButton("🗑 حذف", callback_data=f"unlimplan_delete_{plan['id']}"),
                InlineKeyboardButton("فعال/غیرفعال", callback_data=f"unlimplan_toggle_{plan['id']}")
            ]
            keyboard_rows.append([InlineKeyboardButton(plan_text, callback_data=f"unlimplan_noop_{plan['id']}")])
            keyboard_rows.append(plan_buttons)

    # General action buttons
    keyboard_rows.append([InlineKeyboardButton("➕ افزودن پلن جدید", callback_data="unlimplan_add_new")])
    keyboard_rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_plan_management")])
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# =============================================================================
# 2. Add New Plan Conversation
# =============================================================================

async def start_add_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to add a new unlimited plan."""
    query = update.callback_query
    await query.answer()
    context.user_data['new_unlimited_plan'] = {}
    
    text = "➕ *افزودن پلن جدید*\n\nمرحله ۱ از ۴: لطفاً **نام پلن** را وارد کنید (مثلاً: 💎 نامحدود تک کاربره).\n\nبرای لغو /cancel را ارسال کنید."
    await query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN)
    return GET_NAME

async def get_plan_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the plan name and asks for the price."""
    plan_name = update.message.text.strip()
    context.user_data['new_unlimited_plan']['name'] = plan_name
    
    text = f"✅ نام پلن: *{plan_name}*\n\nمرحله ۲ از ۴: لطفاً **قیمت پلن** را به تومان وارد کنید (فقط عدد)."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_PRICE

async def get_plan_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the price and asks for the max simultaneous users (max_ips)."""
    price_text = update.message.text.strip()
    try:
        price = int(price_text)
        if price < 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ قیمت نامعتبر است. لطفاً فقط یک عدد مثبت وارد کنید.")
        return GET_PRICE
    
    context.user_data['new_unlimited_plan']['price'] = price
    text = f"✅ قیمت: *{price:,}* تومان\n\nمرحله ۳ از ۴: لطفاً **تعداد کاربر همزمان** (تعداد دستگاه) را وارد کنید (مثلاً برای تک کاربره عدد 1)."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_IPS

async def get_max_ips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets max_ips and asks for the sort order."""
    ips_text = update.message.text.strip()
    try:
        max_ips = int(ips_text)
        if max_ips <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ تعداد کاربر نامعتبر است. لطفاً یک عدد صحیح و مثبت وارد کنید.")
        return GET_IPS
        
    context.user_data['new_unlimited_plan']['max_ips'] = max_ips
    text = f"✅ تعداد کاربر: *{max_ips}*\n\nمرحله ۴ از ۴: لطفاً **ترتیب نمایش** این پلن را وارد کنید (عدد کوچکتر = بالاتر)."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return GET_SORT_ORDER
    
async def get_sort_order_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets sort_order, shows a confirmation, and waits for final approval."""
    sort_order_text = update.message.text.strip()
    try:
        sort_order = int(sort_order_text)
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ترتیب نمایش نامعتبر است. لطفاً یک عدد وارد کنید.")
        return GET_SORT_ORDER

    context.user_data['new_unlimited_plan']['sort_order'] = sort_order
    plan_data = context.user_data['new_unlimited_plan']

    text = (
        f"📋 *تایید اطلاعات پلن جدید*\n\n"
        f"▫️ نام پلن: *{plan_data['name']}*\n"
        f"▫️ قیمت: *{plan_data['price']:,}* تومان\n"
        f"▫️ تعداد کاربر: *{plan_data['max_ips']}*\n"
        f"▫️ ترتیب نمایش: *{plan_data['sort_order']}*\n\n"
        "آیا اطلاعات فوق را تایید می‌کنید؟"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ بله، ذخیره کن", callback_data="unlimplan_confirm_add"),
            InlineKeyboardButton("❌ خیر، لغو کن", callback_data="unlimplan_cancel_add")
        ]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_ADD

async def save_new_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new plan to the DB and ends the conversation."""
    query = update.callback_query
    await query.answer("در حال ذخیره...")
    
    plan_data = context.user_data.pop('new_unlimited_plan', {})
    if not plan_data:
        await query.edit_message_text("❌ خطا: اطلاعات پلن یافت نشد.")
        return ConversationHandler.END

    await add_unlimited_plan(
        plan_name=plan_data['name'],
        price=plan_data['price'],
        max_ips=plan_data['max_ips'],
        sort_order=plan_data['sort_order']
    )
    await query.edit_message_text("✅ پلن جدید با موفقیت اضافه شد.")
    await manage_unlimited_plans_menu(update, context) # Refresh the list
    return ConversationHandler.END

async def cancel_add_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the add plan conversation."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop('new_unlimited_plan', None)
    await query.edit_message_text("عملیات افزودن پلن لغو شد.")
    await manage_unlimited_plans_menu(update, context) # Go back to the list
    return ConversationHandler.END

# =============================================================================
# 3. Handlers for Plan Actions (Delete, Toggle Status)
# =============================================================================

async def confirm_delete_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Asks for confirmation before deleting a plan."""
    query = update.callback_query
    plan_id = int(query.data.split('_')[-1])
    
    plan = await get_unlimited_plan_by_id(plan_id)
    if not plan:
        await query.answer("❌ پلن یافت نشد!", show_alert=True)
        return

    text = f"⚠️ آیا از حذف پلن '{plan['plan_name']}' مطمئن هستید؟ این عمل غیرقابل بازگشت است."
    keyboard = [
        [
            InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"unlimplan_do_delete_{plan_id}"),
            InlineKeyboardButton("❌ خیر", callback_data="admin_manage_unlimited")
        ]
    ]
    await query.answer()
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
async def execute_delete_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the plan from the DB."""
    query = update.callback_query
    plan_id = int(query.data.split('_')[-1])
    
    await query.answer("... در حال حذف")
    success = await delete_unlimited_plan(plan_id)
    
    if success:
        await query.edit_message_text("✅ پلن با موفقیت حذف شد.")
    else:
        await query.edit_message_text("❌ خطایی در حذف پلن رخ داد.")
        
    await manage_unlimited_plans_menu(update, context)

async def toggle_plan_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles the is_active status of a plan."""
    query = update.callback_query
    plan_id = int(query.data.split('_')[-1])
    
    await query.answer("... در حال تغییر وضعیت")
    plan = await get_unlimited_plan_by_id(plan_id)
    if not plan:
        await query.answer("❌ پلن یافت نشد!", show_alert=True)
        return
        
    # Toggle the status
    new_status = not plan['is_active']
    
    await update_unlimited_plan(
        plan_id=plan_id,
        plan_name=plan['plan_name'],
        price=plan['price'],
        max_ips=plan['max_ips'],
        is_active=new_status,
        sort_order=plan['sort_order']
    )
    
    await manage_unlimited_plans_menu(update, context)

# =============================================================================
# 4. Conversation Handler Definition
# =============================================================================

add_unlimited_plan_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_plan, pattern='^unlimplan_add_new$')],
    states={
        GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plan_name)],
        GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plan_price)],
        GET_IPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_max_ips)],
        GET_SORT_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sort_order_and_confirm)],
        CONFIRM_ADD: [
            CallbackQueryHandler(save_new_plan, pattern='^unlimplan_confirm_add$'),
            CallbackQueryHandler(cancel_add_plan, pattern='^unlimplan_cancel_add$')
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)], # A generic cancel handler
    conversation_timeout=600
)