# FILE: modules/customer/actions/receipt.py
# (نسخه نهایی با بازگشت صحیح به منوی اصلی)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import config
from database.db_manager import get_linked_marzban_usernames
# --- NEW: Import the customer main menu keyboard ---
from shared.keyboards import get_customer_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
GET_RECEIPT_PHOTO = 0 

async def start_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for the receipt submission conversation.
    Deletes the previous message and sends a new one asking for the photo.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        await query.delete_message()
    except BadRequest as e:
        LOGGER.warning(f"Could not delete message in start_receipt_upload: {e}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")]
    ])
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ بسیار خب! لطفاً تصویر واضح از رسید پرداخت خود را ارسال کنید.",
        reply_markup=keyboard
    )
    
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Receives the photo, forwards it to the admin(s) with approval buttons,
    and properly ends the conversation for the user.
    """
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id

    caption = (
        f"🧾 **رسید پرداخت جدید دریافت شد** 🧾\n\n"
        f"👤 **از طرف:** {user.full_name}\n"
    )
    if user.username:
        caption += f"📧 **یوزرنیم:** @{user.username}\n"
    caption += f"🆔 **آیدی تلگرام:** `{user.id}`\n"

    linked_accounts = await get_linked_marzban_usernames(user.id)
    if linked_accounts:
        caption += "▫️ **سرویس‌های متصل در دیتابیس:**\n"
        for acc in linked_accounts:
            caption += f"  - `{acc}`\n"
    else:
        caption += "▫️ **سرویس متصلی در دیتابیس یافت نشد.**\n"
    
    if not config.AUTHORIZED_USER_IDS:
        LOGGER.warning("Receipt received, but no admin IDs are configured to forward to.")
        await update.message.reply_text("متاسفانه در حال حاضر امکان پردازش رسید شما وجود ندارد. لطفاً با پشتیبانی تماس بگیرید.")
        return ConversationHandler.END

    # ======================== START: FIX - Add Approval Buttons ========================
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید پرداخت", callback_data=f"approve_receipt_{user.id}"),
            InlineKeyboardButton("❌ رد پرداخت", callback_data=f"reject_receipt_{user.id}")
        ]
    ])
    # ========================= END: FIX - Add Approval Buttons =========================

    num_sent = 0
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard  # <-- Pass the keyboard here
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

    # --- Use the helper function for returning to main menu ---
    # Note: You might need to create this helper or just use the direct code
    # For now, I'll assume the direct code is fine.
    
    final_keyboard = get_customer_main_menu_keyboard()
    final_text = "شما به منوی اصلی بازگشتید."
    # Check if the user is an admin in customer view
    if user.id in config.AUTHORIZED_USER_IDS:
        from shared.keyboards import get_admin_main_menu_keyboard
        final_keyboard = get_admin_main_menu_keyboard()
        final_text = "شما به منوی اصلی ادمین بازگشتید."

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=final_text,
        reply_markup=final_keyboard
    )

    return ConversationHandler.END

async def warn_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles cases where the user sends text instead of a photo.
    """
    await update.message.reply_text(
        "❌ ورودی نامعتبر است. لطفاً به جای متن، **عکس رسید** خود را ارسال کنید یا عملیات را لغو نمایید."
    )
    return GET_RECEIPT_PHOTO

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancels the receipt submission process and returns the user to the main menu.
    """
    chat_id = update.effective_chat.id
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            # Delete the "Please send a photo" message
            await query.delete_message()
        except BadRequest:
            pass
    
    # --- START OF FIX: Always send a final message with the main menu ---
    await context.bot.send_message(
        chat_id=chat_id, 
        text="عملیات ارسال رسید لغو شد و شما به منوی اصلی بازگشتید.",
        reply_markup=get_customer_main_menu_keyboard()
    )
    # --- END OF FIX ---
    
    # Clear any lingering user_data from the conversation
    context.user_data.clear()
    return ConversationHandler.END

# The ConversationHandler for the entire receipt flow
receipt_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_receipt_upload, pattern='^start_receipt_upload$')],
    states={
        GET_RECEIPT_PHOTO: [
            MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, warn_for_photo)
        ]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_receipt_upload),
        CallbackQueryHandler(cancel_receipt_upload, pattern='^cancel_receipt_upload$')
    ],
    conversation_timeout=600 
)