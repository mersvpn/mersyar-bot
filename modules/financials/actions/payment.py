# FILE: modules/financials/actions/payment.py (REVISED FOR I18N and BEST PRACTICES)
import qrcode
import io
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from modules.marzban.actions.api import add_data_to_user_api
from database.db_manager import (
    load_financials, get_pending_invoice, update_invoice_status,
    link_user_to_telegram, get_user_note, get_telegram_id_from_marzban_username,
    create_pending_invoice,
    create_pending_invoice, get_user_wallet_balance
)
from shared.keyboards import get_admin_main_menu_keyboard
from modules.general.actions import send_main_menu, start as back_to_main_menu_action
from config import config
from modules.marzban.actions.add_user import create_marzban_user_from_template

LOGGER = logging.getLogger(__name__)

GET_PRICE = 0

async def start_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    if not update.effective_user or update.effective_user.id not in config.AUTHORIZED_USER_IDS:
        if query: await query.answer(_("financials_payment.access_denied"), show_alert=True)
        return ConversationHandler.END

    await query.answer()
    
    try:
        prefix, customer_id, marzban_username = query.data.split(':', 2)
        if prefix != "fin_send_req": raise ValueError("Invalid callback data")
    except (ValueError, IndexError):
        LOGGER.error(f"Invalid callback data for payment request: {query.data}")
        await query.edit_message_text(_("financials_payment.invalid_callback_data"))
        return ConversationHandler.END
        
    context.user_data['payment_info'] = {'customer_id': int(customer_id), 'marzban_username': marzban_username}
    
    await query.edit_message_text(
        text=_("financials_payment.manual_invoice_prompt", username=f"`{marzban_username}`"),
        parse_mode=ParseMode.MARKDOWN
    )
    return GET_PRICE

async def send_payment_details_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    payment_info = context.user_data.get('payment_info')
    if not payment_info:
        await update.message.reply_text(_("financials_payment.error_user_info_lost"))
        return ConversationHandler.END
        
    customer_id, marzban_username = payment_info['customer_id'], payment_info['marzban_username']
    
    try:
        price_int = int(update.message.text.strip())
        if price_int <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_payment.invalid_price_input"))
        return GET_PRICE
        
    financials = await load_financials()
    if not financials.get("card_holder") or not financials.get("card_number"):
        await update.message.reply_text(_("financials_payment.error_financials_not_set"), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    user_note = await get_user_note(marzban_username)
    if not user_note:
        await update.message.reply_text(_("financials_payment.error_subscription_info_not_found", username=f"`{marzban_username}`"))
        return ConversationHandler.END

    plan_details = {
        'username': marzban_username,
        'volume': user_note.get('subscription_data_limit_gb', 0),
        'duration': user_note.get('subscription_duration', 0)
    }

    invoice_id = await create_pending_invoice(customer_id, plan_details, price_int)
    if not invoice_id:
        await update.message.reply_text(_("financials_payment.error_creating_invoice_db"))
        return ConversationHandler.END

    LOGGER.info(f"Created pending invoice #{invoice_id} for manually added user '{marzban_username}'.")

    try:
        payment_message = _("financials_payment.invoice_title_subscription")
        payment_message += _("financials_payment.invoice_number", id=invoice_id)
        payment_message += _("financials_payment.invoice_service", username=f"`{marzban_username}`")
        payment_message += _("financials_payment.invoice_price", price=f"`{price_int:,}`")
        # کد صحیح
        payment_message += _("financials_payment.invoice_payment_details", card_number=financials['card_number'], card_holder=financials['card_holder'])
        payment_message += _("financials_payment.invoice_footer_prompt")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")],
            [InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")]
        ])
        
        await context.bot.send_message(chat_id=customer_id, text=payment_message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        await update.message.reply_text(_("financials_payment.invoice_sent_to_user_success", id=invoice_id, customer_id=customer_id))
    except Exception as e:
        LOGGER.error(f"Failed to send payment details to customer {customer_id}: {e}", exc_info=True)
        await update.message.reply_text(_("financials_payment.error_sending_message_to_customer"))
    
    context.user_data.clear()
    await update.message.reply_text(_("financials_payment.back_to_main_menu"), reply_markup=get_admin_main_menu_keyboard())
    return ConversationHandler.END

async def cancel_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    await update.message.reply_text(_("financials_payment.manual_invoice_cancelled"), reply_markup=get_admin_main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

payment_request_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_payment_request, pattern=r'^fin_send_req:')],
    states={GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_payment_details_to_user)]},
    fallbacks=[CommandHandler('cancel', cancel_payment_request), CommandHandler('start', back_to_main_menu_action)],
    conversation_timeout=300, per_user=True, per_chat=True
)

