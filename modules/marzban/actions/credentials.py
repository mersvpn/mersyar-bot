# modules/marzban/actions/credentials.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode
from .data_manager import load_marzban_credentials, save_marzban_credentials
from .api import get_marzban_token
from shared.callbacks import cancel_conversation

LOGGER = logging.getLogger(__name__)
GET_URL, GET_USERNAME, GET_PASSWORD, CONFIRM = range(4)

async def start_set_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    creds = await load_marzban_credentials()
    current_info = (
        f"**تنظیمات فعلی پنل مرزبان:**\n\n"
        f"▫️ **آدرس:** `{creds.get('base_url', 'تنظیم نشده')}`\n"
        f"▫️ **نام کاربری:** `{creds.get('username', 'تنظیم نشده')}`\n"
        f"▫️ **رمز عبور:** `{'*' * 8 if creds.get('password') else 'تنظیم نشده'}`\n\n"
        "---"
    )
    await update.message.reply_text(
        f"{current_info}\n\n"
        "**مرحله ۱/۳:** لطفاً **آدرس کامل (URL)** پنل مرزبان را وارد کنید.\n"
        "(مثال: `https://panel.example.com`)\n\n"
        "برای لغو، /cancel را ارسال کنید.",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_creds'] = {}
    return GET_URL

async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ آدرس نامعتبر است. باید با `http://` یا `https://` شروع شود.")
        return GET_URL
    context.user_data['new_creds']['base_url'] = url.rstrip('/')
    await update.message.reply_text("✅ آدرس ذخیره شد.\n\n**مرحله ۲/۳:** لطفاً **نام کاربری** ادمین پنل را وارد کنید.")
    return GET_USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_creds']['username'] = update.message.text.strip()
    await update.message.reply_text("✅ نام کاربری ذخیره شد.\n\n**مرحله ۳/۳:** لطفاً **رمز عبور** ادمین پنل را وارد کنید.")
    return GET_PASSWORD

async def get_password_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_creds']['password'] = update.message.text.strip()
    creds = context.user_data['new_creds']
    summary = (
        f"**لطفاً اطلاعات را تایید کنید:**\n\n"
        f"▫️ **آدرس:** `{creds['base_url']}`\n"
        f"▫️ **نام کاربری:** `{creds['username']}`\n"
        f"▫️ **رمز عبور:** `{'*' * len(creds['password'])}`"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ذخیره و تست اتصال", callback_data="creds_save")],
        [InlineKeyboardButton("❌ لغو", callback_data="creds_cancel")]
    ])
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    return CONFIRM

async def save_and_test_creds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    new_creds = context.user_data.get('new_creds')
    if not new_creds:
        await query.edit_message_text("خطا: اطلاعات یافت نشد.")
        return await cancel_conversation(update, context)
    
    await save_marzban_credentials(new_creds)
    await query.edit_message_text("✅ اطلاعات ذخیره شد. در حال تست اتصال...")
    
    token = await get_marzban_token()
    if token:
        await query.message.reply_text("🎉 **اتصال موفقیت‌آمیز بود!**\nتوکن دسترسی با موفقیت از پنل دریافت شد.")
    else:
        await query.message.reply_text("⚠️ **خطا در اتصال!**\nاطلاعات ذخیره شد، اما ربات نتوانست به پنل متصل شود. لطفاً آدرس، نام کاربری و رمز عبور را بررسی کرده و مجدداً تلاش کنید.")
    
    context.user_data.clear()
    return ConversationHandler.END

credential_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^🔐 مدیریت پنل مرزبان$'), start_set_credentials)],
    states={
        GET_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_url)],
        GET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
        GET_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password_and_confirm)],
        CONFIRM: [
            CallbackQueryHandler(save_and_test_creds, pattern='^creds_save$'),
            CallbackQueryHandler(cancel_conversation, pattern='^creds_cancel$'),
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    conversation_timeout=600
)