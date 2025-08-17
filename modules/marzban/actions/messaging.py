# ===== IMPORTS & DEPENDENCIES =====
import logging
import uuid
import asyncio
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ... (imports) ...
# --- Local Imports ---
from .data_manager import load_users_map, save_broadcasts, load_broadcasts
# CORRECTED: Import keyboards and callbacks from the new shared location
from shared.keyboards import get_admin_main_menu_keyboard
from shared.callbacks import cancel_conversation
from modules.auth import admin_only_conv

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- CONSTANTS ---
(
    CHOOSING_TYPE,
    GETTING_USER_ID,
    GETTING_MESSAGE,
    GETTING_BUTTON_DECISION,
    GETTING_BUTTON_TEXT,
    GETTING_BUTTON_URL,
    CONFIRMING_SEND,
) = range(7)

# --- BACKGROUND JOB ---
async def send_broadcast_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """The background job that iterates through users and sends the message."""
    job_data = context.job.data
    job_id = job_data.get("job_id")
    admin_id = job_data.get("admin_id")

    LOGGER.info(f"Starting broadcast job: {job_id}")
    broadcasts_data = await load_broadcasts()
    job_info = broadcasts_data.get(job_id)

    if not job_info:
        LOGGER.error(f"Job {job_id} failed: data not found in broadcasts.json.")
        await context.bot.send_message(admin_id, f"❌ خطای بحرانی: اطلاعات جاب {job_id} یافت نشد.")
        return

    text = job_info.get("text")
    parse_mode = job_info.get("parse_mode")
    button_text = job_info.get("button_text")
    button_url = job_info.get("button_url")
    button_callback = job_info.get("button_callback")
    target_user_id = job_info.get("target_user_id")

    reply_markup = None
    if button_text:
        if button_url:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=button_url)]])
        elif button_callback:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data=button_callback)]])

    # Determine the target audience
    if target_user_id:
        users_to_message = [target_user_id]
    else:
        all_users = await load_users_map()
        users_to_message = list(set(all_users.values())) # Use set to get unique IDs

    total = len(users_to_message)
    success, failure = 0, 0

    await context.bot.send_message(admin_id, f"🚀 فرآیند ارسال پیام (ID: {job_id}) برای {total} کاربر آغاز شد...")

    for user_id in users_to_message:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            success += 1
        except TelegramError as e:
            failure += 1
            LOGGER.warning(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1) # Sleep for 100ms to avoid hitting rate limits

    # Clean up the job from the broadcasts file
    broadcasts_data.pop(job_id, None)
    await save_broadcasts(broadcasts_data)

    report = (
        f"✅ **گزارش نهایی ارسال**\n\n"
        f"▫️ **ID:** `{job_id}`\n"
        f"▫️ **کل:** {total}\n"
        f"▫️ **موفق:** {success} ✅\n"
        f"▫️ **ناموفق:** {failure} ❌"
    )
    await context.bot.send_message(admin_id, report, parse_mode=ParseMode.MARKDOWN)
    LOGGER.info(f"Job {job_id} finished. Success: {success}, Failure: {failure}")


# --- CONVERSATION HANDLER FUNCTIONS ---

async def start_messaging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the messaging conversation by asking for broadcast type."""
    context.user_data['messaging_info'] = {}
    keyboard = [
        [InlineKeyboardButton("👥 ارسال همگانی", callback_data="msg_broadcast_all")],
        [InlineKeyboardButton("👤 ارسال به یک کاربر", callback_data="msg_broadcast_single")],
        [InlineKeyboardButton("❌ لغو", callback_data="msg_cancel")]
    ]
    await update.message.reply_text("لطفاً نوع ارسال را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_TYPE

async def prompt_for_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin to enter the numeric Telegram ID for a single user broadcast."""
    query = update.callback_query
    await query.answer()
    context.user_data['messaging_info']['type'] = 'single'
    await query.edit_message_text("لطفاً **ID عددی** تلگرام کاربر مورد نظر را وارد کنید:", parse_mode=ParseMode.MARKDOWN)
    return GETTING_USER_ID

async def validate_user_id_and_get_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates the entered ID by checking if the bot can get the chat info."""
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط ID عددی کاربر را وارد کنید.")
        return GETTING_USER_ID

    await update.message.reply_text(f"در حال اعتبارسنجی ID: `{user_id}`...")
    try:
        chat = await context.bot.get_chat(user_id)
        context.user_data['messaging_info']['target_user_id'] = user_id
        context.user_data['messaging_info']['target_user_name'] = chat.full_name

        await update.message.reply_text(
            f"✅ کاربر **{chat.full_name}** یافت شد.\n\n"
            "اکنون لطفاً متن پیام خود را وارد کنید (پشتیبانی از Markdown).",
            parse_mode=ParseMode.MARKDOWN
        )
        return GETTING_MESSAGE
    except TelegramError as e:
        LOGGER.warning(f"Admin tried to message invalid user ID {user_id}. Error: {e}")
        await update.message.reply_text(
            f"❌ کاربری با ID `{user_id}` یافت نشد یا ربات توسط او بلاک شده است.\n\n"
            "لطفاً یک ID دیگر وارد کنید یا عملیات را لغو نمایید (/cancel).",
            parse_mode=ParseMode.MARKDOWN
        )
        return GETTING_USER_ID

async def get_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for the message text for a broadcast to all users."""
    query = update.callback_query
    await query.answer()
    context.user_data['messaging_info']['type'] = 'all'
    await query.edit_message_text("لطفاً متن پیام همگانی را وارد کنید (پشتیبانی از Markdown).", parse_mode=ParseMode.MARKDOWN)
    return GETTING_MESSAGE

