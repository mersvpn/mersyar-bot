# FILE: modules/payment/actions/approval.py (FULLY CONVERTED, NO DELETIONS)

import qrcode
import io
import logging
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from decimal import Decimal

from modules.marzban.actions.api import get_user_data, add_data_to_user_api, reset_user_traffic_api, modify_user_api
from modules.marzban.actions.constants import GB_IN_BYTES
from database.crud import (
    pending_invoice as crud_invoice,
    marzban_link as crud_marzban_link,
    user as crud_user,
    user_note as crud_user_note
)
from modules.marzban.actions.add_user import create_marzban_user_from_template
from shared.translator import _
from shared.log_channel import send_log
from database.models.pending_invoice import PendingInvoice

LOGGER = logging.getLogger(__name__)


async def _approve_manual_invoice(context: ContextTypes.DEFAULT_TYPE, invoice: PendingInvoice, query: Update, admin_user):
    """
    Handles approval for manually created invoices.
    Its main job is to save the subscription details to the database.
    """
    customer_id = invoice.user_id
    plan_details = invoice.plan_details
    invoice_id = invoice.invoice_id

    username = plan_details.get('username')
    duration = plan_details.get('duration')
    volume = plan_details.get('volume')
    price = plan_details.get('price')

    if not all([username, duration is not None, volume is not None, price is not None]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_plan_details')}")
        return

    await crud_user_note.create_or_update_user_note(
        marzban_username=username,
        duration=duration,
        data_limit_gb=volume,
        price=price
    )
    LOGGER.info(f"Subscription details for '{username}' saved/updated from manual invoice #{invoice_id}.")

    await crud_invoice.update_invoice_status(invoice_id, 'approved')
    
    try:
        await context.bot.send_message(
            customer_id, 
            _("financials_payment.payment_approved_existing_user", id=invoice_id, username=username)
        )
    except Exception as e:
        LOGGER.error(f"Failed to send manual payment confirmation to customer {customer_id}: {e}")

    final_caption = f"{query.message.caption}{_('financials_payment.admin_log_payment_approved_existing', username=username, admin_name=admin_user.full_name)}"
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
    
    log_message = _("log.manual_invoice_approved", 
                    invoice_id=invoice_id, 
                    username=f"`{username}`", 
                    price=f"{int(price):,}",
                    customer_id=customer_id,
                    admin_name=admin_user.full_name)
    await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)


