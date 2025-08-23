# FILE: modules/marzban/actions/note.py
# (کد کامل و نهایی‌شده برای جایگزینی)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# --- Local Imports ---
# NOTE: We assume you have a database manager that can handle structured notes.
# We will interact with it via these hypothetical functions.
# If these don't exist, you'll need to create them in your db_manager.py
from database.db_manager import get_user_note, save_user_note, delete_user_note
from .data_manager import normalize_username
from shared.keyboards import get_user_management_keyboard
from shared.callbacks import cancel_conversation

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
GET_DURATION, GET_PRICE = range(2)

# ===== NEW NOTE MANAGEMENT CONVERSATION =====

async def prompt_for_note_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to get structured note details (duration and price)."""
    query = update.callback_query
    await query.answer()

    username_raw = query.data.split('_', 1)[1]  # note_{username}
    username = normalize_username(username_raw)
    context.user_data['note_username'] = username
    context.user_data['note_details'] = {}  # Initialize a dictionary to store details

    # Fetch existing structured note from the database
    current_note = await get_user_note(username)
    
    current_duration = current_note.get('subscription_duration', 'تعیین نشده') if current_note else 'تعیین نشده'
    current_price = f"{current_note.get('subscription_price', 0):,}" if current_note and current_note.get('subscription_price') else 'تعیین نشده'

    username_md = escape_markdown(username, version=2)
    message = (
        f"✍️ *مدیریت اطلاعات اشتراک برای:* `{username_md}`\n\n"
        f"▫️ **مدت فعلی:** {current_duration} روز\n"
        f"▫️ **قیمت فعلی:** {current_price} تومان\n\n"
        f"لطفاً **مدت زمان اشتراک** جدید را به **روز** وارد کنید \(مثال: 30\)\.\n"
        f"برای لغو /cancel را بزنید\\."
    )
    
    keyboard = []
    if current_note:
        keyboard.append([InlineKeyboardButton("🗑 حذف اطلاعات فعلی", callback_data=f"delete_note_{username}")])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return GET_DURATION

async def get_duration_and_ask_for_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the duration and asks for the price."""
    try:
        duration = int(update.message.text)
        if duration <= 0:
            await update.message.reply_text("❌ مدت زمان باید یک عدد مثبت باشد. لطفاً دوباره وارد کنید.")
            return GET_DURATION
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return GET_DURATION
    
    context.user_data['note_details']['subscription_duration'] = duration
    
    await update.message.reply_text(
        f"✅ مدت زمان: **{duration} روز** ثبت شد.\n\n"
        f"حالا لطفاً **قیمت اشتراک** را به **تومان** وارد کنید (فقط عدد، مثال: 50000).",
        parse_mode=ParseMode.HTML
    )
    return GET_PRICE

async def get_price_and_save_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets the price, saves the complete structured note, and ends the conversation."""
    username = context.user_data.get('note_username')
    if not username:
        return await cancel_conversation(update, context)

    try:
        price = int(update.message.text)
        if price < 0:
            await update.message.reply_text("❌ قیمت نمی‌تواند منفی باشد. لطفاً دوباره وارد کنید.")
            return GET_PRICE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return GET_PRICE
        
    context.user_data['note_details']['subscription_price'] = price
    
    # Save the structured data to the database
    await save_user_note(username, context.user_data['note_details'])
    
    await update.message.reply_text(
        f"✅ اطلاعات اشتراک برای کاربر `{username}` با موفقیت ذخیره شد.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_user_management_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def delete_note_from_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the deletion of a note from the initial prompt."""
    query = update.callback_query
    await query.answer()

    username_raw = query.data.split('_', 2)[2] # delete_note_{username}
    username = normalize_username(username_raw)
    
    await delete_user_note(username)
    
    await query.edit_message_text(
        f"✅ اطلاعات اشتراک برای کاربر `{username}` با موفقیت حذف شد.",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data.clear()
    return ConversationHandler.END

    # ===== NEW FUNCTION for Listing Subscriptions =====

# ===== NEW FUNCTION for Listing Subscriptions (Upgraded with Buttons) =====

async def list_users_with_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays a list of all users who have subscription details saved, with each user as a clickable button.
    """
    await update.message.reply_text("در حال دریافت لیست اشتراک‌های ثبت‌شده...")

    from database.db_manager import get_all_users_with_notes
    
    users_with_notes = await get_all_users_with_notes()
    
    if not users_with_notes:
        await update.message.reply_text("هیچ اشتراکی تاکنون ثبت نشده است.")
        return

    keyboard_rows = []
    message_text = "👤 **لیست اشتراک‌های ثبت‌شده:**\nروی نام هر کاربر کلیک کنید تا وارد جزئیات شوید.\n"

    for user_note in users_with_notes:
        username = user_note.get('username')
        duration = user_note.get('subscription_duration')
        price = user_note.get('subscription_price')

        duration_str = f"{duration} روز" if duration is not None else "نامشخص"
        price_str = f"{price:,} ت" if price is not None else "نامشخص"

        # Create a descriptive button text
        button_text = f"👤 {username}  |  ⏳ {duration_str}  |  💰 {price_str}"
        
        # --- KEY CHANGE: Use a callback_data that the existing show_user_details handler understands ---
        # We use '_all_1' so the 'Back' button on the details page will return to the main user list.
        callback_data = f"user_details_{username}_all_1"
        
        keyboard_rows.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Add a close button at the end
    keyboard_rows.append([InlineKeyboardButton("✖️ بستن", callback_data="close_pagination")])
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    
    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )