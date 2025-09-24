# FILE: modules/payment/actions/approval.py

import qrcode
import io
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from modules.marzban.actions.api import get_user_data, add_data_to_user_api
from database.db_manager import (
    get_pending_invoice, update_invoice_status,
    link_user_to_telegram, increase_wallet_balance
)
from shared.keyboards import get_admin_main_menu_keyboard
from modules.marzban.actions.add_user import create_marzban_user_from_template
from shared.translator import _

LOGGER = logging.getLogger(__name__)


async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main handler for approving a payment. It reads the invoice type and delegates
    to the appropriate function.
    """
    query = update.callback_query
    admin_user = update.effective_user
    # For wallet payments, we don't have a message to edit, so we check.
    if query.message:
        await query.answer(_("financials_payment.processing_approval"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        if query.message:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_invalid_invoice_number')}")
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        if query.message:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}")
        return

    # --- MAIN LOGIC: Delegate based on invoice type ---
    plan_details = invoice.get('plan_details', {})
    
    # Here you should define clear 'invoice_type's when creating invoices.
    # e.g., 'NEW_USER_CUSTOM', 'RENEWAL', 'WALLET_CHARGE', 'DATA_TOP_UP'
    invoice_type = plan_details.get("invoice_type")

    if invoice_type == "WALLET_CHARGE":
        await _approve_wallet_charge(context, invoice, query, admin_user)
    elif invoice_type == "DATA_TOP_UP":
        await _approve_data_top_up(context, invoice, query, admin_user)
    elif invoice_type in ["NEW_USER_CUSTOM", "NEW_USER_UNLIMITED"]:
        await _approve_new_user_creation(context, invoice, query, admin_user)
    elif invoice_type == "RENEWAL":
        # We need to implement the renewal logic here.
        # For now, let's add a placeholder.
        await _approve_renewal(context, invoice, query, admin_user)
    else: # Fallback for older or undefined invoices
        await _approve_legacy(context, invoice, query, admin_user)


async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the rejection of a payment receipt."""
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_rejection"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('errors.internal_error')}")
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}")
        return

    if not await update_invoice_status(invoice_id, 'rejected'):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_updating_invoice_db')}")
        return
        
    LOGGER.info(f"Admin {admin_user.id} rejected payment for invoice #{invoice_id}.")
    
    try:
        await context.bot.send_message(invoice['user_id'], _("financials_payment.payment_rejected_customer_message", id=invoice_id))
    except Exception as e:
        LOGGER.error(f"Failed to send rejection notification to customer {invoice['user_id']}: {e}")

    await query.edit_message_caption(caption=f"{query.message.caption}{_('financials_payment.admin_log_payment_rejected', admin_name=admin_user.full_name)}", parse_mode=ParseMode.MARKDOWN)

# --- Private Helper Functions for Approval ---

async def _approve_new_user_creation(context, invoice, query, admin_user):
    """Logic to create a new user in Marzban after payment approval."""
    customer_id = invoice['user_id']
    plan_details = invoice.get('plan_details', {})
    invoice_id = invoice['id']
    
    marzban_username = plan_details.get('username')
    plan_type = plan_details.get("plan_type")
    duration_days = plan_details.get('duration')
    price = invoice.get('price')
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
    
    # --- START OF THE MISSING LOGIC ---
    from database.db_manager import save_subscription_note
    if price > 0 and duration_days > 0:
        try:
            await save_subscription_note(username=marzban_username, duration=duration_days, price=price, data_limit_gb=data_limit_gb)
        except Exception as e:
            LOGGER.error(f"CRITICAL: Failed to save subscription note for '{marzban_username}': {e}", exc_info=True)
    
    await link_user_to_telegram(marzban_username, customer_id)
    await update_invoice_status(invoice_id, 'approved')
    
    try:
        subscription_url = new_user_data.get('subscription_url')
        if subscription_url:
            qr_image = qrcode.make(subscription_url)
            bio = io.BytesIO()
            bio.name = 'qrcode.png'; qr_image.save(bio, 'PNG'); bio.seek(0)
            
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
    
    # Optionally send a confirmation to admin's private chat
    try:
        await context.bot.send_message(admin_user.id, _("financials_payment.admin_confirm_user_created"), reply_markup=get_admin_main_menu_keyboard())
    except Exception as e:
        LOGGER.warning(f"Could not send private confirmation to admin {admin_user.id}: {e}")
    # --- END OF THE MISSING LOGIC ---
async def _approve_renewal(context, invoice, query, admin_user):
    """Logic to renew an existing user's subscription."""
    # This needs to be implemented. It would call renew_user_subscription_api
    # from modules.marzban.actions.api
    pass

