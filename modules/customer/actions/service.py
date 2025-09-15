# FILE: modules/customer/actions/service.py (REVISED FOR PAGINATION)

import datetime
import jdatetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import config
from shared.keyboards import get_customer_main_menu_keyboard, get_admin_main_menu_keyboard
from modules.marzban.actions.api import get_user_data, reset_subscription_url_api, get_all_users
from modules.marzban.actions.constants import GB_IN_BYTES
from modules.marzban.actions.data_manager import normalize_username
from database.db_manager import load_pricing_parameters, create_pending_invoice
from modules.financials.actions.payment import send_custom_plan_invoice
from shared.keyboards import get_back_to_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

CHOOSE_SERVICE, DISPLAY_SERVICE, CONFIRM_RESET_SUB, CONFIRM_DELETE = range(4)
PROMPT_FOR_DATA_AMOUNT, CONFIRM_DATA_PURCHASE = range(4, 6)
ITEMS_PER_PAGE = 8

# =============================================================================
#  بخش جدید: توابع کمکی برای صفحه‌بندی
# =============================================================================
async def _build_paginated_service_keyboard(services: list, page: int = 0) -> InlineKeyboardMarkup:
    """یک کیبورد صفحه‌بندی شده از سرویس‌ها می‌سازد."""
    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    
    keyboard = []
    
    # Add service buttons for the current page
    for user in services[start_index:end_index]:
        status_emoji = "🟢" if user.get('status') == 'active' else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} سرویس: {user['username']}", 
                callback_data=f"select_service_{user['username']}"
            )
        ])
        
    # Add navigation buttons
    nav_buttons = []
    total_pages = (len(services) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"page_back_{page-1}"))
    
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"صفحه {page + 1}/{total_pages}", callback_data="noop")) # No operation

    if end_index < len(services):
        nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"page_fwd_{page+1}"))
        
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="customer_back_to_main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def handle_service_page_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles clicks on 'next' and 'previous' buttons."""
    query = update.callback_query
    await query.answer()

    direction, page_str = query.data.split('_')[1:]
    page = int(page_str)

    services = context.user_data.get('services_list', [])
    if not services:
        await query.edit_message_text("خطا: لیست سرویس‌ها یافت نشد. لطفاً دوباره امتحان کنید.")
        return ConversationHandler.END

    reply_markup = await _build_paginated_service_keyboard(services, page)
    await query.edit_message_text(
        "شما چندین سرویس دارید. لطفاً یکی را برای مشاهده جزئیات انتخاب کنید:", 
        reply_markup=reply_markup
    )
    return CHOOSE_SERVICE

# =============================================================================
#  توابع اصلی (با تغییرات)
# =============================================================================

