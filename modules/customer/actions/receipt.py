# FILE: modules/customer/actions/receipt.py (REVISED FOR I18N)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import config
from database.db_manager import get_pending_invoices_for_user
from shared.keyboards import get_customer_shop_keyboard
from modules.general.actions import end_conversation_and_show_menu
from shared.translator import _

LOGGER = logging.getLogger(__name__)

CHOOSE_INVOICE, GET_RECEIPT_PHOTO = range(2)

async def start_receipt_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    processing_message = await update.message.reply_text(_("receipt.checking_invoices"), reply_markup=ReplyKeyboardRemove())
    
    pending_invoices = await get_pending_invoices_for_user(user_id)
    await processing_message.delete()

    if not pending_invoices:
        await update.message.reply_text(_("receipt.no_pending_invoices"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    if len(pending_invoices) == 1:
        invoice = pending_invoices[0]
        context.user_data['invoice_id'] = invoice['invoice_id']
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
        await update.message.reply_text(
            text=_("receipt.single_invoice_prompt", price=invoice['price']),
            reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        return GET_RECEIPT_PHOTO
    
    else:
        buttons = []
        text = _("receipt.multiple_invoices_prompt")
        for inv in pending_invoices:
            details = inv.get('plan_details', {})
            btn_text = _("receipt.invoice_button_format", 
                         id=inv['invoice_id'], 
                         volume=details.get('volume','N/A'), 
                         duration=details.get('duration','N/A'), 
                         price=inv.get('price', 0))
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"select_invoice_{inv['invoice_id']}")])
        
        buttons.append([InlineKeyboardButton(_("buttons.cancel_operation"), callback_data="cancel_receipt_upload")])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text=text, reply_markup=keyboard)
        return CHOOSE_INVOICE

async def start_receipt_from_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    message_text = query.message.text
    try:
        invoice_id_str = message_text.split("شماره فاکتور: `")[1].split("`")[0]
        invoice_id = int(invoice_id_str)
        context.user_data['invoice_id'] = invoice_id
    except (IndexError, ValueError):
        LOGGER.error(f"Could not parse invoice ID from message for user {update.effective_user.id}.")
        await query.edit_message_text(_("receipt.invoice_id_parse_error"))
        return ConversationHandler.END

    LOGGER.info(f"User {update.effective_user.id} started receipt upload for invoice #{invoice_id} from inline button.")
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
    await query.edit_message_text(
        text=_("receipt.photo_prompt_for_invoice", invoice_text=query.message.text),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return GET_RECEIPT_PHOTO

async def select_invoice_for_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try:
        invoice_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.answer(_("errors.internal_error"), show_alert=True)
        return ConversationHandler.END

    context.user_data['invoice_id'] = invoice_id
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("buttons.cancel_operation"), callback_data="cancel_receipt_upload")]])
    await query.edit_message_text(
        text=_("receipt.photo_prompt_for_invoice", invoice_text="").split('\n\n')[1], # Get the second part
        reply_markup=keyboard
    )
    return GET_RECEIPT_PHOTO

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    invoice_id = context.user_data.get('invoice_id')

    if not invoice_id:
        await update.message.reply_text(_("receipt.internal_error_start_over"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END
        
    from database.db_manager import get_pending_invoice
    invoice_details = await get_pending_invoice(invoice_id)
    if not invoice_details:
        await update.message.reply_text(_("receipt.invoice_info_not_found"), reply_markup=get_customer_shop_keyboard())
        return ConversationHandler.END

    plan = invoice_details.get('plan_details', {})
    price = invoice_details.get('price', 0)
    volume = plan.get('volume', 'N/A')
    duration = plan.get('duration', 'N/A')
    
    volume_str = _("receipt.unlimited_volume_label") if plan.get("plan_type") == "unlimited" else volume
    
    caption = _("receipt.admin_caption", 
                invoice_id=invoice_id, 
                full_name=user.full_name, 
                user_id=f"`{user.id}`", 
                volume=volume_str, 
                duration=duration, 
                price=price)

    plan_type = plan.get("plan_type")

    # ✨✨✨ KEY FIX HERE ✨✨✨
    # This logic now correctly routes all new service types (including unlimited)
    # to the powerful `approve_receipt` handler. The manual confirmation is
    # reserved ONLY for cases where volume/duration are literally zero (manual admin requests).

    if plan_type == "data_top_up":
        approve_button_text = _("buttons.approve_data_top_up")
        approve_callback = f"approve_data_top_up_{invoice_id}"
    # This covers custom plans, unlimited plans, and any other defined plan type
    elif plan_type in ["custom", "unlimited"] or (isinstance(volume, int) and volume > 0 and isinstance(duration, int) and duration > 0):
        approve_button_text = _("buttons.approve_and_create_service")
        approve_callback = f"approve_receipt_{invoice_id}"
    else:
        # This is now the fallback for truly manual payments where no service is being created
        approve_button_text = _("buttons.approve_payment")
        approve_callback = f"confirm_manual_receipt_{invoice_id}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(approve_button_text, callback_data=approve_callback),
            InlineKeyboardButton(_("buttons.reject"), callback_data=f"reject_receipt_{invoice_id}")
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
        await update.message.reply_text(_("receipt.sent_to_support_success"), reply_markup=get_customer_shop_keyboard())
    else:
        await update.message.reply_text(_("receipt.sent_to_support_fail"), reply_markup=get_customer_shop_keyboard())

    context.user_data.clear()
    return ConversationHandler.END

async def warn_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(_("receipt.invalid_input_warning"))
    return GET_RECEIPT_PHOTO

async def cancel_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(_("receipt.upload_cancelled"))
        except BadRequest:
            pass
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=_("receipt.back_to_shop_menu"), reply_markup=get_customer_shop_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

receipt_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex(f'^{_("keyboards.customer_shop.send_receipt")}$'), start_receipt_from_menu),
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
        MessageHandler(filters.Regex(f'^{_("keyboards.general.back_to_main_menu")}$'), end_conversation_and_show_menu)
    ],
    conversation_timeout=600 
)