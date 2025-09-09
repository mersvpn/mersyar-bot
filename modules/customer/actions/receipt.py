# FILE: modules/customer/actions/receipt.py (FINAL, DUAL-ENTRY VERSION)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import config
from database.db_manager import get_pending_invoices_for_user
from shared.keyboards import get_customer_shop_keyboard
from modules.general.actions import end_conversation_and_show_menu

LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
CHOOSE_INVOICE, GET_RECEIPT_PHOTO = range(2)

# --- Entry Point 1: From Text Button (User has multiple invoices) ---
async def start_receipt_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the receipt upload process when user clicks the text button in the shop menu."""
    user_id = update.effective_user.id
    
    processing_message = await update.message.reply_text("در حال بررسی فاکتورهای شما...", reply_markup=ReplyKeyboardRemove())
    
    pending_invoices = await get_pending_invoices_for_user(user_id)
    await processing_message.delete()

    if not pending_invoices:
        await update.message.reply_text("شما هیچ فاکتور پرداخت نشده‌ای ندارید.", reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    # If user has only one invoice, go straight to asking for a photo
    if len(pending_invoices) == 1:
        invoice = pending_invoices[0]
        context.user_data['invoice_id'] = invoice['invoice_id']
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")]])
        await update.message.reply_text(
            text=f"🧾 شما یک فاکتور به مبلغ `{invoice['price']:,}` تومان دارید.\n\n"
                 f"لطفاً تصویر واضح از رسید پرداخت خود را ارسال کنید.",
            reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return GET_RECEIPT_PHOTO
    
    # If user has multiple invoices, ask them to choose one
    else:
        buttons = []
        text = "شما چندین فاکتور پرداخت نشده دارید. لطفاً انتخاب کنید که این رسید برای کدام فاکتور است:\n\n"
        for inv in pending_invoices:
            details = inv.get('plan_details', {})
            btn_text = f"فاکتور #{inv['invoice_id']} - {details.get('volume','N/A')}GB/{details.get('duration','N/A')} روز - {inv.get('price', 0):,} تومان"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_invoice_{inv['invoice_id']}")])
        
        buttons.append([InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text=text, reply_markup=keyboard)
        return CHOOSE_INVOICE

# --- Entry Point 2: From Inline Button (User has a specific invoice) ---
async def start_receipt_from_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the receipt upload process when user clicks the inline button under an invoice."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()

    # The invoice message itself contains the invoice ID in its text
    message_text = query.message.text
    try:
        # Extract invoice ID from a line like "*شماره فاکتور: `123`*"
        invoice_id = int(message_text.split("شماره فاکتور: `")[1].split("`")[0])
        context.user_data['invoice_id'] = invoice_id
    except (IndexError, ValueError):
        LOGGER.error(f"Could not parse invoice ID from message for user {user_id}.")
        await query.edit_message_text("❌ خطا در شناسایی فاکتور. لطفاً از منوی فروشگاه اقدام کنید.")
        return ConversationHandler.END

    LOGGER.info(f"User {user_id} started receipt upload for specific invoice #{invoice_id} from inline button.")
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")]])
    # Edit the invoice message to ask for the photo
    await query.edit_message_text(
        text=f"{query.message.text}\n\n"
             "✅ بسیار خب! لطفاً تصویر واضح از رسید پرداخت خود را برای این فاکتور ارسال کنید.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return GET_RECEIPT_PHOTO


# --- Subsequent Conversation States (Mostly Unchanged) ---

async def select_invoice_for_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function is now only called when the user starts from the main menu and has multiple invoices
    query = update.callback_query
    try:
        invoice_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.answer("خطای داخلی رخ داد.", show_alert=True)
        return ConversationHandler.END

    context.user_data['invoice_id'] = invoice_id
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو عملیات", callback_data="cancel_receipt_upload")]])
    await query.edit_message_text(
        text="✅ بسیار خب! لطفاً تصویر واضح از رسید پرداخت خود را ارسال کنید.",
        reply_markup=keyboard
    )
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    invoice_id = context.user_data.get('invoice_id')

    if not invoice_id:
        await update.message.reply_text("خطای داخلی رخ داد. لطفاً از ابتدا شروع کنید.", reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END
        
    from database.db_manager import get_pending_invoice
    invoice_details = await get_pending_invoice(invoice_id)
    if not invoice_details:
        await update.message.reply_text("خطا: اطلاعات فاکتور شما یافت نشد.", reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    plan = invoice_details.get('plan_details', {})
    price = invoice_details.get('price', 0)
    # Safely get volume and duration with defaults
    volume = plan.get('volume', 'N/A')
    duration = plan.get('duration', 'N/A')
    
    caption = (f"🧾 *رسید پرداخت جدید برای فاکتور #{invoice_id}*\n\n"
               f"👤 *کاربر:* {user.full_name}\n"
               f"🆔 *آیدی:* `{user.id}`\n"
               f"-------------------------------------\n"
               f"📦 *جزئیات پلن:*\n"
               f"  - حجم: *{volume if volume != 999 else 'نامحدود'} گیگابایت*\n"
               f"  - مدت: *{duration} روز*\n"
               f"  - مبلغ: *{price:,} تومان*")

    approve_callback = f"approve_receipt_{invoice_id}"
    if plan.get("plan_type") == "unlimited" or (volume == 0 or duration == 0): # Check for manual or unlimited
        approve_callback = f"confirm_manual_receipt_{invoice_id}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و فعالسازی", callback_data=approve_callback),
         InlineKeyboardButton("❌ رد کردن", callback_data=f"reject_receipt_{invoice_id}")]])

    num_sent = 0
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_photo(chat_id=admin_id, photo=photo_file_id, caption=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            num_sent += 1
        except Exception as e:
            LOGGER.error(f"Failed to forward receipt for invoice #{invoice_id} to admin {admin_id}: {e}")

    if num_sent > 0:
        await update.message.reply_text("✅ رسید شما با موفقیت برای پشتیبانی ارسال شد. منتظر تایید بمانید.", reply_markup=get_customer_shop_keyboard())
    else:
        await update.message.reply_text("❌ خطا در ارسال رسید به پشتیبانی. لطفاً بعداً دوباره تلاش کنید.", reply_markup=get_customer_shop_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

async def warn_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً **عکس رسید** را ارسال کنید یا عملیات را لغو نمایید.")
    return GET_RECEIPT_PHOTO

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        try:
            # Edit the message to show cancellation, don't just delete it.
            await update.callback_query.edit_message_text("عملیات ارسال رسید لغو شد.")
        except BadRequest:
            pass
    
    # Send a new message to show the shop menu keyboard again.
    await context.bot.send_message(chat_id=update.effective_chat.id, text="به منوی فروشگاه بازگشتید.", reply_markup=get_customer_shop_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# --- The final ConversationHandler with DUAL entry points ---
receipt_conv = ConversationHandler(
    entry_points=[
        # Entry Point 1: From the text button in the shop menu
        MessageHandler(filters.Regex('^🧾 ارسال رسید پرداخت$'), start_receipt_from_menu),
        # Entry Point 2: From the inline button under an invoice
        CallbackQueryHandler(start_receipt_from_invoice, pattern='^customer_send_receipt$')
    ],
    states={
        CHOOSE_INVOICE: [CallbackQueryHandler(select_invoice_for_receipt, pattern='^select_invoice_')],
        GET_RECEIPT_PHOTO: [
            MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_receipt_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, warn_for_photo)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_receipt_upload, pattern='^cancel_receipt_upload$'),
        MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), end_conversation_and_show_menu)
    ],
    conversation_timeout=600 
)