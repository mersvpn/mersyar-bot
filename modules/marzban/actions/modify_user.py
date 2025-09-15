# FILE: modules/marzban/actions/modify_user.py (نسخه نهایی، کاملاً صحیح و بازبینی شده)

import datetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from shared.log_channel import send_log
from telegram.helpers import escape_markdown
from shared.keyboards import get_back_to_main_menu_keyboard

from .display import show_user_details_panel
from .constants import GB_IN_BYTES, DEFAULT_RENEW_DAYS
from .data_manager import normalize_username
from .api import (
    get_user_data, modify_user_api, delete_user_api,
    reset_user_traffic_api
)

LOGGER = logging.getLogger(__name__)

ADD_DAYS_PROMPT, ADD_DATA_PROMPT = range(2)

async def prompt_for_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    username = query.data.removeprefix('add_days_')

    context.user_data['modify_user_info'] = {
        'username': username,
        'chat_id': query.message.chat_id,
        'message_id': query.message.message_id,
        'list_type': context.user_data.get('current_list_type', 'all'),
        'page_number': context.user_data.get('current_page', 1)
    }
    await query.answer()
    
    text = (f"🗓️ لطفاً تعداد روزهایی که می‌خواهید به اشتراک کاربر `{username}` اضافه شود را وارد کنید.\n\n"
            "برای انصراف، از دکمه زیر استفاده کنید.")
    
    # --- CHANGE IS HERE ---
    # Delete the old inline keyboard message
    await query.message.delete()
    # Send a new message with the ReplyKeyboardMarkup
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    # --- END OF CHANGE ---

    return ADD_DAYS_PROMPT

async def prompt_for_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    username = query.data.removeprefix('add_data_')
        
    context.user_data['modify_user_info'] = {
        'username': username,
        'chat_id': query.message.chat_id,
        'message_id': query.message.message_id,
        'list_type': context.user_data.get('current_list_type', 'all'),
        'page_number': context.user_data.get('current_page', 1)
    }
    await query.answer()
    
    text = (f"➕ لطفاً مقدار حجمی که می‌خواهید به کاربر `{username}` اضافه شود را به **گیگابایت (GB)** وارد کنید.\n\n"
            "برای انصراف، از دکمه زیر استفاده کنید.")
            
    await query.message.delete()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    return ADD_DATA_PROMPT
async def do_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    modify_info = context.user_data.get('modify_user_info')
    if not modify_info:
        await update.message.reply_text("خطا: اطلاعات گفتگو منقضی شده. لطفاً دوباره امتحان کنید.")
        return ConversationHandler.END

    try:
        days_to_add = int(update.message.text)
        if days_to_add <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد مثبت وارد کنید.")
            return ADD_DAYS_PROMPT
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return ADD_DAYS_PROMPT

    await update.message.delete()
    
    username = modify_info['username']
    user_data = await get_user_data(username)
    if not user_data:
        await context.bot.edit_message_text(
            chat_id=modify_info['chat_id'], message_id=modify_info['message_id'],
            text=f"❌ خطا: اطلاعات کاربر `{username}` یافت نشد."
        )
        return ConversationHandler.END

    current_expire_ts = user_data.get('expire') or 0
    now_ts = datetime.datetime.now().timestamp()
    start_date_ts = max(current_expire_ts, now_ts)
    new_expire_date = datetime.datetime.fromtimestamp(start_date_ts) + datetime.timedelta(days=days_to_add)
    
    success, message = await modify_user_api(username, {"expire": int(new_expire_date.timestamp())})
    
    success_msg = f"✅ با موفقیت {days_to_add} روز به اشتراک اضافه شد." if success else f"❌ خطا در افزودن روز: {message}"

    await show_user_details_panel(context=context, **modify_info, success_message=success_msg)
    
    context.user_data.pop('modify_user_info', None)
    return ConversationHandler.END


