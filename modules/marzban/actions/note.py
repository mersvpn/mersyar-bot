# FILE: modules/marzban/actions/note.py (نسخه اصلاح شده برای دریافت حجم)
import math
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from .data_manager import normalize_username
from shared.keyboards import get_user_management_keyboard
from shared.callbacks import cancel_conversation
from .api import get_all_users as get_all_marzban_users

LOGGER = logging.getLogger(__name__)

# وضعیت‌های جدید برای مکالمه
GET_DURATION, GET_DATA_LIMIT, GET_PRICE = range(3)
USERS_PER_PAGE = 10

async def prompt_for_note_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import get_user_note

    query = update.callback_query
    await query.answer()
    username_raw = query.data.split('_', 1)[1]
    username = normalize_username(username_raw)
    context.user_data['note_username'] = username
    context.user_data['note_details'] = {}
    
    current_note = await get_user_note(username)
    current_duration = current_note.get('subscription_duration', 'تعیین نشده') if current_note else 'تعیین نشده'
    current_datalimit = current_note.get('subscription_data_limit_gb', 'تعیین نشده') if current_note else 'تعیین نشده'
    current_price = f"{current_note.get('subscription_price', 0):,}" if current_note and current_note.get('subscription_price') is not None else 'تعیین نشده'
    username_md = escape_markdown(username, version=2)

    message = (
        f"✍️ *مدیریت اطلاعات اشتراک برای:* `{username_md}`\n\n"
        f"▫️ **مدت فعلی:** {current_duration} روز\n"
        f"▫️ **حجم فعلی:** {current_datalimit} GB\n"
        f"▫️ **قیمت فعلی:** {current_price} تومان\n\n"
        f"۱/۳: لطفاً **مدت زمان اشتراک** جدید را به **روز** وارد کنید \(مثال: 30\)\.\n"
        f"برای لغو /cancel را بزنید\\."
    )
    keyboard = []
    if current_note and any(current_note.values()):
        keyboard.append([InlineKeyboardButton("🗑 حذف اطلاعات فعلی", callback_data=f"delete_note_{username}")])

    await query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode=ParseMode.MARKDOWN_V2
    )
    return GET_DURATION

async def get_duration_and_ask_for_data_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        duration = int(update.message.text)
        if duration <= 0:
            await update.message.reply_text("❌ مدت زمان باید یک عدد مثبت باشد.")
            return GET_DURATION
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return GET_DURATION
        
    context.user_data['note_details']['subscription_duration'] = duration
    await update.message.reply_text(
        f"✅ مدت زمان: **{duration} روز** ثبت شد.\n\n"
        f"۲/۳: حالا لطفاً **حجم اشتراک** را به **گیگابایت (GB)** وارد کنید (فقط عدد).", 
        parse_mode=ParseMode.HTML
    )
    return GET_DATA_LIMIT

async def get_data_limit_and_ask_for_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        data_limit = int(update.message.text)
        if data_limit < 0:
            await update.message.reply_text("❌ حجم نمی‌تواند منفی باشد.")
            return GET_DATA_LIMIT
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return GET_DATA_LIMIT
        
    context.user_data['note_details']['subscription_data_limit_gb'] = data_limit
    await update.message.reply_text(
        f"✅ حجم: **{data_limit} GB** ثبت شد.\n\n"
        f"۳/۳: در نهایت، **قیمت اشتراک** را به **تومان** وارد کنید (فقط عدد).", 
        parse_mode=ParseMode.HTML
    )
    return GET_PRICE

async def get_price_and_save_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_user_note

    username = context.user_data.get('note_username')
    if not username: return await cancel_conversation(update, context)
    try:
        price = int(update.message.text)
        if price < 0:
            await update.message.reply_text("❌ قیمت نمی‌تواند منفی باشد.")
            return GET_PRICE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return GET_PRICE
        
    context.user_data['note_details']['subscription_price'] = price
    await save_user_note(username, context.user_data['note_details'])
    await update.message.reply_text(
        f"✅ اطلاعات اشتراک برای `{username}` ذخیره شد.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_user_management_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def delete_note_from_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import delete_user_note

    query = update.callback_query
    await query.answer("✅ اطلاعات با موفقیت حذف شد.", show_alert=True)
    username_raw = query.data.split('_', 2)[2]
    username = normalize_username(username_raw)
    
    await delete_user_note(username)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به لیست اشتراک‌ها", callback_data="list_subs_page_1")]
    ])
    await query.edit_message_text(
        f"✅ اطلاعات اشتراک برای کاربر `{username}` با موفقیت حذف شد.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def list_users_with_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.db_manager import get_all_users_with_notes

    query = update.callback_query
    page = 1
    
    if query:
        await query.answer()
        if query.data.startswith('list_subs_page_'):
            page = int(query.data.split('_')[-1])
        message_to_edit = query.message
    else:
        message_to_edit = await update.message.reply_text("در حال دریافت لیست اشتراک‌های ثبت‌شده...")

    all_notes = await get_all_users_with_notes()
    marzban_users = await get_all_marzban_users()
    
    if marzban_users is None:
        await message_to_edit.edit_text("❌ خطا در ارتباط با پنل مرزبان.")
        return
        
    marzban_usernames = {normalize_username(u['username']) for u in marzban_users if u.get('username')}
    valid_notes = sorted(
        [note for note in all_notes if normalize_username(note['username']) in marzban_usernames],
        key=lambda x: x['username'].lower()
    )

    if not valid_notes:
        await message_to_edit.edit_text("هیچ اشتراک فعالی برای نمایش ثبت نشده است.")
        return

    total_users = len(valid_notes)
    total_pages = math.ceil(total_users / USERS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * USERS_PER_PAGE
    end_index = start_index + USERS_PER_PAGE
    page_notes = valid_notes[start_index:end_index]

    keyboard_rows = []
    it = iter(page_notes)
    for note1 in it:
        row = []
        username1 = note1['username']
        row.append(InlineKeyboardButton(f"👤 {username1}", callback_data=f"user_details_{username1}_subs_{page}"))
        try:
            note2 = next(it)
            username2 = note2['username']
            row.append(InlineKeyboardButton(f"👤 {username2}", callback_data=f"user_details_{username2}_subs_{page}"))
        except StopIteration:
            pass
        keyboard_rows.append(row)

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"list_subs_page_{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"list_subs_page_{page + 1}"))
    if nav_row:
        keyboard_rows.append(nav_row)
    keyboard_rows.append([InlineKeyboardButton("✖️ بستن", callback_data="close_pagination")])
    
    message_parts = ["👤 **لیست اشتراک‌های ثبت‌شده:**\n"]
    for note in page_notes:
        uname = note['username']
        dur = note.get('subscription_duration') or "نامشخص"
        datalimit = note.get('subscription_data_limit_gb') or "نامشخص"
        price = note.get('subscription_price')
        price_f = f"{price:,}" if price is not None else "نامشخص"
        
        line = (
            f"▫️ **{uname}**\n"
            f"   ⏳ {dur} روزه  |  📦 {datalimit} GB  |  💰 {price_f} تومان"
        )
        message_parts.append(line)

    message_text = "\n\n".join(message_parts)

    await message_to_edit.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        parse_mode=ParseMode.MARKDOWN,
    )