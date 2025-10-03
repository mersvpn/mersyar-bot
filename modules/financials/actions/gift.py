# FILE: modules/financials/actions/gift.py (NEW FILE)

import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from database.db_manager import (
    save_welcome_gift_amount, load_welcome_gift_amount, 
    increase_balance_for_all_users, get_all_user_ids
)
from shared.keyboards import get_gift_management_keyboard
from shared.translator import _
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

# --- Conversation States ---
# For Welcome Gift
(MENU, GET_WELCOME_AMOUNT) = range(2)
# For Universal Gift
(GET_UNIVERSAL_AMOUNT, CONFIRM_UNIVERSAL_GIFT) = range(2, 4)


async def show_gift_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the main gift management menu."""
    query = update.callback_query
    await query.answer()

    welcome_amount = await load_welcome_gift_amount()
    
    if welcome_amount > 0:
        amount_str = _("financials_gift.welcome_gift_amount_set", amount=f"{welcome_amount:,}")
    else:
        amount_str = _("financials_gift.welcome_gift_not_set")

    text = _("financials_gift.menu_title", current_gift=amount_str)
    keyboard = get_gift_management_keyboard()

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return MENU

# =============================================================================
# 1. Welcome Gift Conversation
# =============================================================================

async def prompt_for_welcome_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the new welcome gift amount."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("financials_gift.prompt_welcome_gift"))
    return GET_WELCOME_AMOUNT

async def save_welcome_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the new welcome gift amount."""
    try:
        amount = int(update.message.text.strip())
        if amount < 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_gift.invalid_amount"))
        return GET_WELCOME_AMOUNT

    await save_welcome_gift_amount(amount)
    
    if amount > 0:
        feedback = _("financials_gift.welcome_gift_save_success", amount=f"{amount:,}")
    else:
        feedback = _("financials_gift.welcome_gift_disabled")
        
    await update.message.reply_text(feedback)
    
    # Go back to the main financial menu by simulating a callback
    from .settings import show_financial_menu
    query = context.user_data.get('financial_menu_query')
    await show_financial_menu(update, context, query_to_use=query)
    
    return ConversationHandler.END

# =============================================================================
# 2. Universal Gift Conversation
# =============================================================================

async def prompt_for_universal_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the universal gift amount."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("financials_gift.prompt_universal_gift"))
    return GET_UNIVERSAL_AMOUNT

async def prompt_for_gift_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for final confirmation by typing a keyword."""
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_gift.invalid_amount"))
        return GET_UNIVERSAL_AMOUNT

    context.user_data['universal_gift_amount'] = amount
    
    text = _("financials_gift.universal_gift_confirm_prompt", amount=f"{amount:,}", keyword=f"`{_('financials_gift.confirm_keyword')}`")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return CONFIRM_UNIVERSAL_GIFT

async def process_universal_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Applies the gift to all users and schedules the notification job."""
    confirmation = update.message.text.strip()
    if confirmation != _('financials_gift.confirm_keyword'):
        await update.message.reply_text(_("financials_gift.confirmation_failed"))
        # Go back to the main financial menu
        from .settings import show_financial_menu
        query = context.user_data.get('financial_menu_query')
        await show_financial_menu(update, context, query_to_use=query)
        return ConversationHandler.END

    amount = context.user_data.get('universal_gift_amount')
    admin_user = update.effective_user

    await update.message.reply_text(_("financials_gift.processing_universal_gift"))

    # Step 1: Update database (this is fast)
    affected_users_count = await increase_balance_for_all_users(amount)

    if affected_users_count is None:
        await update.message.reply_text(_("financials_gift.db_error"))
    elif affected_users_count > 0:
        # Step 2: Get user IDs for notification job
        user_ids = await get_all_user_ids()
        
        # Step 3: Schedule the background job
        context.job_queue.run_once(send_gift_notification_job, 1, 
                           data={'user_ids': user_ids, 'amount': amount}, 
                           name=f"universal_gift_{update.effective_chat.id}")
        
        feedback = _("financials_gift.universal_gift_success_admin", count=affected_users_count)
        await update.message.reply_text(feedback)

        # Step 4: Log to channel
        log_message = _("log.universal_gift_sent", 
                        amount=f"{amount:,}", 
                        count=affected_users_count, 
                        admin_name=admin_user.full_name)
        await send_log(context.bot, log_message)
    else:
        await update.message.reply_text(_("financials_gift.no_users_found"))

# Go back to the main financial menu
    from .settings import show_financial_menu
    query = context.user_data.get('financial_menu_query')
    await show_financial_menu(update, context, query_to_use=query)
    return ConversationHandler.END

async def send_gift_notification_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to send gift notification to users with a delay."""
    job_context = context.job.data

    user_ids = job_context['user_ids']
    amount = job_context['amount']
    
    message = _("financials_gift.universal_gift_user_notification", amount=f"{amount:,}")
    
    LOGGER.info(f"Starting universal gift notification job for {len(user_ids)} users.")
    
    sent_count = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            sent_count += 1
        except Exception as e:
            LOGGER.warning(f"Failed to send gift notification to user {user_id}: {e}")
        
        await asyncio.sleep(0.1) # 10 messages per second to avoid flood limits

    log_message = _("log.universal_gift_notification_finished", count=sent_count)
    await send_log(context.bot, log_message)
    LOGGER.info(f"Universal gift notification job finished. Sent to {sent_count} users.")