# ==================== مکالمه افزایش حجم ====================
async def prompt_for_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    username = query.data.removeprefix('add_data_')
        
    context.user_data['modify_user_info'] = {
        'username': username,
        'chat_id': query.message.chat_id,
        'message_id': query.message.message_id,
        'list_type': context.user_data.get('current_list_type', 'all'),
        'page_number': context.user_data.get('current_page', 1)
    }
    await query.answer()
    
    text = (f"➕ لطفاً مقدار حجمی که می‌خواهید به کاربر `{username}` اضافه شود را به **گیگابایت (GB)** وارد کنید.\n\n"
            "برای انصراف، از دکمه زیر استفاده کنید.")
            
    # --- CHANGE IS HERE ---
    # Delete the old inline keyboard message
    await query.message.delete()
    # Send a new message with the ReplyKeyboardMarkup
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    # --- END OF CHANGE ---
    
    return ADD_DATA_PROMPT

async def do_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    modify_info = context.user_data.get('modify_user_info')
    if not modify_info:
        await update.message.reply_text("خطا: اطلاعات گفتگو منقضی شده. لطفاً دوباره امتحان کنید.")
        return ConversationHandler.END

    try:
        gb_to_add = int(update.message.text)
        if gb_to_add <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد مثبت وارد کنید.")
            return ADD_DATA_PROMPT
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return ADD_DATA_PROMPT

    await update.message.delete()
    
    username = modify_info['username']
    user_data = await get_user_data(username)
    if not user_data:
        await context.bot.edit_message_text(
            chat_id=modify_info['chat_id'], message_id=modify_info['message_id'],
            text=f"❌ خطا: اطلاعات کاربر `{username}` یافت نشد."
        )
        return ConversationHandler.END

    current_data_limit = user_data.get('data_limit', 0)
    new_data_limit = current_data_limit + (gb_to_add * GB_IN_BYTES)
    
    success, message = await modify_user_api(username, {"data_limit": new_data_limit})
    
    success_msg = f"✅ با موفقیت {gb_to_add} گیگابایت به حجم کل اضافه شد." if success else f"❌ خطا در افزایش حجم: {message}"
    
    await show_user_details_panel(context=context, **modify_info, success_message=success_msg)
        
    context.user_data.pop('modify_user_info', None)
    return ConversationHandler.END


# ==================== توابع مستقل (بدون مکالمه) ====================
async def reset_user_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    # روش صحیح و امن برای استخراج نام کاربری
    username = query.data.removeprefix('reset_traffic_')

    await query.answer(f"در حال ریست ترافیک کاربر {username}...")
    
    success, message = await reset_user_traffic_api(username)
    success_msg = "✅ ترافیک کاربر با موفقیت صفر شد." if success else f"❌ خطا: {message}"

    await show_user_details_panel(
        context=context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        username=username,
        list_type=context.user_data.get('current_list_type', 'all'),
        page_number=context.user_data.get('current_page', 1),
        success_message=success_msg
    )