async def send_renewal_invoice_to_user(context: ContextTypes.DEFAULT_TYPE, user_telegram_id: int, username: str, renewal_days: int, price: int, data_limit_gb: int):
    from shared.translator import _
    try:
        financials = await load_financials()
        if not financials.get("card_holder") or not financials.get("card_number"):
            LOGGER.error(f"Cannot send renewal invoice to {username}: Financial settings not configured."); return

        plan_details = {'username': username, 'volume': data_limit_gb, 'duration': renewal_days}
        invoice_id = await create_pending_invoice(user_telegram_id, plan_details, price)
        if not invoice_id:
            LOGGER.error(f"Failed to create renewal invoice for {username}."); return

        invoice_text = _("financials_payment.invoice_title_renewal")
        invoice_text += _("financials_payment.invoice_number", id=invoice_id)
        invoice_text += _("financials_payment.invoice_service", username=f"`{username}`")
        invoice_text += _("financials_payment.invoice_renewal_period", days=renewal_days)
        invoice_text += _("financials_payment.invoice_price", price=f"`{price:,}`")
        invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{financials['card_number']}`", card_holder=f"`{financials['card_holder']}`")
        invoice_text += _("financials_payment.invoice_footer_prompt")
        
        # === START: WALLET PAYMENT BUTTON LOGIC ===
        user_id = user_telegram_id # The variable name is different here
        
        keyboard_rows = [
            [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")]
        ]
        
        user_balance = await get_user_wallet_balance(user_id)
        if user_balance is not None and user_balance >= price: # `price` is available here
            wallet_button_text = _("financials_payment.button_pay_with_wallet", balance=f"{int(user_balance):,}")
            keyboard_rows.insert(0, [
                InlineKeyboardButton(wallet_button_text, callback_data=f"wallet_pay_{invoice_id}")
            ])

        keyboard_rows.append([InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")])
        keyboard = InlineKeyboardMarkup(keyboard_rows)
        # === END: WALLET PAYMENT BUTTON LOGIC ===

        await context.bot.send_message(chat_id=user_telegram_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Renewal invoice #{invoice_id} sent to user {username} ({user_telegram_id}).")
    except TelegramError as e:
        if "bot was blocked" in str(e).lower(): LOGGER.warning(f"Could not send renewal invoice to {user_telegram_id}: User blocked the bot.")
        else: LOGGER.error(f"Telegram error sending renewal invoice to {user_telegram_id}: {e}", exc_info=True)
    except Exception as e:
        LOGGER.error(f"Unexpected error in send_renewal_invoice_to_user for {username}: {e}", exc_info=True)

async def handle_payment_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    query = update.callback_query
    await query.answer()
    await send_main_menu(update, context, message_text=_("financials_payment.back_to_main_menu"))

async def send_manual_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    query = update.callback_query
    await query.answer()
    username = query.data.split('_', 2)[-1]
    admin_chat_id = update.effective_chat.id
    try:
        customer_id = await get_telegram_id_from_marzban_username(username)
        if not customer_id:
         await context.bot.send_message(admin_chat_id, _("financials_payment.error_customer_telegram_not_found", username=f"`{username}`"), parse_mode=ParseMode.MARKDOWN); return
            
        note_data = await get_user_note(username)
        price, duration = note_data.get('subscription_price'), note_data.get('subscription_duration')
        
        if not price or not duration:
            callback_string = f"fin_send_req:{customer_id}:{username}"
            admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("financials_payment.button_create_send_invoice"), callback_data=callback_string)]])
            await context.bot.send_message(admin_chat_id, _("financials_payment.note_not_set_prompt_manual_invoice", username=f"`{username}`"), reply_markup=admin_keyboard, parse_mode=ParseMode.MARKDOWN); return

        financials = await load_financials()
        card_holder, card_number = financials.get("card_holder", "تنظیم نشده"), financials.get("card_number", "تنظیم نشده")
        if "تنظیم نشده" in [card_holder, card_number]:
            await context.bot.send_message(admin_chat_id, _("financials_payment.error_financials_not_set"), parse_mode=ParseMode.MARKDOWN); return

        plan_details = {'username': username, 'volume': note_data.get('subscription_data_limit_gb', 0), 'duration': duration}
        invoice_id = await create_pending_invoice(customer_id, plan_details, price)
        if not invoice_id:
            await context.bot.send_message(admin_chat_id, _("financials_payment.error_creating_invoice_db")); return

        invoice_text = _("financials_payment.invoice_title_subscription")
        invoice_text += _("financials_payment.invoice_number", id=invoice_id)
        invoice_text += _("financials_payment.invoice_service", username=f"`{username}`") + f"▫️ **دوره:** {duration} روزه\n"
        invoice_text += _("financials_payment.invoice_price", price=f"`{price:,}`")
        invoice_text += f"**پرداخت به:**\n - شماره کارت: `{card_number}`\n - به نام: `{card_holder}`\n\n"
        invoice_text += _("financials_payment.invoice_footer_prompt")
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")]])
        await context.bot.send_message(chat_id=customer_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        await context.bot.send_message(admin_chat_id, _("financials_payment.invoice_sent_to_user_success", id=invoice_id, customer_id=customer_id), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        LOGGER.error(f"Failed to send manual invoice for user {username}: {e}", exc_info=True)
        await context.bot.send_message(admin_chat_id, _("financials_payment.unknown_error"), parse_mode=ParseMode.MARKDOWN)

async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    from shared.translator import _
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_approval"))

    try: invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_invalid_invoice_number')}"); return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}"); return

    customer_id, plan_details = invoice['user_id'], invoice['plan_details']
     
    marzban_username = plan_details.get('username')
    if not marzban_username:
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_username_not_in_invoice')}"); return

    from modules.marzban.actions.api import get_user_data
    existing_user = await get_user_data(marzban_username)

    if existing_user and "error" not in existing_user:
        await update_invoice_status(invoice_id, 'approved')
        try: await context.bot.send_message(customer_id, _("financials_payment.payment_approved_existing_user", id=invoice_id, username=marzban_username))
        except Exception as e: LOGGER.error(f"Failed to send manual payment confirmation to customer {customer_id}: {e}")
        await query.edit_message_caption(caption=f"{query.message.caption}{_('financials_payment.admin_log_payment_approved_existing', username=marzban_username, admin_name=admin_user.full_name)}", parse_mode=ParseMode.MARKDOWN)
        return

    plan_type, duration_days, price, max_ips = plan_details.get("plan_type"), plan_details.get('duration'), plan_details.get('price'), plan_details.get('max_ips')
    data_limit_gb = 0 if plan_type == "unlimited" else plan_details.get('volume')

    if not all([data_limit_gb is not None, duration_days is not None, price is not None]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_plan_details')}"); return

    try:
        new_user_data = await create_marzban_user_from_template(data_limit_gb=data_limit_gb, expire_days=duration_days, username=marzban_username, max_ips=max_ips)
        if not new_user_data or 'username' not in new_user_data: raise Exception("Failed to create user in Marzban, received empty response.")
    except Exception as e:
        LOGGER.error(f"Failed to create Marzban user for invoice #{invoice_id}: {e}", exc_info=True)
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_creating_user_in_marzban')}"); return
    
    if price > 0 and duration_days > 0:
        from database.db_manager import save_subscription_note
        try: await save_subscription_note(username=marzban_username, duration=duration_days, price=price, data_limit_gb=data_limit_gb)
        except Exception as e: LOGGER.error(f"CRITICAL: Failed to save subscription note for '{marzban_username}': {e}", exc_info=True)
    
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
            caption += _("financials_payment.user_creation_success_message_footer", url=subscription_url)
            await context.bot.send_photo(chat_id=customer_id, photo=bio, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else: await context.bot.send_message(customer_id, _("financials_payment.user_creation_fallback_message", username=f"`{marzban_username}`"), parse_mode=ParseMode.MARKDOWN)
    except Exception as e: LOGGER.error(f"Failed to send success message to customer {customer_id} for invoice #{invoice_id}: {e}", exc_info=True)
    
    final_caption = f"{query.message.caption}{_('financials_payment.admin_log_user_created', username=f'`{marzban_username}`', admin_name=admin_user.full_name)}"
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(admin_user.id, _("financials_payment.admin_confirm_user_created"), reply_markup=get_admin_main_menu_keyboard())

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_rejection"))

    try: invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError): await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('errors.internal_error')}"); return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}"); return

    if not await update_invoice_status(invoice_id, 'rejected'):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_updating_invoice_db')}"); return
        
    LOGGER.info(f"Admin {admin_user.id} rejected payment for invoice #{invoice_id}.")
    
    try: await context.bot.send_message(invoice['user_id'], _("financials_payment.payment_rejected_customer_message", id=invoice_id))
    except Exception as e: LOGGER.error(f"Failed to send rejection notification to customer {invoice['user_id']}: {e}")

    await query.edit_message_caption(caption=f"{query.message.caption}{_('financials_payment.admin_log_payment_rejected', admin_name=admin_user.full_name)}", parse_mode=ParseMode.MARKDOWN)

async def send_custom_plan_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_details: dict, invoice_id: int):
    from shared.translator import _
    user_id = update.effective_user.id
    volume, duration, price = plan_details.get('volume'), plan_details.get('duration'), plan_details.get('price')
    
    if not all([volume, duration, price]):
        await context.bot.send_message(chat_id=user_id, text=_("financials_payment.error_processing_plan")); return

    financials = await load_financials()
    card_holder, card_number = financials.get("card_holder", "تنظیم نشده"), financials.get("card_number", "تنظیم نشده")
    if "تنظیم نشده" in [card_holder, card_number]:
        await context.bot.send_message(chat_id=user_id, text=_("financials_payment.invoice_generation_unavailable")); return

    invoice_text = _("financials_payment.invoice_title_custom_plan")
    invoice_text += _("financials_payment.invoice_number", id=invoice_id)
    invoice_text += _("financials_payment.invoice_custom_plan_volume", volume=volume)
    invoice_text += _("financials_payment.invoice_custom_plan_duration", duration=duration)
    invoice_text += "-------------------------------------\n"
    invoice_text += _("financials_payment.invoice_price", price=f"`{price:,.0f}`")
    invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{card_number}`", card_holder=f"`{card_holder}`")
    invoice_text += _("financials_payment.invoice_footer_prompt")
    
    # === START: WALLET PAYMENT BUTTON LOGIC ===
    user_id = update.effective_user.id # Get user_id from update
    price = plan_details.get('price')

    keyboard_rows = [
        [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")]
    ]
    
    user_balance = await get_user_wallet_balance(user_id)
    if user_balance is not None and user_balance >= price:
        wallet_button_text = _("financials_payment.button_pay_with_wallet", balance=f"{int(user_balance):,}")
        keyboard_rows.insert(0, [
            InlineKeyboardButton(wallet_button_text, callback_data=f"wallet_pay_{invoice_id}")
        ])

    keyboard_rows.append([InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    # === END: WALLET PAYMENT BUTTON LOGIC ===
    
    try:
        await context.bot.send_message(chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Custom plan invoice #{invoice_id} sent to user {user_id}.")
    except Exception as e:
        LOGGER.error(f"Failed to send custom plan invoice #{invoice_id} to user {user_id}: {e}", exc_info=True)
        try: await context.bot.send_message(chat_id=user_id, text=_("financials_payment.error_sending_invoice"))
        except Exception: pass

async def confirm_manual_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.db_manager import increase_wallet_balance
    from shared.translator import _
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_approval"))

    try: invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError): await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('errors.internal_error')}"); return

    invoice = await get_pending_invoice(invoice_id)

        # === START: NEW LOGIC FOR WALLET CHARGE ===
    if invoice and invoice.get('plan_details', {}).get("type") == "wallet_charge":
        customer_id = invoice['user_id']
        price = invoice.get('price', 0)
        amount_to_add = invoice.get('plan_details', {}).get("amount", price)
        new_balance = await increase_wallet_balance(user_id=customer_id, amount=float(amount_to_add))

        if new_balance is not None:
            await update_invoice_status(invoice_id, 'approved')
            
            try:
                await context.bot.send_message(
                    customer_id,
                    _("financials_payment.wallet_charge_success_customer", 
                      amount=f"{amount_to_add:,}", 
                      new_balance=f"{int(new_balance):,}")
                )
            except Exception as e:
                LOGGER.error(f"Failed to send wallet charge confirmation to customer {customer_id}: {e}")
            
            final_caption = f"{query.message.caption}{_('financials_payment.admin_log_wallet_charge_success', amount=f'{amount_to_add:,}', admin_name=admin_user.full_name)}"
            await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_updating_wallet_db')}")
        
        return # End of execution for wallet charge
    # === END: NEW LOGIC FOR WALLET CHARGE ===
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}"); return

    if not await update_invoice_status(invoice_id, 'approved'):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_updating_invoice_db')}"); return
        
    LOGGER.info(f"Admin {admin_user.id} confirmed payment for manual invoice #{invoice_id}.")
    
    try: await context.bot.send_message(invoice['user_id'], _("financials_payment.payment_approved_existing_user", id=invoice_id, username=""))
    except Exception as e: LOGGER.error(f"Failed to send manual payment confirmation to customer {invoice['user_id']}: {e}")

    await query.edit_message_caption(caption=f"{query.message.caption}{_('financials_payment.admin_log_payment_approved_existing', username='', admin_name=admin_user.full_name)}", parse_mode=ParseMode.MARKDOWN)

async def approve_data_top_up(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer(_("financials_payment.processing_add_data"))

    try: invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError): await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('errors.internal_error')}"); return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.invoice_already_processed')}"); return

    plan_details, customer_id = invoice.get('plan_details', {}), invoice.get('user_id')
    marzban_username, data_gb_to_add = plan_details.get('username'), plan_details.get('volume')

    if not all([marzban_username, data_gb_to_add, customer_id]):
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_incomplete_top_up_details')}"); return

    success, message = await add_data_to_user_api(marzban_username, data_gb_to_add)

    if success:
        await update_invoice_status(invoice_id, 'approved')
        LOGGER.info(f"Admin {admin_user.id} approved data top-up for '{marzban_username}' (Invoice #{invoice_id}).")
        
        try: await context.bot.send_message(customer_id, _("financials_payment.data_top_up_customer_success", id=f"`{invoice_id}`", gb=f"**{data_gb_to_add}**"))
        except Exception as e: LOGGER.error(f"Failed to send data top-up confirmation to customer {customer_id}: {e}")

        await query.edit_message_caption(caption=f"{query.message.caption}{_('financials_payment.admin_log_data_top_up_success', username=f'`{marzban_username}`', admin_name=admin_user.full_name)}", parse_mode=ParseMode.MARKDOWN)
    else:
        LOGGER.error(f"Failed to add data for '{marzban_username}' via API. Reason: {message}")
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n{_('financials_payment.error_marzban_connection', error=message)}")

       

