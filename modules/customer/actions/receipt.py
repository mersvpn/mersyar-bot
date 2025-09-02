# FILE: modules/customer/actions/receipt.py (نسخه نهایی با اصلاح نام متغیر کانفیگ)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import config
from database.db_manager import get_pending_invoices_for_user
from shared.keyboards import get_customer_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
CHOOSE_INVOICE, GET_RECEIPT_PHOTO = range(2)

async def start_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for receipt submission. Finds pending invoices for the user.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    pending_invoices = await get_pending_invoices_for_user(user_id)

    if not pending_invoices:
        LOGGER.info(f"User {user_id} tried to upload a receipt but has no pending invoices.")
        await query.edit_message_text("شما هیچ فاکتور پرداخت نشده‌ای ندارید.")
        return ConversationHandler.END

    if len(pending_invoices) == 1:
        invoice = pending_invoices[0]
        context.user_data['invoice_id'] = invoice['invoice_id']
        LOGGER.info(f"User {user_id} has one pending invoice (#{invoice['invoice_id']}). Asking for photo.")
        
        try:
            await query.delete_message()
        except BadRequest:
            pass

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")]])
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🧾 شما یک فاکتور به مبلغ `{invoice['price']:,}` تومان دارید.\n\n"
                 f"لطفاً تصویر واضح از رسید پرداخت خود را ارسال کنید.",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return GET_RECEIPT_PHOTO
    else:
        LOGGER.info(f"User {user_id} has multiple pending invoices. Asking to choose.")
        buttons = []
        text = "شما چندین فاکتور پرداخت نشده دارید. لطفاً انتخاب کنید که این رسید برای کدام فاکتور است:\n\n"
        for inv in pending_invoices:
            details = inv.get('plan_details', {})
            btn_text = f"فاکتور #{inv['invoice_id']} - {details.get('volume','N/A')}GB, {details.get('duration','N/A')} روز - {inv.get('price', 0):,} تومان"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_invoice_{inv['invoice_id']}")])
        
        buttons.append([InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")])
        keyboard = InlineKeyboardMarkup(buttons)
        
        await query.edit_message_text(text=text, reply_markup=keyboard)
        return CHOOSE_INVOICE

async def select_invoice_for_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice of invoice and asks for the photo."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        invoice_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        LOGGER.error(f"Invalid callback data in select_invoice_for_receipt: {query.data}")
        await query.answer("خطای داخلی رخ داد. لطفاً دوباره تلاش کنید.", show_alert=True)
        return ConversationHandler.END

    context.user_data['invoice_id'] = invoice_id
    LOGGER.info(f"User {user_id} selected invoice #{invoice_id} for receipt submission.")
    
    await query.answer()
    try:
        await query.delete_message()
    except BadRequest:
        pass

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")]])
    await context.bot.send_message(
        chat_id=user_id,
        text="✅ بسیار خب! لطفاً تصویر واضح از رسید پرداخت خود را ارسال کنید.",
        reply_markup=keyboard
    )
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the photo, forwards it to admins with invoice details and appropriate buttons."""
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    invoice_id = context.user_data.get('invoice_id')

    if not invoice_id:
        LOGGER.error(f"User {user.id} reached handle_receipt_photo without an invoice_id in context.")
        await update.message.reply_text("خطای داخلی رخ داد. لطفاً از ابتدا شروع کنید.")
        return ConversationHandler.END
        
    from database.db_manager import get_pending_invoice
    invoice_details = await get_pending_invoice(invoice_id)
    if not invoice_details:
        LOGGER.error(f"Could not find invoice #{invoice_id} for user {user.id} in the database.")
        await update.message.reply_text("خطا: اطلاعات فاکتور شما یافت نشد.")
        return ConversationHandler.END

    plan = invoice_details.get('plan_details', {})
    price = invoice_details.get('price', 0)
    volume = plan.get('volume', 'N/A')
    duration = plan.get('duration', 'N/A')
    
    caption = (
        f"🧾 *رسید پرداخت جدید برای فاکتور #{invoice_id}*\n\n"
        f"👤 *کاربر:* {user.full_name}\n"
        f"🆔 *آیدی:* `{user.id}`\n"
        f"-------------------------------------\n"
        f"📦 *جزئیات پلن:*\n"
        f"  - حجم: *{volume} گیگابایت*\n"
        f"  - مدت: *{duration} روز*\n"
        f"  - مبلغ: *{price:,} تومان*\n"
    )

    if not config.AUTHORIZED_USER_IDS:
        LOGGER.warning("Receipt received, but no admin IDs are configured to forward to.")
        await update.message.reply_text("متاسفانه در حال حاضر امکان پردازش رسید شما وجود ندارد.")
        return ConversationHandler.END

    # --- START: New Logic to Differentiate Invoice Types ---
    # We check if volume or duration are 0, which is typical for a manually created user invoice.
    is_manual_purchase = (volume == 0 or duration == 0)
    
    if is_manual_purchase:
        LOGGER.info(f"Receipt for invoice #{invoice_id} is for a manually created user. Showing 'Confirm Payment' button.")
        approve_button_text = "✅ تایید پرداخت"
        approve_callback = f"confirm_manual_receipt_{invoice_id}"
    else:
        LOGGER.info(f"Receipt for invoice #{invoice_id} is for a custom plan. Showing 'Confirm and Create' button.")
        approve_button_text = "✅ تایید و ساخت سرویس"
        approve_callback = f"approve_receipt_{invoice_id}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(approve_button_text, callback_data=approve_callback),
            InlineKeyboardButton("❌ رد کردن", callback_data=f"reject_receipt_{invoice_id}")
        ]
    ])
    # --- END: New Logic ---

    num_sent = 0
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=photo_file_id, caption=caption,
                parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
            )
            num_sent += 1
        except Exception as e:
            LOGGER.error(f"Failed to forward receipt for invoice #{invoice_id} to admin {admin_id}: {e}")

    if num_sent > 0:
        await update.message.reply_text(
            "✅ رسید شما با موفقیت برای پشتیبانی ارسال شد.\n"
            "منتظر تایید توسط پشتیبانی بمانید."
        )
    else:
        await update.message.reply_text("❌ خطا در ارسال رسید به پشتیبانی. لطفاً بعداً دوباره تلاش کنید.")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="شما به منوی اصلی بازگشتید.",
        reply_markup=get_customer_main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def warn_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles cases where the user sends text instead of a photo."""
    await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً **عکس رسید** را ارسال کنید یا عملیات را لغو نمایید.")
    return GET_RECEIPT_PHOTO

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the receipt submission process."""
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.delete_message()
        except BadRequest:
            pass
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="عملیات ارسال رسید لغو شد.",
        reply_markup=get_customer_main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# در انتهای فایل modules/customer/actions/receipt.py، این بخش را جایگزین کنید

receipt_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_receipt_upload, pattern='^customer_send_receipt$')], # <-- FIX: الگو اصلاح شد
    states={
        CHOOSE_INVOICE: [CallbackQueryHandler(select_invoice_for_receipt, pattern='^select_invoice_')],
        GET_RECEIPT_PHOTO: [
            MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, warn_for_photo)
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_receipt_upload, pattern='^cancel_receipt_upload$')],
    conversation_timeout=600 
)