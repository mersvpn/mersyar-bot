# FILE: modules/customer/actions/receipt.py (MODIFIED FOR CALLBACK_TYPES)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest
from shared.financial_utils import calculate_payment_details
from config import config
from database.db_manager import get_pending_invoices_for_user, get_pending_invoice
from shared.keyboards import get_customer_shop_keyboard
from shared.translator import _
# --- MODIFIED: Import the new callback type ---
from shared.callback_types import SendReceipt

LOGGER = logging.getLogger(__name__)

CHOOSE_INVOICE, GET_RECEIPT_PHOTO = range(2)

async def start_receipt_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the receipt upload process when initiated from the main menu."""
    user_id = update.effective_user.id
    processing_message = await update.message.reply_text(_("customer.receipt.checking_invoices"), reply_markup=ReplyKeyboardRemove())
    
    pending_invoices = await get_pending_invoices_for_user(user_id)
    await processing_message.delete()

    if not pending_invoices:
        await update.message.reply_text(_("customer.receipt.no_pending_invoices"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    if len(pending_invoices) == 1:
        invoice = pending_invoices[0]
        context.user_data['invoice_id'] = invoice['invoice_id']
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
        await update.message.reply_text(
            text=_("customer.receipt.single_invoice_prompt", price=invoice['price']),
            reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return GET_RECEIPT_PHOTO
    
    else:
        buttons = []
        text = _("customer.receipt.multiple_invoices_prompt")
        for inv in pending_invoices:
            details = inv.get('plan_details', {})
            btn_text = _("customer.receipt.invoice_button_format", 
                         id=inv['invoice_id'], 
                         volume=details.get('volume','N/A'), 
                         duration=details.get('duration','N/A'), 
                         price=inv.get('price', 0))
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_invoice_{inv['invoice_id']}")])
        
        buttons.append([InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text=text, reply_markup=keyboard)
        return CHOOSE_INVOICE

async def start_receipt_from_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the receipt upload process when initiated from an invoice button."""
    query = update.callback_query
    await query.answer()

    # --- MODIFIED: Use the new callback class to get the invoice_id directly ---
    callback_obj = SendReceipt.from_string(query.data)
    if not callback_obj:
        LOGGER.error(f"Could not parse SendReceipt callback for user {update.effective_user.id}. Data: {query.data}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_("customer.receipt.invoice_id_parse_error")
        )
        return ConversationHandler.END

    invoice_id = callback_obj.invoice_id
    context.user_data['invoice_id'] = invoice_id

    LOGGER.info(f"User {update.effective_user.id} started receipt upload for invoice #{invoice_id} from an inline button.")
    
    try:
        await query.message.delete()
    except Exception as e:
        LOGGER.warning(f"Could not delete the original invoice message (ID: {query.message.message_id}): {e}")

    text_prompt = _("customer.receipt.photo_prompt_simple")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")]
    ])
    
    try:
        with open("assets/receipt_guide.png", "rb") as photo_file:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_file,
                caption=text_prompt,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
    except FileNotFoundError:
        LOGGER.warning("assets/receipt_guide.png not found. Sending a text prompt as a fallback.")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text_prompt,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return GET_RECEIPT_PHOTO