async def confirm_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    # روش صحیح و امن برای استخراج نام کاربری
    username = query.data.removeprefix('delete_')
        
    list_type = context.user_data.get('current_list_type', 'all')
    page_number = context.user_data.get('current_page', 1)
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"do_delete_{username}")],
        [InlineKeyboardButton("❌ خیر", callback_data=f"user_details_{username}_{list_type}_{page_number}")]
    ])
    await query.edit_message_text(f"⚠️ آیا از حذف کامل کانفیگ `{username}` مطمئن هستید؟ این عمل غیرقابل بازگشت است.", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def do_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.db_manager import cleanup_marzban_user_data, get_telegram_id_from_marzban_username
    query = update.callback_query
    admin_user = update.effective_user
    # روش صحیح و امن برای استخراج نام کاربری
    username = query.data.removeprefix('do_delete_')

    await query.answer()
    
    # تشخیص میدهیم که این یک درخواست از طرف مشتری بوده یا خیر
    is_customer_request = "درخواست حذف سرویس" in query.message.text
    
    await query.edit_message_text(f"در حال حذف `{username}` از پنل مرزبان...", parse_mode=ParseMode.MARKDOWN)
    
    customer_id = await get_telegram_id_from_marzban_username(normalize_username(username))

    success, message = await delete_user_api(username)
    if success:
        await cleanup_marzban_user_data(username)
        
        admin_name = admin_user.full_name
        admin_mention = escape_markdown(admin_name, version=2).replace('(', '\\(').replace(')', '\\)')
        safe_username = escape_markdown(username, version=2)
        
        log_title = "🗑️ اشتراک حذف شد (بنا به درخواست مشتری)" if is_customer_request else "🗑️ اشتراک حذف شد (دستی توسط ادمین)"
        log_message = (
            f"{log_title}\n\n"
            f"▫️ **نام کاربری:** `{safe_username}`\n"
            f"👤 **توسط ادمین:** {admin_mention}"
        )
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)
        
        await query.edit_message_text(f"🗑 کانفیگ `{username}` و تمام اطلاعات مرتبط با آن با موفقیت حذف شد.", parse_mode=ParseMode.MARKDOWN)

        # اگر مشتری به ربات متصل بود به او اطلاع بده
        if customer_id:
             try:
                await context.bot.send_message(chat_id=customer_id, text=f"✅ سرویس `{username}` شما طبق درخواستتان حذف شد.")
             except Exception as e:
                LOGGER.warning(f"Config deleted, but failed to notify customer {customer_id}: {e}")

    else:
        await query.edit_message_text(f"❌ {message}", parse_mode=ParseMode.MARKDOWN)