async def _approve_new_user_creation(context: ContextTypes.DEFAULT_TYPE, invoice: PendingInvoice, query: Update, admin_user):
    """Logic to create a new user in Marzban after payment approval."""
    customer_id = invoice.user_id
    plan_details = invoice.plan_details
    invoice_id = invoice.invoice_id
    
    marzban_username = plan_details.get('username')
    plan_type = plan_details.get("plan_type")
    duration_days = plan_details.get('duration')
    price = plan_details.get('price')
    max_ips = plan_details.get('max_ips')
    data_limit_gb = 0 if plan_type == "unlimited" else plan_details.get('volume')

    if not all([marzban_username, data_limit_gb is not None, duration_days, price is not None]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_plan_details')}")
        return

    try:
        new_user_data = await create_marzban_user_from_template(data_limit_gb=data_limit_gb, expire_days=duration_days, username=marzban_username, max_ips=max_ips)
        if not new_user_data or 'username' not in new_user_data:
            raise Exception("Failed to create user in Marzban, received empty response.")
    except Exception as e:
        LOGGER.error(f"Failed to create Marzban user for invoice #{invoice_id}: {e}", exc_info=True)
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_creating_user_in_marzban')}")
        return
    
    await crud_user_note.create_or_update_user_note(
        marzban_username=marzban_username,
        duration=duration_days,
        price=price,
        data_limit_gb=data_limit_gb
    )
    
    await crud_marzban_link.create_or_update_link(marzban_username, customer_id)
    await crud_invoice.update_invoice_status(invoice_id, 'approved')
    
    try:
        subscription_url = new_user_data.get('subscription_url')
        if subscription_url:
            qr_image = qrcode.make(subscription_url)
            bio = io.BytesIO(); bio.name = 'qrcode.png'; qr_image.save(bio, 'PNG'); bio.seek(0)
            
            volume_text = _("marzban_display.unlimited") if plan_type == "unlimited" else f"{data_limit_gb} گیگابایت"
            user_limit_text = _("financials_payment.user_creation_success_message_ips", ips=max_ips) if max_ips else ""
            
            caption = _("financials_payment.user_creation_success_message_title")
            caption += _("financials_payment.user_creation_success_message_username", username=f"`{marzban_username}`")
            caption += _("financials_payment.user_creation_success_message_volume", volume=volume_text)
            caption += _("financials_payment.user_creation_success_message_duration", duration=duration_days) + user_limit_text
            caption += _("financials_payment.user_creation_success_connection_intro")
            caption += f"\n`{subscription_url}`\n"
            caption += _("financials_payment.user_creation_success_link_guide")
            caption += _("financials_payment.user_creation_success_qr_guide")
            
            await context.bot.send_photo(chat_id=customer_id, photo=bio, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(customer_id, _("financials_payment.user_creation_fallback_message", username=f"`{marzban_username}`"), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        LOGGER.error(f"Failed to send success message to customer {customer_id} for invoice #{invoice_id}: {e}", exc_info=True)
    
    final_caption = f"{query.message.caption}{_('financials_payment.admin_log_user_created', username=f'`{marzban_username}`', admin_name=admin_user.full_name)}"
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
    
    volume_text_log = _("marzban_display.unlimited") if data_limit_gb == 0 else f"{data_limit_gb} GB"
    log_message = _("log.new_user_approved",
                    invoice_id=invoice_id,
                    username=f"`{marzban_username}`",
                    volume=volume_text_log,
                    duration=duration_days,
                    price=f"{int(price):,}",
                    customer_id=customer_id,
                    admin_name=admin_user.full_name)
    await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)


async def _approve_renewal(context: ContextTypes.DEFAULT_TYPE, invoice: PendingInvoice, query: Update, admin_user):
    """
    Logic to renew an existing user's subscription AFTER payment approval.
    """
    customer_id = invoice.user_id
    plan_details = invoice.plan_details
    invoice_id = invoice.invoice_id
    
    username = plan_details.get('username')
    # --- ✨ FIX: Read duration and volume from plan_details, with fallback to user_note ---
    note_data = await crud_user_note.get_user_note(username)
    renewal_days = plan_details.get('duration')
    if renewal_days is None and note_data:
        renewal_days = note_data.subscription_duration

    data_limit_gb = plan_details.get('volume')
    if data_limit_gb is None and note_data:
        data_limit_gb = note_data.subscription_data_limit_gb
    
    data_limit_gb = data_limit_gb or 0 # Ensure it's not None
    # --- END OF FIX ---
    price = invoice.price

    if not all([username, renewal_days is not None, data_limit_gb is not None]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_plan_details')}")
        return

    user_data = await get_user_data(username)
    if not user_data:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('marzban_display.user_not_found')}")
        return

    success_reset, msg_reset = await reset_user_traffic_api(username)
    if not success_reset:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('marzban_modify_user.renew_error_reset_traffic', error=msg_reset)}")
        return

    start_date = datetime.datetime.fromtimestamp(max(user_data.get('expire') or 0, datetime.datetime.now().timestamp()))
    new_expire_date = start_date + datetime.timedelta(days=renewal_days)
    payload = {"expire": int(new_expire_date.timestamp()), "data_limit": int(data_limit_gb * GB_IN_BYTES), "status": "active"}
    
    success_modify, msg_modify = await modify_user_api(username, payload)
    if not success_modify:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('marzban_modify_user.renew_error_modify', error=msg_modify)}")
        return

    await crud_invoice.update_invoice_status(invoice_id, 'approved')
    
    try:
        await context.bot.send_message(
            customer_id,
            _("financials_payment.renewal_success_customer", 
              username=f"`{username}`", days=renewal_days, gb=data_limit_gb)
        )
    except Exception as e:
        LOGGER.error(f"Failed to send renewal confirmation to customer {customer_id}: {e}")

    final_caption = f"{query.message.caption}{_('financials_payment.admin_log_renewal_success', username=f'`{username}`', admin_name=admin_user.full_name)}"
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
    
    volume_text_log = _("marzban_display.unlimited") if data_limit_gb == 0 else f"{data_limit_gb} GB"
    log_message = _("log.renewal_approved",
                    invoice_id=invoice_id,
                    username=f"`{username}`",
                    volume=volume_text_log,
                    duration=renewal_days,
                    price=f"{int(price):,}",
                    customer_id=customer_id,
                    admin_name=admin_user.full_name)
    await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)


async def _approve_wallet_charge(context: ContextTypes.DEFAULT_TYPE, invoice: PendingInvoice, query: Update, admin_user):
    """Logic to increase a user's wallet balance after payment."""
    customer_id = invoice.user_id
    amount_to_add = Decimal(invoice.price)
    invoice_id = invoice.invoice_id

    new_balance = await crud_user.increase_wallet_balance(user_id=customer_id, amount=amount_to_add)

    if new_balance is not None:
        await crud_invoice.update_invoice_status(invoice_id, 'approved')
        try:
            await context.bot.send_message(
                customer_id,
                _("financials_payment.wallet_charge_success_customer", 
                  amount=f"{int(amount_to_add):,}", new_balance=f"{int(new_balance):,}")
            )
        except Exception as e:
            LOGGER.error(f"Failed to send wallet charge confirmation to customer {customer_id}: {e}")
        
        final_caption = f"{query.message.caption}{_('financials_payment.admin_log_wallet_charge_success', amount=f'{int(amount_to_add):,}', admin_name=admin_user.full_name)}"
        await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
        
        log_message = _("log.wallet_charge_approved",
                        invoice_id=invoice_id,
                        amount=f"{int(amount_to_add):,}",
                        customer_id=customer_id,
                        admin_name=admin_user.full_name)
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_updating_wallet_db')}")