async def get_button_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the message text and asks if a button should be added."""
    context.user_data['messaging_info']['text'] = update.message.text
    context.user_data['messaging_info']['parse_mode'] = ParseMode.MARKDOWN
    keyboard = [[InlineKeyboardButton("✅ بله", callback_data="msg_add_button_yes"), InlineKeyboardButton(" خیر", callback_data="msg_add_button_no")]]
    await update.message.reply_text("آیا می‌خواهید یک دکمه به پیام اضافه کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return GETTING_BUTTON_DECISION

async def prompt_for_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for the text to be displayed on the button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً متن روی دکمه را وارد کنید:")
    return GETTING_BUTTON_TEXT

async def get_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the button text and asks for the button's action (URL or callback)."""
    context.user_data['messaging_info']['button_text'] = update.message.text
    await update.message.reply_text("عالی. اکنون **لینک (URL)** یا کلمه کلیدی `خرید` را وارد کنید.", parse_mode=ParseMode.MARKDOWN)
    return GETTING_BUTTON_URL

async def show_preview_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows a preview of the message and asks for final confirmation."""
    query = update.callback_query
    info = context.user_data.get('messaging_info', {})

    if query:
        # Came from "No button" path
        await query.answer()
        await query.edit_message_text("در حال آماده‌سازی پیش‌نمایش...")
    else:
        # Came from entering a button URL/keyword
        url_or_keyword = update.message.text.strip()
        if url_or_keyword.lower() == 'خرید':
            info['button_callback'] = 'start_purchase_flow'
            info['button_url'] = None
        elif re.match(r'^https?://', url_or_keyword):
            info['button_url'] = url_or_keyword
            info['button_callback'] = None
        else:
            await update.message.reply_text("❌ لینک نامعتبر است. باید با http:// یا https:// شروع شود، یا کلمه `خرید` باشد.", parse_mode=ParseMode.MARKDOWN)
            return GETTING_BUTTON_URL

    # Build the message preview
    text = info.get("text", "متن پیام یافت نشد")
    parse_mode = info.get("parse_mode")
    button_text = info.get("button_text")
    button_url = info.get("button_url")
    button_callback = info.get("button_callback")
    reply_markup = None
    if button_text:
        if button_url: reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=button_url)]])
        elif button_callback: reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data=button_callback)]])

    await context.bot.send_message(chat_id=update.effective_chat.id, text="--- ⬇️ **پیش‌نمایش** ⬇️ ---", parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="--- ⬆️ **پایان** ⬆️ ---", parse_mode=ParseMode.MARKDOWN)

    # Build the confirmation text
    if info.get('type') == 'single':
        target_name = info.get('target_user_name', 'N/A')
        target_id = info.get('target_user_id')
        confirm_text = f"آیا پیام بالا برای کاربر **{target_name}** (ID: `{target_id}`) ارسال شود؟"
    else:
        total_users = len(set((await load_users_map()).values()))
        confirm_text = f"⚠️ **اخطار:** آیا پیام بالا برای **تمام {total_users} کاربر** ربات ارسال شود؟"

    keyboard = [[InlineKeyboardButton("✅ ارسال", callback_data="msg_confirm_send"), InlineKeyboardButton("❌ لغو", callback_data="msg_cancel")]]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=confirm_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRMING_SEND

async def schedule_job_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Schedules the background job and ends the conversation."""
    query = update.callback_query
    info = context.user_data.get('messaging_info', {})
    await query.answer()

    job_id = str(uuid.uuid4())
    broadcast_data = {
        "text": info.get("text"),
        "parse_mode": info.get("parse_mode"),
        "button_text": info.get("button_text"),
        "button_url": info.get("button_url"),
        "button_callback": info.get("button_callback"),
        "target_user_id": info.get("target_user_id"),
        "admin_id": update.effective_user.id
    }

    all_broadcasts = await load_broadcasts()
    all_broadcasts[job_id] = broadcast_data
    await save_broadcasts(all_broadcasts)

    # Schedule the job to run almost immediately
    context.job_queue.run_once(
        send_broadcast_message_job,
        when=1,
        data={"job_id": job_id, "admin_id": update.effective_user.id},
        name=f"broadcast_{job_id}"
    )

    await query.edit_message_text(f"✅ عملیات ارسال با ID `{job_id}` در صف قرار گرفت.", parse_mode=ParseMode.MARKDOWN)
    return await cancel_conversation(update, context)


async def end_messaging_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the messaging conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("عملیات ارسال پیام لغو شد.")
    return await cancel_conversation(update, context)

# --- EXPORTED CONVERSATION HANDLER ---
messaging_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^📨 ارسال پیام$'), admin_only_conv(start_messaging))],
    states={
        CHOOSING_TYPE: [
            CallbackQueryHandler(prompt_for_user_id, pattern='^msg_broadcast_single$'),
            CallbackQueryHandler(get_broadcast_message, pattern='^msg_broadcast_all$'),
            CallbackQueryHandler(end_messaging_conversation, pattern='^msg_cancel$'),
        ],
        GETTING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, validate_user_id_and_get_message)],
        GETTING_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_button_decision)],
        GETTING_BUTTON_DECISION: [
            CallbackQueryHandler(prompt_for_button_text, pattern='^msg_add_button_yes$'),
            CallbackQueryHandler(show_preview_and_confirm, pattern='^msg_add_button_no$'),
        ],
        GETTING_BUTTON_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_button_url)],
        GETTING_BUTTON_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_preview_and_confirm)],
        CONFIRMING_SEND: [
            CallbackQueryHandler(schedule_job_and_end, pattern='^msg_confirm_send$'),
            CallbackQueryHandler(end_messaging_conversation, pattern='^msg_cancel$'),
        ]
    },
    fallbacks=[CommandHandler('cancel', end_messaging_conversation)],
    conversation_timeout=600
)