# ==================== تابع تمدید هوشمند ====================
async def renew_user_smart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.financials.actions.payment import send_renewal_invoice_to_user
    from database.db_manager import get_user_note, get_telegram_id_from_marzban_username

    query = update.callback_query
    # روش صحیح و امن برای استخراج نام کاربری
    username = query.data.removeprefix('renew_')
    
    admin_user = update.effective_user
    await query.answer(f"در حال تمدید هوشمند کانفیگ {username}...")

    user_data = await get_user_data(username)
    if not user_data:
        await query.edit_message_text(f"❌ خطا: اطلاعات کانفیگ `{username}` یافت نشد.", parse_mode=ParseMode.MARKDOWN)
        return

    note_data = await get_user_note(normalize_username(username))
    
    renewal_duration_days = DEFAULT_RENEW_DAYS
    data_limit_gb = (user_data.get('data_limit') or 0) / GB_IN_BYTES
    subscription_price = 0

    if note_data:
        renewal_duration_days = note_data.get('subscription_duration') or renewal_duration_days
        if note_data.get('subscription_data_limit_gb') is not None:
            data_limit_gb = note_data.get('subscription_data_limit_gb')
        subscription_price = note_data.get('subscription_price') or 0

    await query.edit_message_text(f"در حال تمدید `{username}` (۱/۲: ریست ترافیک)...", parse_mode=ParseMode.MARKDOWN)
    success_reset, message_reset = await reset_user_traffic_api(username)
    if not success_reset:
        await query.edit_message_text(f"⚠️ **تمدید ناموفق!** خطا در ریست ترافیک: `{message_reset}`", parse_mode=ParseMode.MARKDOWN)
        return
        
    await query.edit_message_text(f"✅ ترافیک صفر شد. در حال تمدید `{username}` (۲/۲: آپدیت حجم و تاریخ)...", parse_mode=ParseMode.MARKDOWN)
    
    current_expire_ts = user_data.get('expire') or 0
    now_ts = datetime.datetime.now().timestamp()
    start_date_ts = max(current_expire_ts, now_ts)
    new_expire_date = datetime.datetime.fromtimestamp(start_date_ts) + datetime.timedelta(days=renewal_duration_days)
    
    payload_to_modify = {
        "expire": int(new_expire_date.timestamp()),
        "data_limit": int(data_limit_gb * GB_IN_BYTES),
        "status": "active"  # <--- این خط اضافه شده است
    }
    
    success_modify, message_modify = await modify_user_api(username, payload_to_modify)
    if not success_modify:
        await query.edit_message_text(f"⚠️ **تمدید ناقص!** ترافیک صفر شد، اما حجم و تاریخ آپدیت نشد. دلیل: `{message_modify}`", parse_mode=ParseMode.MARKDOWN)
        return
        
    admin_name = admin_user.full_name
    admin_mention = escape_markdown(admin_name, version=2).replace('(', '\\(').replace(')', '\\)')
    safe_username = escape_markdown(username, version=2)
    log_message = (
        f"🔄 *اشتراک تمدید شد*\n\n"
        f"▫️ **نام کاربری:** `{safe_username}`\n"
        f"▫️ **حجم جدید:** {int(data_limit_gb)} GB\n"
        f"▫️ **مدت تمدید:** {renewal_duration_days} روز\n"
        f"👤 **توسط ادمین:** {admin_mention}"
    )
    await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)

    response_message = (f"✅ **تمدید هوشمند موفق**\n\n"
                        f"▫️ **کانفیگ:** `{username}`\n"
                        f"▫️ **مدت:** `{renewal_duration_days}` روز\n"
                        f"▫️ **حجم کل:** `{int(data_limit_gb)}` GB\n"
                        f"▫️ **ترافیک:** صفر شد")
                        
    list_type = context.user_data.get('current_list_type', 'all')
    page_number = context.user_data.get('current_page', 1)
    back_button = InlineKeyboardButton("🔙 بازگشت به لیست", callback_data=f"show_users_page_{list_type}_{page_number}")
    await query.edit_message_text(response_message, reply_markup=InlineKeyboardMarkup([[back_button]]), parse_mode=ParseMode.MARKDOWN)
    
    customer_id = await get_telegram_id_from_marzban_username(normalize_username(username))
    if not customer_id:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ کاربر `{username}` به ربات متصل نیست. پیام تمدید برای او ارسال نشد.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        success_message_to_customer = (
            f"✅ **سرویس شما با موفقیت تمدید شد!**\n\n"
            f"▫️ **نام کاربری:** `{username}`\n"
            f"▫️ **حجم جدید:** {int(data_limit_gb)} GB\n"
            f"▫️ **مدت تمدید:** {renewal_duration_days} روز\n\n"
            f"از همراهی شما سپاسگزاریم."
        )
        await context.bot.send_message(
            chat_id=customer_id,
            text=success_message_to_customer,
            parse_mode=ParseMode.MARKDOWN
        )
        LOGGER.info(f"Successfully sent renewal confirmation to customer {customer_id} for user {username}.")

        if subscription_price > 0:
            await send_renewal_invoice_to_user(
                context=context, user_telegram_id=customer_id, username=username,
                renewal_days=renewal_duration_days, 
                price=subscription_price,
                data_limit_gb=int(data_limit_gb)
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"ℹ️ پیام تایید و صورتحساب برای مشتری (ID: {customer_id}) ارسال شد."
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"ℹ️ پیام تایید تمدید برای مشتری (ID: {customer_id}) ارسال شد (صورتحساب ارسال نشد چون قیمتی ثبت نشده بود)."
            )

    except Exception as e:
        LOGGER.error(f"User {username} renewed, but failed to notify customer {customer_id}: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"⚠️ **خطا:** کانفیگ `{username}` تمدید شد، اما ارسال پیام به مشتری (ID: {customer_id}) با خطا مواجه شد. لطفاً دستی به او اطلاع دهید.",
            parse_mode=ParseMode.MARKDOWN
        )