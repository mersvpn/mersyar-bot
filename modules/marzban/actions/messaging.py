# FILE: modules/marzban/actions/messaging.py (REVISED)

import logging
import uuid
import asyncio
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from shared.callbacks import end_conversation_and_show_menu
from telegram.constants import ParseMode
from telegram.error import TelegramError

# V V V V V THE FIX IS HERE (IMPORTS) V V V V V
from shared.keyboards import get_admin_main_menu_keyboard

# ^ ^ ^ ^ ^ THE FIX IS HERE (IMPORTS) ^ ^ ^ ^ ^

LOGGER = logging.getLogger(__name__)

(
    CHOOSING_TYPE, GETTING_USER_ID, GETTING_MESSAGE, GETTING_BUTTON_DECISION,
    GETTING_BUTTON_TEXT, GETTING_BUTTON_URL, CONFIRMING_SEND,
) = range(7)

async def send_broadcast_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    # --- LAZY IMPORTS ---
    from database.db_manager import get_broadcast_job, delete_broadcast_job, get_all_linked_users

    job_data = context.job.data
    job_id = job_data.get("job_id")
    admin_id = job_data.get("admin_id")

    LOGGER.info(f"Starting broadcast job: {job_id}")
    job_info = await get_broadcast_job(job_id)

    if not job_info:
        LOGGER.error(f"Job {job_id} failed: data not found in database.")
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

    if target_user_id:
        users_to_message = [target_user_id]
    else:
        all_users_map = await get_all_linked_users()
        users_to_message = list(set(all_users_map.values()))

    total = len(users_to_message)
    success, failure = 0, 0
    await context.bot.send_message(admin_id, f"🚀 فرآیند ارسال پیام (ID: {job_id}) برای {total} کاربر آغاز شد...")

    for user_id in users_to_message:
        try:
            await context.bot.send_message(
                chat_id=user_id, text=text,
                parse_mode=parse_mode, reply_markup=reply_markup
            )
            success += 1
        except TelegramError as e:
            failure += 1
            LOGGER.warning(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1)

    await delete_broadcast_job(job_id)
    report = (
        f"✅ **گزارش نهایی ارسال**\n\n"
        f"▫️ **ID:** `{job_id}`\n"
        f"▫️ **کل:** {total}\n"
        f"▫️ **موفق:** {success} ✅\n"
        f"▫️ **ناموفق:** {failure} ❌"
    )
    await context.bot.send_message(admin_id, report, parse_mode=ParseMode.MARKDOWN)
    LOGGER.info(f"Job {job_id} finished. Success: {success}, Failure: {failure}")

async def start_messaging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.keyboards import get_back_to_main_menu_keyboard
    
    context.user_data['messaging_info'] = {}
    
    inline_keyboard = [
        [
            InlineKeyboardButton("👥 ارسال همگانی", callback_data="msg_broadcast_all"),
            InlineKeyboardButton("👤 ارسال به یک کاربر", callback_data="msg_broadcast_single")
        ]
    ]

    await update.message.reply_text(
        "لطفاً نوع ارسال را انتخاب کنید:", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )
    # Send a dummy message just to show the new keyboard
    await update.message.reply_text(
        "گزینه مورد نظر را انتخاب کنید:", 
        reply_markup=get_back_to_main_menu_keyboard()
    )
    return CHOOSING_TYPE
async def prompt_for_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['messaging_info']['type'] = 'single'
    await query.edit_message_text("لطفاً **ID عددی** تلگرام کاربر مورد نظر را وارد کنید:", parse_mode=ParseMode.MARKDOWN)
    return GETTING_USER_ID


async def validate_user_id_and_get_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
            f"❌ کاربری با ID `{user_id}` یافت نشد یا ربات توسط او بلاک شده است.", parse_mode=ParseMode.MARKDOWN
        )
        return GETTING_USER_ID


async def get_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['messaging_info']['type'] = 'all'
    await query.edit_message_text("لطفاً متن پیام همگانی را وارد کنید (پشتیبانی از Markdown).", parse_mode=ParseMode.MARKDOWN)
    return GETTING_MESSAGE


