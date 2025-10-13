# --- START OF FILE modules/customer/actions/receipt.py ---
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest
from shared.financial_utils import calculate_payment_details
from config import config
from database.crud import pending_invoice as crud_invoice
from shared.keyboards import get_customer_shop_keyboard
from shared.translator import _
from shared.callback_types import SendReceipt

LOGGER = logging.getLogger(__name__)

CHOOSE_INVOICE, GET_RECEIPT_PHOTO = range(2)

async def start_receipt_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    processing_message = await update.message.reply_text(_("customer.receipt.checking_invoices"), reply_markup=ReplyKeyboardRemove())
    
    pending_invoices = await crud_invoice.get_pending_invoices_for_user(user_id)
    await processing_message.delete()

    if not pending_invoices:
        await update.message.reply_text(_("customer.receipt.no_pending_invoices"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    if len(pending_invoices) == 1:
        invoice = pending_invoices[0]
        context.user_data['invoice_id'] = invoice.invoice_id
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
        await update.message.reply_text(
            text=_("customer.receipt.single_invoice_prompt", price=f"{invoice.price:,.0f}"),
            reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return GET_RECEIPT_PHOTO
    
    else:
        buttons = []
        text = _("customer.receipt.multiple_invoices_prompt")
        for inv in pending_invoices:
            plan_desc = inv.plan_details.get('username') or inv.plan_details.get('plan_name') or f"Invoice #{inv.invoice_id}"
            btn_text = _("customer.receipt.invoice_button_format", 
                         id=inv.invoice_id,  
                         description=plan_desc,
                         price=f"{inv.price:,.0f}")
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_invoice_{inv.invoice_id}")])
        
        buttons.append([InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text=text, reply_markup=keyboard)
        return CHOOSE_INVOICE

async def start_receipt_from_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    callback_obj = SendReceipt.from_string(query.data)
    if not callback_obj:
        LOGGER.error(f"Could not parse SendReceipt callback for user {update.effective_user.id}. Data: {query.data}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=_("customer.receipt.invoice_id_parse_error"))
        return ConversationHandler.END

    context.user_data['invoice_id'] = callback_obj.invoice_id
    LOGGER.info(f"User {update.effective_user.id} started receipt upload for invoice #{callback_obj.invoice_id} from an inline button.")
    
    try: await query.message.delete()
    except Exception: pass

    text_prompt = _("customer.receipt.photo_prompt_simple")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")]
    ])
    
    try:
        with open("assets/receipt_guide.png", "rb") as photo_file:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_file, caption=text_prompt, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        LOGGER.warning("assets/receipt_guide.png not found. Sending text fallback.")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text_prompt, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    
    return GET_RECEIPT_PHOTO

async def select_invoice_for_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try:
        invoice_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.answer(_("general.errors.internal_error"), show_alert=True)
        return ConversationHandler.END

    context.user_data['invoice_id'] = invoice_id
    await query.answer()
    
    try: await query.message.delete()
    except Exception: pass

    text_prompt = _("customer.receipt.photo_prompt_simple")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
    
    try:
        with open("assets/receipt_guide.png", "rb") as photo_file:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_file, caption=text_prompt, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        LOGGER.warning("assets/receipt_guide.png not found. Sending text fallback.")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text_prompt, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    invoice_id = context.user_data.get('invoice_id')

    if not invoice_id:
        await update.message.reply_text(_("customer.receipt.internal_error_start_over"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END
        
    invoice = await crud_invoice.get_pending_invoice_by_id(invoice_id)
    if not invoice:
        await update.message.reply_text(_("customer.receipt.invoice_info_not_found"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    total_price = float(invoice.price)
    plan_details = invoice.plan_details

    payment_info = await calculate_payment_details(user.id, total_price)
    paid_from_wallet = payment_info["paid_from_wallet"]
    payable_amount = payment_info["payable_amount"]
    
    # Build caption parts
    caption = _("customer.receipt.admin_caption_title", invoice_id=invoice_id)
    caption += _("customer.receipt.admin_caption_user", full_name=user.full_name, user_id=f"`{user.id}`")

    # Add plan details section
    caption += _("customer.receipt.admin_caption_plan_details_title")
    if plan_details.get('invoice_type') == 'WALLET_CHARGE':
        caption += _("customer.receipt.admin_caption_plan_wallet", amount=f"{plan_details.get('amount', 0):,.0f}")
    else:
        username = plan_details.get('marzban_username') or plan_details.get('username', 'N/A')
        volume = plan_details.get('data_limit_gb') or plan_details.get('volume', 'N/A')
        duration = plan_details.get('renewal_days') or plan_details.get('duration', 'N/A')
        caption += _("customer.receipt.admin_caption_plan_service", username=username, volume=volume, duration=duration)

    # Add financial details section
    caption += _("customer.receipt.admin_caption_financial_details_title")
    caption += _("customer.receipt.admin_caption_financial_total", price=f"{total_price:,.0f}")
    if paid_from_wallet > 0:
        caption += _("customer.receipt.admin_caption_financial_wallet", amount=f"{paid_from_wallet:,.0f}")
    caption += _("customer.receipt.admin_caption_financial_payable", amount=f"{payable_amount:,.0f}")

    caption += _("customer.receipt.admin_caption_footer")
        
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_("keyboards.buttons.approve_payment"), callback_data=f"approve_receipt_{invoice_id}"),
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
    await update.message.reply_text(_("customer.receipt.invalid_input_warning"))
    return GET_RECEIPT_PHOTO

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(_("customer.receipt.upload_cancelled"))
        except BadRequest:
            pass
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=_("customer.receipt.back_to_shop_menu"), reply_markup=get_customer_shop_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# --- END OF FILE modules/customer/actions/receipt.py ---