# ===== IMPORTS & DEPENDENCIES =====
import datetime
import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# --- Local Imports ---
from modules.financials.actions.payment import send_renewal_invoice_to_user
from .constants import ADD_DATA_PROMPT, ADD_DAYS_PROMPT, GB_IN_BYTES, DEFAULT_RENEW_DAYS
from shared.keyboards import get_user_management_keyboard
from .data_manager import load_users_map, save_users_map, normalize_username
from .api import (
    get_user_data, modify_user_api, delete_user_api,
    reset_user_traffic_api, reset_subscription_url_api
)

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- ADMIN-FACING DELETION HANDLERS ---
async def admin_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    username, customer_id = parts[3], int(parts[4])
    await query.edit_message_text(f"در حال حذف سرویس `{username}`...", parse_mode=ParseMode.MARKDOWN)
    success, message = await delete_user_api(username)
    if success:
        users_map = await load_users_map()
        if username in users_map:
            del users_map[username]
            await save_users_map(users_map)
        await query.edit_message_text(f"✅ سرویس `{username}` با موفقیت حذف شد.", parse_mode=ParseMode.MARKDOWN)
        try:
            await context.bot.send_message(chat_id=customer_id, text=f"✅ سرویس `{username}` شما طبق درخواستتان حذف شد.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            LOGGER.warning(f"User {username} deleted, but failed to notify customer {customer_id}: {e}")
            await query.message.reply_text(f"⚠️ کاربر حذف شد، اما ارسال پیام به مشتری (ID: {customer_id}) خطا داد.")
    else:
        await query.edit_message_text(f"❌ خطا در حذف: {message}", parse_mode=ParseMode.MARKDOWN)

async def admin_reject_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    username, customer_id = parts[3], int(parts[4])
    await query.edit_message_text(f"❌ درخواست حذف سرویس `{username}` توسط شما رد شد.", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(chat_id=customer_id, text=f"❌ درخواست شما برای حذف سرویس `{username}` توسط ادمین رد شد.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        LOGGER.warning(f"Deletion for {username} rejected, but failed to notify customer {customer_id}: {e}")
        await query.message.reply_text(f"⚠️ درخواست رد شد، اما ارسال پیام به مشتری (ID: {customer_id}) خطا داد.")

# ===== USER MODIFICATION ACTIONS (from admin panel) =====
async def reset_user_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    username = query.data.split('_', 2)[-1]
    await query.answer()
    success, message = await reset_user_traffic_api(username)
    if success:
        back_button = InlineKeyboardButton("🔙 بازگشت", callback_data=f"user_details_{username}")
        keyboard = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(f"✅ ترافیک مصرفی کاربر `{username}` صفر شد.", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.answer(f"❌ {message}", show_alert=True)


async def renew_user_smart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # --- The import is changed to the new function ---
    from database.db_manager import get_user_note

    query = update.callback_query
    username = query.data.split('_', 1)[-1]
    await query.answer(f"در حال تمدید هوشمند کاربر {username}...")

    user_data = await get_user_data(username)
    if not user_data or "error" in user_data:
        await query.edit_message_text(f"❌ خطا: اطلاعات کاربر `{username}` یافت نشد یا خطای API رخ داد.")
        return

    # --- Database Interaction using the new function ---
    renewal_duration_days = DEFAULT_RENEW_DAYS
    subscription_price = 0  # Default price if not found
    note_data = await get_user_note(normalize_username(username)) # <-- Function call changed here
    if note_data:
        if note_data.get('subscription_duration'):
            renewal_duration_days = note_data['subscription_duration']
        if note_data.get('subscription_price'):
            subscription_price = note_data['subscription_price']
    # --- End of Database Interaction ---

    await query.edit_message_text(f"در حال تمدید `{username}` (۱/۲: ریست ترافیک)...", parse_mode=ParseMode.MARKDOWN)
    success_reset, message_reset = await reset_user_traffic_api(username)
    if not success_reset:
        await query.edit_message_text(f"⚠️ **تمدید ناموفق!**\n\nخطا در ریست ترافیک: `{message_reset}`", parse_mode=ParseMode.MARKDOWN)
        return
        
    await query.edit_message_text(f"✅ ترافیک صفر شد.\nدر حال تمدید `{username}` (۲/۲: افزایش تاریخ)...", parse_mode=ParseMode.MARKDOWN)
    
    current_expire_ts = user_data.get('expire')
    now_ts = datetime.datetime.now().timestamp()
    
    start_date_ts = current_expire_ts if current_expire_ts and current_expire_ts > now_ts else now_ts
    start_date = datetime.datetime.fromtimestamp(start_date_ts)
    
    new_expire_date = start_date + datetime.timedelta(days=renewal_duration_days)
    new_expire_ts = int(new_expire_date.timestamp())

    success_expire, message_expire = await modify_user_api(username, {"expire": new_expire_ts})
    if not success_expire:
        await query.edit_message_text(f"⚠️ **تمدید ناقص!**\n\nترافیک صفر شد، اما تاریخ تمدید نشد.\n**دلیل:** `{message_expire}`", parse_mode=ParseMode.MARKDOWN)
        return
        
    data_limit_gb = (user_data.get('data_limit') or 0) / GB_IN_BYTES
    response_message = (f"✅ **تمدید هوشمند موفق**\n\n"
                        f"▫️ **کاربر:** `{username}`\n"
                        f"▫️ **مدت:** `{renewal_duration_days}` روز\n"
                        f"▫️ **حجم کل:** `{f'{data_limit_gb:.0f}' if data_limit_gb > 0 else 'نامحدود'}` GB\n"
                        f"▫️ **ترافیک:** صفر شد")
                        
    back_button = InlineKeyboardButton("🔙 بازگشت", callback_data=f"user_details_{username}")
    await query.edit_message_text(response_message, reply_markup=InlineKeyboardMarkup([[back_button]]), parse_mode=ParseMode.MARKDOWN)
    
    users_map = await load_users_map()
    customer_id = users_map.get(normalize_username(username))
    if customer_id:
        try:
            if subscription_price > 0:
                await send_renewal_invoice_to_user(
                    context=context,
                    user_telegram_id=customer_id,
                    username=username,
                    renewal_days=renewal_duration_days,
                    price=subscription_price
                )
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"ℹ️ صورتحساب تمدید برای مشتری (ID: {customer_id}) ارسال شد.")
            else:
                await context.bot.send_message(chat_id=customer_id, text="✅ اشتراک شما با موفقیت تمدید شد!")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"ℹ️ پیام تایید (بدون فاکتور) برای مشتری (ID: {customer_id}) ارسال شد.")

        except Exception as e:
            LOGGER.warning(f"User {username} renewed, but failed to notify customer {customer_id}: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ کاربر تمدید شد، اما ارسال پیام/فاکتور به مشتری (ID: {customer_id}) خطا داد.")
            
async def prompt_for_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    username = query.data.split('_', 2)[-1]
    await query.answer()
    context.user_data['action_username'] = username
    await query.edit_message_text(f"لطفاً مقدار حجم برای افزودن به `{username}` را به **گیگابایت (GB)** وارد کنید:", parse_mode=ParseMode.MARKDOWN)
    return ADD_DATA_PROMPT

async def process_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = context.user_data.get('action_username')
    if not username: return ConversationHandler.END
    try:
        gb_to_add = float(update.message.text)
        if gb_to_add <= 0:
            await update.message.reply_text("❌ حجم باید یک عدد مثبت باشد."); return ADD_DATA_PROMPT
        await update.message.reply_text(f"در حال افزودن `{gb_to_add}` GB به `{username}`...")
        user_data = await get_user_data(username)
        if not user_data:
            await update.message.reply_text(f"❌ خطا: کاربر `{username}` یافت نشد."); return ConversationHandler.END
        current_limit = user_data.get('data_limit') or 0
        new_limit = int(current_limit + (gb_to_add * GB_IN_BYTES))
        success, message = await modify_user_api(username, {"data_limit": new_limit})
        reply_text = f"✅ `{gb_to_add}` GB با موفقیت به `{username}` اضافه شد." if success else f"❌ {message}"
        await update.message.reply_text(reply_text, reply_markup=get_user_management_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فقط عدد وارد کنید."); return ADD_DATA_PROMPT
    context.user_data.clear()
    return ConversationHandler.END

async def prompt_for_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    username = query.data.split('_', 2)[-1]
    await query.answer()
    context.user_data['action_username'] = username
    await query.edit_message_text(f"لطفاً تعداد روز برای افزودن به انقضای `{username}` را وارد کنید:", parse_mode=ParseMode.MARKDOWN)
    return ADD_DAYS_PROMPT

async def process_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = context.user_data.get('action_username')
    if not username: return ConversationHandler.END
    try:
        days_to_add = int(update.message.text)
        if days_to_add <= 0:
            await update.message.reply_text("❌ تعداد روز باید عدد مثبت باشد."); return ADD_DAYS_PROMPT
        await update.message.reply_text(f"در حال افزودن `{days_to_add}` روز به `{username}`...")
        user_data = await get_user_data(username)
        if not user_data:
            await update.message.reply_text(f"❌ خطا: کاربر `{username}` یافت نشد."); return ConversationHandler.END
        current_expire_ts = user_data.get('expire')
        start_date = datetime.datetime.fromtimestamp(current_expire_ts) if current_expire_ts and current_expire_ts > datetime.datetime.now().timestamp() else datetime.datetime.now()
        new_expire = int((start_date + datetime.timedelta(days=days_to_add)).timestamp())
        success, message = await modify_user_api(username, {"expire": new_expire})
        reply_text = f"✅ `{days_to_add}` روز با موفقیت به `{username}` اضافه شد." if success else f"❌ {message}"
        await update.message.reply_text(reply_text, reply_markup=get_user_management_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. فقط عدد صحیح وارد کنید."); return ADD_DAYS_PROMPT
    context.user_data.clear()
    return ConversationHandler.END

async def confirm_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; username = query.data.split('_', 1)[-1]
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"do_delete_{username}"), InlineKeyboardButton("❌ خیر", callback_data=f"user_details_{username}")]])
    await query.edit_message_text(f"⚠️ آیا از حذف کامل `{username}` مطمئن هستید؟", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def do_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; username = query.data.split('_', 2)[-1]
    await query.answer()
    await query.edit_message_text(f"در حال حذف `{username}`...", parse_mode=ParseMode.MARKDOWN)
    success, message = await delete_user_api(username)
    if success:
        users_map = await load_users_map()
        if username in users_map:
            del users_map[username]
            await save_users_map(users_map)
        await query.edit_message_text(f"🗑 کاربر `{username}` با موفقیت حذف شد.", parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(f"❌ {message}", parse_mode=ParseMode.MARKDOWN)