async def get_button_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['messaging_info']['text'] = update.message.text
    context.user_data['messaging_info']['parse_mode'] = ParseMode.MARKDOWN
    keyboard = [[InlineKeyboardButton("✅ بله", callback_data="msg_add_button_yes"), InlineKeyboardButton(" خیر", callback_data="msg_add_button_no")]]
    await update.message.reply_text("آیا می‌خواهید یک دکمه به پیام اضافه کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return GETTING_BUTTON_DECISION


async def prompt_for_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً متن روی دکمه را وارد کنید:")
    return GETTING_BUTTON_TEXT


async def get_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['messaging_info']['button_text'] = update.message.text
    await update.message.reply_text("عالی. اکنون **لینک (URL)** یا کلمه کلیدی `خرید` را وارد کنید.", parse_mode=ParseMode.MARKDOWN)
    return GETTING_BUTTON_URL


async def show_preview_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- LAZY IMPORT ---
    from database.db_manager import get_all_linked_users

    query = update.callback_query
    info = context.user_data.get('messaging_info', {})

    if query:
        await query.answer()
        await query.edit_message_text("در حال آماده‌سازی پیش‌نمایش...")
    else:
        url_or_keyword = update.message.text.strip()
        if url_or_keyword.lower() == 'خرید':
            info['button_callback'] = 'start_purchase_flow'
            info['button_url'] = None
        elif re.match(r'^https?://', url_or_keyword):
            info['button_url'] = url_or_keyword
            info['button_callback'] = None
        else:
            await update.message.reply_text("❌ لینک نامعتبر است یا کلمه کلیدی `خرید` نیست.", parse_mode=ParseMode.MARKDOWN)
            return GETTING_BUTTON_URL

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

    if info.get('type') == 'single':
        target_name = info.get('target_user_name', 'N/A')
        target_id = info.get('target_user_id')
        confirm_text = f"آیا پیام بالا برای کاربر **{target_name}** (ID: `{target_id}`) ارسال شود؟"
    else:
        total_users = len(set((await get_all_linked_users()).values()))
        confirm_text = f"⚠️ **اخطار:** آیا پیام بالا برای **تمام {total_users} کاربر** ربات ارسال شود؟"

    keyboard = [[InlineKeyboardButton("✅ ارسال", callback_data="msg_confirm_send"), InlineKeyboardButton("❌ لغو", callback_data="msg_cancel")]]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=confirm_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRMING_SEND


async def schedule_job_and_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- LAZY IMPORT ---
    from database.db_manager import add_broadcast_job

    query = update.callback_query
    info = context.user_data.get('messaging_info', {})
    await query.answer()

    job_id = str(uuid.uuid4())
    broadcast_data = {
        "job_id": job_id,
        "text": info.get("text"),
        "parse_mode": info.get("parse_mode"),
        "button_text": info.get("button_text"),
        "button_url": info.get("button_url"),
        "button_callback": info.get("button_callback"),
        "target_user_id": info.get("target_user_id"),
    }

    await add_broadcast_job(broadcast_data)

    context.job_queue.run_once(
        send_broadcast_message_job,
        when=1,
        data={"job_id": job_id, "admin_id": update.effective_user.id},
        name=f"broadcast_{job_id}"
    )

    await query.edit_message_text(f"✅ عملیات ارسال با ID `{job_id}` در صف قرار گرفت.", parse_mode=ParseMode.MARKDOWN)
    # V V V V V THE FIX IS HERE (FUNCTION CALL) V V V V V
    return await end_conversation_and_show_menu(update, context)
    # ^ ^ ^ ^ ^ THE FIX IS HERE (FUNCTION CALL) ^ ^ ^ ^ ^


async def end_messaging_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        # Message is handled by the standard function
    # V V V V V THE FIX IS HERE (FUNCTION CALL) V V V V V
    return await end_conversation_and_show_menu(update, context)
    # ^ ^ ^ ^ ^ THE FIX IS HERE (FUNCTION CALL) ^ ^ ^ ^ ^


messaging_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^📨 ارسال پیام$'), start_messaging)],
    states={
        CHOOSING_TYPE: [
            CallbackQueryHandler(prompt_for_user_id, pattern='^msg_broadcast_single$'),
            CallbackQueryHandler(get_broadcast_message, pattern='^msg_broadcast_all$'),
        ],
        GETTING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^🔙 بازگشت به منوی اصلی$'), validate_user_id_and_get_message)],
        GETTING_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^🔙 بازگشت به منوی اصلی$'), get_button_decision)],
        GETTING_BUTTON_DECISION: [
            CallbackQueryHandler(prompt_for_button_text, pattern='^msg_add_button_yes$'),
            CallbackQueryHandler(show_preview_and_confirm, pattern='^msg_add_button_no$'),
        ],
        GETTING_BUTTON_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^🔙 بازگشت به منوی اصلی$'), get_button_url)],
        GETTING_BUTTON_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^🔙 بازگشت به منوی اصلی$'), show_preview_and_confirm)],
        CONFIRMING_SEND: [
            CallbackQueryHandler(schedule_job_and_end, pattern='^msg_confirm_send$'),
            CallbackQueryHandler(end_messaging_conversation, pattern='^msg_cancel$'), # Kept for inline cancel button
        ]
    },
    fallbacks=[
        MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), end_messaging_conversation),
        CallbackQueryHandler(end_messaging_conversation, pattern='^msg_cancel$') # General cancel
    ],
    conversation_timeout=600,
    # Allow other admin buttons to end this conversation
    per_user=True, 
    per_chat=True,
)