# FILE: modules/customer/actions/receipt.py
# (نسخه نهایی و ادغام شده)

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)
from telegram.constants import ParseMode

from config import config
# --- UPDATED: Import the new database function instead of the old JSON loader ---
from database.db_manager import get_linked_marzban_usernames

LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
GET_RECEIPT_PHOTO = range(1)

async def start_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for the receipt submission conversation.
    Asks the user to send their payment receipt photo.
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="لطفاً تصویر واضح از رسید پرداخت خود را ارسال کنید.\n\nبرای انصراف، دستور /cancel را بفرستید.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Receives the photo, forwards it to the admin(s) with full details, and ends the conversation.
    This function combines the logic from your original file with the new conversation structure.
    """
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id

    # --- Prepare detailed information for the admin (from your original logic) ---
    caption = (
        f"🧾 **رسید پرداخت جدید دریافت شد** 🧾\n\n"
        f"👤 **از طرف:** {user.full_name}\n"
    )
    if user.username:
        caption += f"📧 **یوزرنیم:** @{user.username}\n"
    caption += f"🆔 **آیدی تلگرام:** `{user.id}`\n"

    # Try to find the associated Marzban username(s) using the new database function
    linked_accounts = await get_linked_marzban_usernames(user.id)
    if linked_accounts:
        caption += "▫️ **سرویس‌های متصل در دیتابیس:**\n"
        for acc in linked_accounts:
            caption += f"  - `{acc}`\n"
    else:
        caption += "▫️ **سرویس متصلی در دیتابیس یافت نشد.**\n"
    
    # --- Forward the photo and info to all admins ---
    if not config.AUTHORIZED_USER_IDS:
        LOGGER.warning("Receipt received, but no admin IDs are configured to forward to.")
        await update.message.reply_text("متاسفانه در حال حاضر امکان پردازش رسید شما وجود ندارد. لطفاً با پشتیبانی تماس بگیرید.")
        return ConversationHandler.END

    num_sent = 0
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
            num_sent += 1
        except Exception as e:
            LOGGER.error(f"Failed to forward receipt to admin {admin_id}: {e}")

    if num_sent > 0:
        await update.message.reply_text(
            "✅ رسید شما با موفقیت برای پشتیبانی ارسال شد.\n"
            "لطفاً منتظر تایید از طرف ما بمانید."
        )
    else:
        await update.message.reply_text("❌ خطا در ارسال رسید به پشتیبانی. لطفاً بعداً دوباره تلاش کنید.")

    return ConversationHandler.END

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancels the receipt submission process.
    """
    # Try to edit the original message if possible
    if context.user_data.get('panel_message_id'):
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['panel_message_id'],
                text="عملیات لغو شد. به پنل خرید و پرداخت بازگشتید."
            )
        except: pass # Ignore if message is old
    else:
        await update.message.reply_text("ارسال رسید لغو شد.")

    context.user_data.clear()
    return ConversationHandler.END

# --- The ConversationHandler for the entire receipt flow ---
receipt_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_receipt_upload, pattern='^start_receipt_upload$')],
    states={
        GET_RECEIPT_PHOTO: [MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt_photo)]
    },
    fallbacks=[CommandHandler('cancel', cancel_receipt_upload)],
    conversation_timeout=600 # 10 minutes for user to send the photo
)