async def display_service_details(update: Update, context: ContextTypes.DEFAULT_TYPE, marzban_username: str) -> int:
    from database.db_manager import get_user_note
    
    target_message = update.callback_query.message if update.callback_query else update.message
    
    await context.bot.edit_message_text(
        chat_id=target_message.chat_id,
        message_id=target_message.message_id,
        text=f"در حال دریافت اطلاعات سرویس «{marzban_username}»..."
    )

    user_info = await get_user_data(marzban_username)
    if not user_info or "error" in user_info:
        await target_message.edit_text("❌ خطا: این سرویس در پنل یافت نشد.")
        return ConversationHandler.END

    is_active = user_info.get('status') == 'active'

    if is_active:
        usage_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
        limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
        usage_str = f"{usage_gb:.2f} GB" + (f" / {limit_gb:.0f} GB" if limit_gb > 0 else " (از نامحدود)")

        expire_str = "نامحدود"
        duration_str = "نامشخص"

        note_data = await get_user_note(normalize_username(marzban_username))
        if note_data and note_data.get('subscription_duration'):
            duration_str = f"{note_data['subscription_duration']} روزه"

        if user_info.get('expire'):
            expire_date = datetime.datetime.fromtimestamp(user_info['expire'])
            if (expire_date - datetime.datetime.now()).total_seconds() > 0:
                jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_date)
                time_left = expire_date - datetime.datetime.now()
                expire_str = f"{jalali_date.strftime('%Y/%m/%d')} ({time_left.days} روز باقی‌مانده)"
            else:
                is_active = False 
                expire_str = "منقضی شده"
        
        sub_url = user_info.get('subscription_url', 'یافت نشد')
        message = (
            f"📊 **مشخصات سرویس**\n\n"
            f"👤 **نام کاربری:** `{marzban_username}`\n"
            f"🟢 **وضعیت:** فعال\n"
            f"📶 **حجم:** {usage_str}\n"
            f"▫️ **طول دوره:** {duration_str}\n"
            f"⏳ **انقضا:** `{expire_str}`\n\n"
            f"🔗 **لینک اشتراک** (برای کپی کلیک کنید):\n`{sub_url}`"
        )
        
        # V V V V V MODIFY THIS KEYBOARD V V V V V
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💳 درخواست تمدید", callback_data=f"customer_renew_request_{marzban_username}"),
                InlineKeyboardButton("➕ خرید حجم اضافه", callback_data=f"purchase_data_{marzban_username}")
            ],
            [
                InlineKeyboardButton("🔗 بازسازی لینک", callback_data=f"customer_reset_sub_{marzban_username}"),
                InlineKeyboardButton("🗑 درخواست حذف", callback_data=f"request_delete_{marzban_username}")
            ],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="customer_back_to_main_menu")]
        ])
        # ^ ^ ^ ^ ^ MODIFY THIS KEYBOARD ^ ^ ^ ^ ^
    
    if not is_active:
        message = (
            f"⚠️ **وضعیت سرویس**\n\n"
            f"▫️ **نام کاربری:** `{marzban_username}`\n"
            f"▫️ **وضعیت:** 🔴 غیرفعال / منقضی شده\n\n"
            "برای استفاده مجدد از این سرویس، لطفاً آن را تمدید کنید."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 تمدید این سرویس", callback_data=f"customer_renew_request_{marzban_username}")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="customer_back_to_main_menu")]
        ])

    await target_message.edit_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return DISPLAY_SERVICE
    
async def handle_my_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import get_linked_marzban_usernames, unlink_user_from_telegram
    
    user_id = update.effective_user.id
    loading_message = await update.message.reply_text("در حال بررسی سرویس‌های شما...")

    linked_usernames_raw = await get_linked_marzban_usernames(user_id)
    if not linked_usernames_raw:
        await loading_message.edit_text("سرویسی به حساب تلگرام شما متصل نیست.")
        return ConversationHandler.END

    all_marzban_users_list = await get_all_users()
    if all_marzban_users_list is None:
        await loading_message.edit_text("❌ خطا در ارتباط با پنل. لطفاً بعداً تلاش کنید.")
        return ConversationHandler.END
        
    marzban_usernames_set = {normalize_username(u['username']) for u in all_marzban_users_list if u.get('username')}
    all_marzban_users_dict = {normalize_username(u['username']): u for u in all_marzban_users_list if u.get('username')}

    valid_linked_accounts = []
    dead_links_to_cleanup = []

    for username_raw in linked_usernames_raw:
        normalized = normalize_username(username_raw)
        if normalized in marzban_usernames_set:
            valid_linked_accounts.append(all_marzban_users_dict[normalized])
        else:
            dead_links_to_cleanup.append(normalized)

    if dead_links_to_cleanup:
        LOGGER.info(f"Cleaning up {len(dead_links_to_cleanup)} dead links for user {user_id}: {dead_links_to_cleanup}")
        for dead_username in dead_links_to_cleanup:
            await unlink_user_from_telegram(dead_username)

    if not valid_linked_accounts:
        await loading_message.edit_text(
            "هیچ سرویسی برای شما یافت نشد. اگر قبلاً سرویس داشته‌اید، ممکن است توسط ادمین حذف شده باشد."
        )
        return ConversationHandler.END

    if len(valid_linked_accounts) == 1:
        class DummyQuery:
            def __init__(self, message): self.message = message
        dummy_update = type('obj', (object,), {'callback_query': DummyQuery(loading_message)})
        original_username = valid_linked_accounts[0]['username']
        return await display_service_details(dummy_update, context, original_username)

    # --- REVISED FOR PAGINATION ---
    sorted_services = sorted(valid_linked_accounts, key=lambda u: u['username'].lower())
    context.user_data['services_list'] = sorted_services

    reply_markup = await _build_paginated_service_keyboard(sorted_services, page=0)
    
    await loading_message.edit_text("شما چندین سرویس دارید. لطفاً یکی را برای مشاهده جزئیات انتخاب کنید:", reply_markup=reply_markup)
    return CHOOSE_SERVICE

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    marzban_username = query.data.split('select_service_')[-1]
    return await display_service_details(update, context, marzban_username)