async def _approve_wallet_charge(context, invoice, query, admin_user):
    """Logic to increase a user's wallet balance after payment."""
    customer_id = invoice['user_id']
    amount_to_add = float(invoice.get('plan_details', {}).get("amount", invoice.get('price', 0)))

    new_balance = await increase_wallet_balance(user_id=customer_id, amount=amount_to_add)

    if new_balance is not None:
        await update_invoice_status(invoice['id'], 'approved')
        try:
            await context.bot.send_message(
                customer_id,
                _("financials_payment.wallet_charge_success_customer", 
                  amount=f"{int(amount_to_add):,}", 
                  new_balance=f"{int(new_balance):,}")
            )
        except Exception as e:
            LOGGER.error(f"Failed to send wallet charge confirmation to customer {customer_id}: {e}")
        
        final_caption = f"{query.message.caption}{_('financials_payment.admin_log_wallet_charge_success', amount=f'{int(amount_to_add):,}', admin_name=admin_user.full_name)}"
        await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_updating_wallet_db')}")

async def _approve_data_top_up(context, invoice, query, admin_user):
    """Logic to add data to an existing user's plan."""
    plan_details, customer_id = invoice.get('plan_details', {}), invoice.get('user_id')
    marzban_username, data_gb_to_add = plan_details.get('username'), plan_details.get('volume')
    invoice_id = invoice['id']

    if not all([marzban_username, data_gb_to_add, customer_id]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_top_up_details')}")
        return

    success, message = await add_data_to_user_api(marzban_username, data_gb_to_add)

    if success:
        await update_invoice_status(invoice_id, 'approved')
        LOGGER.info(f"Admin {admin_user.id} approved data top-up for '{marzban_username}' (Invoice #{invoice_id}).")
        
        try:
            await context.bot.send_message(customer_id, _("financials_payment.data_top_up_customer_success", id=f"`{invoice_id}`", gb=f"**{data_gb_to_add}**"))
        except Exception as e:
            LOGGER.error(f"Failed to send data top-up confirmation to customer {customer_id}: {e}")

        await query.edit_message_caption(caption=f"{query.message.caption}{_('financials_payment.admin_log_data_top_up_success', username=f'`{marzban_username}`', admin_name=admin_user.full_name)}", parse_mode=ParseMode.MARKDOWN)
    else:
        LOGGER.error(f"Failed to add data for '{marzban_username}' via API. Reason: {message}")
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_marzban_connection', error=message)}")


async def _approve_legacy(context, invoice, query, admin_user):
    """Fallback approval logic for old invoices without a specific type."""
    LOGGER.warning(f"Approving invoice #{invoice['id']} using legacy method.")
    
    # --- START OF THE MISSING LOGIC ---
    customer_id, plan_details = invoice['user_id'], invoice.get('plan_details', {})
    invoice_id = invoice['id']

    marzban_username = plan_details.get('username')
    if not marzban_username:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_username_not_in_invoice')}")
        return

    existing_user = await get_user_data(marzban_username)

    # Scenario 1: User already exists in Marzban -> This is a renewal or manual payment
    if existing_user and "error" not in existing_user:
        # Here we should ideally call the _approve_renewal logic, but for legacy, we just approve.
        await update_invoice_status(invoice_id, 'approved')
        try:
            await context.bot.send_message(customer_id, _("financials_payment.payment_approved_existing_user", id=invoice_id, username=marzban_username))
        except Exception as e:
            LOGGER.error(f"Failed to send manual payment confirmation to customer {customer_id}: {e}")
        
        final_caption = f"{query.message.caption}{_('financials_payment.admin_log_payment_approved_existing', username=marzban_username, admin_name=admin_user.full_name)}"
        await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
        return

    # Scenario 2: User does not exist -> This is a new user creation
    # We delegate this to the proper function we already have.
    await _approve_new_user_creation(context, invoice, query, admin_user)
    # --- END OF THE MISSING LOGIC ---

    # FILE: modules/payment/actions/approval.py
# ADD THIS ENTIRE FUNCTION TO THE END OF THE FILE

async def confirm_manual_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles approval for invoices that don't trigger a Marzban action,
    like wallet charges or manually created invoices for existing services.
    """
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_approval"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('errors.internal_error')}")
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}")
        return
    
    # Check if this is a wallet charge invoice
    if invoice.get('plan_details', {}).get("invoice_type") == "WALLET_CHARGE":
        # If it is, delegate to the specific wallet charge approval function
        await _approve_wallet_charge(context, invoice, query, admin_user)
        return

    # Otherwise, it's a generic manual payment approval
    await update_invoice_status(invoice['id'], 'approved')
    LOGGER.info(f"Admin {admin_user.id} confirmed payment for manual invoice #{invoice['id']}.")
    
    try:
        username = invoice.get('plan_details', {}).get('username', '')
        await context.bot.send_message(
            invoice['user_id'], 
            _("financials_payment.payment_approved_existing_user", id=invoice['id'], username=username)
        )
    except Exception as e:
        LOGGER.error(f"Failed to send manual payment confirmation to customer {invoice['user_id']}: {e}")

    final_caption = f"{query.message.caption}{_('financials_payment.admin_log_payment_approved_existing', username=username, admin_name=admin_user.full_name)}"
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)