async def select_invoice_for_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the selection when a user has multiple pending invoices."""
    query = update.callback_query
    try:
        invoice_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.answer(_("general.errors.internal_error"), show_alert=True)
        return ConversationHandler.END

    context.user_data['invoice_id'] = invoice_id
    await query.answer()
    
    try:
        await query.message.delete()
    except Exception as e:
        LOGGER.warning(f"Could not delete the invoice list message (ID: {query.message.message_id}): {e}")

    text_prompt = _("customer.receipt.photo_prompt_simple")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
    
    try:
        with open("assets/receipt_guide.png", "rb") as photo_file:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_file,
                caption=text_prompt,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
    except FileNotFoundError:
        LOGGER.warning("assets/receipt_guide.png not found. Sending a text prompt as a fallback.")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text_prompt,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Receives the photo, and forwards it to admins for approval.
    Intelligently formats the admin caption based on the invoice type.
    """
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    invoice_id = context.user_data.get('invoice_id')

    if not invoice_id:
        await update.message.reply_text(_("customer.receipt.internal_error_start_over"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END
        
    invoice_details = await get_pending_invoice(invoice_id)
    if not invoice_details:
        await update.message.reply_text(_("customer.receipt.invoice_info_not_found"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    plan = invoice_details.get('plan_details', {})
    total_price = invoice_details.get('price', 0)
    
    # --- ✨ Intelligent Caption Generation ✨ ---
    plan_type = plan.get("plan_type")
    invoice_type = invoice_details.get('plan_details', {}).get('invoice_type')

    if invoice_type == "WALLET_CHARGE":
        # This is a wallet charge invoice, use a simpler caption
        amount = plan.get('amount', total_price)
        caption = _("customer.receipt.admin_caption_wallet_charge",
                    invoice_id=invoice_id,
                    full_name=user.full_name,
                    user_id=f"`{user.id}`",
                    amount=f"{int(amount):,.0f}")
    else:
        # For all other types (new user, renewal, etc.), use the detailed caption
        volume = plan.get('volume', 'N/A')
        duration = plan.get('duration', 'N/A')
        
        # Calculate payment details only for non-wallet-charge invoices
        payment_info = await calculate_payment_details(user.id, total_price)
        paid_from_wallet = payment_info["paid_from_wallet"]
        payable_amount = payment_info["payable_amount"]
        
        volume_str = _("customer.receipt.unlimited_volume_label") if plan.get("plan_type") == "unlimited" else volume
        caption = _("customer.receipt.admin_caption_detailed", 
                    invoice_id=invoice_id, 
                    full_name=user.full_name, 
                    user_id=f"`{user.id}`", 
                    volume=volume_str, 
                    duration=duration, 
                    total_price=f"{total_price:,.0f}",
                    paid_from_wallet=f"{paid_from_wallet:,.0f}",
                    payable_amount=f"{payable_amount:,.0f}")
    # --- End of Intelligent Caption Generation ---

    # --- Button Logic (Remains mostly the same, but we need to identify wallet charge approval) ---
    if invoice_type == "WALLET_CHARGE":
        # Explicitly set the callback for wallet charge approval
        approve_button_text = _("keyboards.buttons.approve_payment") # A generic "Approve" button is fine
        approve_callback = f"approve_receipt_{invoice_id}" # This will be routed correctly in approval.py
    elif plan_type == "data_top_up":
        approve_button_text = _("keyboards.buttons.approve_data_top_up")
        approve_callback = f"approve_data_top_up_{invoice_id}"
    elif plan_type in ["custom", "unlimited"] or (isinstance(plan.get('volume', 'N/A'), int) and plan.get('volume', 'N/A') > 0):
        approve_button_text = _("keyboards.buttons.approve_and_create_service")
        approve_callback = f"approve_receipt_{invoice_id}"
    else:
        # Fallback for manual invoices or other types
        approve_button_text = _("keyboards.buttons.approve_payment")
        approve_callback = f"confirm_manual_receipt_{invoice_id}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(approve_button_text, callback_data=approve_callback),
            InlineKeyboardButton(_("keyboards.buttons.reject"), callback_data=f"reject_receipt_{invoice_id}")
        ]
    ])

    num_sent = 0
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_photo(chat_id=admin_id, photo=photo_file_id, caption=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            num_sent += 1
        except Exception as e:
            LOGGER.error(f"Failed to forward receipt for invoice #{invoice_id} to admin {admin_id}: {e}")

    if num_sent > 0:
        await update.message.reply_text(_("customer.receipt.sent_to_support_success"), reply_markup=get_customer_shop_keyboard())
    else:
        await update.message.reply_text(_("customer.receipt.sent_to_support_fail"), reply_markup=get_customer_shop_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

async def warn_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Warns the user to send a photo, not text."""
    await update.message.reply_text(_("customer.receipt.invalid_input_warning"))
    return GET_RECEIPT_PHOTO

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the receipt upload conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(_("customer.receipt.upload_cancelled"))
        except BadRequest:
            pass
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=_("customer.receipt.back_to_shop_menu"), reply_markup=get_customer_shop_keyboard())
    context.user_data.clear()
    return ConversationHandler.END