# ... (بقیه توابع بدون تغییر باقی می‌مانند)
async def confirm_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    context.user_data['service_username'] = username
    text = "⚠️ **اخطار** ⚠️\n\nبا بازسازی لینک، **لینک قبلی از کار خواهد افتاد**.\n\nآیا مطمئن هستید؟"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، بازسازی کن", callback_data=f"do_reset_sub_{username}")],
        [InlineKeyboardButton("❌ خیر، بازگرد", callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_RESET_SUB

async def execute_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    if not username:
        await query.edit_message_text("خطا: نام کاربری یافت نشد.")
        return ConversationHandler.END

    await query.edit_message_text(f"در حال بازسازی لینک برای `{username}`...")
    success, result = await reset_subscription_url_api(username)

    if success:
        new_sub_url = result.get('subscription_url', 'خطا در دریافت لینک')
        text = f"✅ لینک بازسازی شد:\n\n`{new_sub_url}`"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        text = f"❌ خطا در بازسازی: {result}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard) # edit the same message on failure
    return DISPLAY_SERVICE

async def back_to_main_menu_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id in config.AUTHORIZED_USER_IDS:
        final_keyboard = get_admin_main_menu_keyboard()
        message_text = "به منوی اصلی ادمین بازگشتید."
    else:
        final_keyboard = get_customer_main_menu_keyboard()
        message_text = "به منوی اصلی بازگشتید."

    await query.message.delete()
    await context.bot.send_message(
        chat_id=user_id,
        text=message_text,
        reply_markup=final_keyboard
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def request_delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    text = (
        f"⚠️ **اخطار: این عمل غیرقابل بازگشت است.** ⚠️\n\n"
        f"آیا از درخواست حذف کامل سرویس `{username}` اطمینان دارید؟"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، درخواست حذف ارسال شود", callback_data=f"confirm_delete_{username}")],
        [InlineKeyboardButton("❌ خیر، منصرف شدم", callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DELETE

async def confirm_delete_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from config import config
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    user = update.effective_user
    await query.edit_message_text(
        "✅ درخواست شما برای حذف سرویس با موفقیت برای ادمین ارسال شد.\n"
        "لطفاً منتظر بمانید."
    )
    if config.AUTHORIZED_USER_IDS:
        user_info = f"کاربر {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\nUser ID: `{user.id}`"
        message_to_admin = (
            f"🗑️ **درخواست حذف سرویس** 🗑️\n\n"
            f"{user_info}\n"
            f"نام کاربری در پنل: `{username}`\n\n"
            "این کاربر درخواست حذف کامل این سرویس را دارد."
        )
        
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید حذف", callback_data=f"delete_{username}")],
        ])

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_to_admin,
                    reply_markup=admin_keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send delete request to admin {admin_id} for {username}: {e}", exc_info=True)
    return ConversationHandler.END


# REPLACE THE ENTIRE `start_data_purchase` FUNCTION WITH THIS VERSION
async def start_data_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the 'purchase additional data' conversation."""
    query = update.callback_query
    await query.answer()
    
    marzban_username = query.data.split('purchase_data_')[-1]
    context.user_data['purchase_data_username'] = marzban_username
    
    pricing_params = await load_pricing_parameters()
    if not pricing_params.get("tiers"):
        await query.edit_message_text(
            "⚠️ متاسفانه امکان خرید حجم اضافه در حال حاضر وجود ندارد (پیکربندی نشده)."
        )
        # We don't return to the same state, instead we let the user see the message
        # and they can navigate back manually.
        return ConversationHandler.END

    text = (
        f"➕ **خرید حجم اضافه برای سرویس:** `{marzban_username}`\n\n"
        "لطفاً مقدار حجم مورد نیاز خود را به **گیگابایت (GB)** وارد کنید (مثلاً: 10).\n\n"
        "برای انصراف، از دکمه زیر استفاده کنید."
    )
    
    # Delete the previous message (service details)
    await query.message.delete()
    
    # Send a new message with the prompt and a "Back" ReplyKeyboard
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return PROMPT_FOR_DATA_AMOUNT

async def calculate_price_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calculates the price for the requested data and asks for confirmation."""
    try:
        volume_gb = int(update.message.text.strip())
        if volume_gb <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فقط یک عدد صحیح و مثبت وارد کنید.")
        return PROMPT_FOR_DATA_AMOUNT

    pricing_params = await load_pricing_parameters()
    tiers = sorted(pricing_params.get("tiers", []), key=lambda x: x['volume_limit_gb'])
    
    price_per_gb = 0
    if tiers:
        # Find the correct price tier for the requested volume
        for tier in tiers:
            if volume_gb <= tier['volume_limit_gb']:
                price_per_gb = tier['price_per_gb']
                break
        # If volume is larger than the largest tier, use the price of the largest tier
        if price_per_gb == 0:
            price_per_gb = tiers[-1]['price_per_gb']
    
    if price_per_gb == 0:
        await update.message.reply_text("❌ خطایی در سیستم قیمت‌گذاری رخ داد. لطفاً با پشتیبانی تماس بگیرید.")
        return ConversationHandler.END

    total_price = volume_gb * price_per_gb
    username = context.user_data.get('purchase_data_username')
    
    context.user_data['purchase_data_details'] = {
        "volume": volume_gb,
        "price": total_price,
        "plan_type": "data_top_up",
        "username": username
    }

    text = (
        f"🧾 **پیش‌فاکتور خرید حجم اضافه**\n\n"
        f"▫️ **سرویس:** `{username}`\n"
        f"▫️ **حجم درخواستی:** {volume_gb} گیگابایت\n"
        f"-------------------------------------\n"
        f"💳 **مبلغ قابل پرداخت:** {total_price:,.0f} تومان\n\n"
        "آیا اطلاعات فوق را تایید می‌کنید؟"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و دریافت فاکتور", callback_data="confirm_data_purchase_final")],
        [InlineKeyboardButton("❌ لغو", callback_data=f"select_service_{username}")] # Back to details
    ])
    
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DATA_PURCHASE


async def generate_data_purchase_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates a pending invoice for the data purchase and ends the conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("... در حال صدور فاکتور")
    
    user_id = query.from_user.id
    purchase_details = context.user_data.get('purchase_data_details')
    
    if not purchase_details:
        await query.edit_message_text("❌ خطایی رخ داد. اطلاعات خرید یافت نشد.")
        return ConversationHandler.END

    price = purchase_details.get('price')
    invoice_id = await create_pending_invoice(user_id, purchase_details, price)
    
    if not invoice_id:
        await query.edit_message_text("❌ خطایی در سیستم رخ داد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
        
    await query.message.delete()
    
    # We can reuse the invoice sending function
    invoice_display_details = {
        "volume": f"+{purchase_details['volume']} GB",
        "duration": "حجم اضافه",
        "price": price
    }
    await send_custom_plan_invoice(update, context, invoice_display_details, invoice_id)
    
    context.user_data.clear()
    return ConversationHandler.END