async def send_wallet_charge_invoice(context: ContextTypes.DEFAULT_TYPE, user_id: int, invoice_id: int, amount: int):
    from shared.translator import _
    
    financials = await load_financials()
    card_holder, card_number = financials.get("card_holder"), financials.get("card_number")
    
    if not card_holder or not card_number:
        LOGGER.error(f"Cannot send wallet charge invoice to user {user_id}: Financials not set.")
        try:
            await context.bot.send_message(chat_id=user_id, text=_("financials_payment.invoice_generation_unavailable"))
        except Exception: pass
        return

    invoice_text = _("financials_payment.invoice_title_wallet_charge")
    invoice_text += _("financials_payment.invoice_number", id=invoice_id)
    invoice_text += "-------------------------------------\n"
    invoice_text += _("financials_payment.invoice_price", price=f"`{amount:,.0f}`")
    invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{card_number}`", card_holder=f"`{card_holder}`")
    invoice_text += _("financials_payment.invoice_footer_prompt")
    
    # === START: WALLET PAYMENT BUTTON LOGIC ===
    # It doesn't make sense to pay for a wallet charge from the wallet itself,
    # but we add the logic for completeness and future use cases.
    keyboard_rows = [
        [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")]
    ]
    
    user_balance = await get_user_wallet_balance(user_id)
    if user_balance is not None and user_balance >= amount: # Here the variable is `amount`
        wallet_button_text = _("financials_payment.button_pay_with_wallet", balance=f"{int(user_balance):,}")
        keyboard_rows.insert(0, [
            InlineKeyboardButton(wallet_button_text, callback_data=f"wallet_pay_{invoice_id}")
        ])

    keyboard_rows.append([InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    # === END: WALLET PAYMENT BUTTON LOGIC ===
    try:
        await context.bot.send_message(chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Wallet charge invoice #{invoice_id} for {amount:,} Tomans sent to user {user_id}.")
    except Exception as e:
        LOGGER.error(f"Failed to send wallet charge invoice #{invoice_id} to user {user_id}: {e}", exc_info=True)

async def pay_with_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    from database.db_manager import decrease_wallet_balance

    query = update.callback_query
    await query.answer(_("financials_payment.processing_wallet_payment"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        await query.edit_message_text(_("errors.internal_error"))
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_text(_("financials_payment.invoice_already_processed_simple"))
        return

    user_id = update.effective_user.id
    price = float(invoice.get('price', 0))

    new_balance = await decrease_wallet_balance(user_id=user_id, amount=price)

    if new_balance is not None:
        # Payment successful!
        await query.edit_message_text(
            _("financials_payment.wallet_payment_successful", 
              price=f"{int(price):,}", 
              new_balance=f"{int(new_balance):,}")
        )
        
        # Now, we need to trigger the same approval logic as the admin.
        # To do this safely, we will call the appropriate approval function.
        # We create a "mock" admin user for the logs.
        class MockUser:
            id = 0
            full_name = "پرداخت خودکار (کیف پول)"

        class MockQuery:
            data = f"approve_receipt_{invoice_id}" # This matches the admin's button
            message = None # Not needed for this flow
            async def answer(self, *args, **kwargs): pass
            async def edit_message_caption(self, *args, **kwargs): pass # We already edited the message
        
        class MockUpdate:
            effective_user = MockUser()
            callback_query = MockQuery()
            
        # IMPORTANT: Call the correct approval function
        await approve_payment(MockUpdate(), context)

    else:
        # Payment failed (insufficient funds)
        await query.answer(_("financials_payment.wallet_payment_failed_insufficient_funds"), show_alert=True)