async def _approve_data_top_up(context: ContextTypes.DEFAULT_TYPE, invoice: PendingInvoice, query: Update, admin_user):
    """Logic to add data to an existing user's plan."""
    customer_id = invoice.user_id
    plan_details = invoice.plan_details
    marzban_username = plan_details.get('username')
    data_gb_to_add = plan_details.get('volume')
    price = invoice.price
    invoice_id = invoice.invoice_id

    if not all([marzban_username, data_gb_to_add, customer_id]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_top_up_details')}")
        return

    success, message = await add_data_to_user_api(marzban_username, data_gb_to_add)

    if success:
        await crud_invoice.update_invoice_status(invoice_id, 'approved')
        LOGGER.info(f"Admin {admin_user.id} approved data top-up for '{marzban_username}' (Invoice #{invoice_id}).")
        
        try:
            await context.bot.send_message(customer_id, _("financials_payment.data_top_up_customer_success", id=f"`{invoice_id}`", gb=f"**{data_gb_to_add}**"))
        except Exception as e:
            LOGGER.error(f"Failed to send data top-up confirmation to customer {customer_id}: {e}")

        final_caption = f"{query.message.caption}{_('financials_payment.admin_log_data_top_up_success', username=f'`{marzban_username}`', admin_name=admin_user.full_name)}"
        await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
        
        log_message = _("log.data_topup_approved",
                        invoice_id=invoice_id,
                        username=f"`{marzban_username}`",
                        volume=data_gb_to_add,
                        price=f"{int(price):,}",
                        customer_id=customer_id,
                        admin_name=admin_user.full_name)
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)
    else:
        LOGGER.error(f"Failed to add data for '{marzban_username}' via API. Reason: {message}")
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_marzban_connection', error=message)}")


async def _approve_legacy(context: ContextTypes.DEFAULT_TYPE, invoice: PendingInvoice, query: Update, admin_user):
    """Fallback approval logic for old invoices without a specific type."""
    LOGGER.warning(f"Approving invoice #{invoice.invoice_id} using legacy method.")
    await _approve_manual_invoice(context, invoice, query, admin_user)


async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, auto_approved: bool = False) -> None:
    """
    Main handler for approving a payment. It reads the invoice type and delegates
    to the appropriate helper function defined above.
    """
    query = update.callback_query
    admin_user = update.effective_user
    if query.message:
        await query.answer(_("financials_payment.processing_approval"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        if query.message:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_invalid_invoice_number')}")
        return

    invoice = await crud_invoice.get_pending_invoice_by_id(invoice_id)
    if not invoice or invoice.status != 'pending':
        if query.message:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}")
        return

# --- START: Wallet deduction logic for admin approvals ---
    if not auto_approved and invoice.from_wallet_amount > 0:
        new_balance = await crud_user.decrease_wallet_balance(user_id=invoice.user_id, amount=invoice.from_wallet_amount)
        if new_balance is None:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_insufficient_funds_on_approval')}")
            return
    # --- END: Wallet deduction logic ---

    plan_details = invoice.plan_details
    invoice_type = plan_details.get("invoice_type")

    if invoice_type == "WALLET_CHARGE":
        await _approve_wallet_charge(context, invoice, query, admin_user)
    elif invoice_type == "MANUAL_INVOICE":
        await _approve_manual_invoice(context, invoice, query, admin_user)
    elif invoice_type == "DATA_TOP_UP":
        await _approve_data_top_up(context, invoice, query, admin_user)
    elif invoice_type in ["NEW_USER_CUSTOM", "NEW_USER_UNLIMITED"]:
        await _approve_new_user_creation(context, invoice, query, admin_user)
    elif invoice_type == "RENEWAL":
        await _approve_renewal(context, invoice, query, admin_user)
    else: 
        await _approve_legacy(context, invoice, query, admin_user)


async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the rejection of a payment receipt."""
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_rejection"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        if query.message:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('errors.internal_error')}")
        return

    invoice = await crud_invoice.get_pending_invoice_by_id(invoice_id)
    if not invoice or invoice.status != 'pending':
        if query.message:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}")
        return

    await crud_invoice.update_invoice_status(invoice.invoice_id, 'rejected')
        
    LOGGER.info(f"Admin {admin_user.id} rejected payment for invoice #{invoice.invoice_id}.")
    
    try:
        await context.bot.send_message(invoice.user_id, _("financials_payment.payment_rejected_customer_message", id=invoice.invoice_id))
    except Exception as e:
        LOGGER.error(f"Failed to send rejection notification to customer {invoice.user_id}: {e}")

    final_caption = f"{query.message.caption}{_('financials_payment.admin_log_payment_rejected', admin_name=admin_user.full_name)}"
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)

    log_message = _("log.payment_rejected",
                    invoice_id=invoice.invoice_id,
                    customer_id=invoice.user_id,
                    admin_name=admin_user.full_name)
    await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)


async def confirm_manual_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is now a general entry point for any `approve` button.
    It simply delegates to the main `approve_payment` handler.
    This simplifies the handler registration.
    """
    await approve_payment(update, context)