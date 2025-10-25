# --- START OF FILE modules/financials/actions/gift.py (REVISED) ---

import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# --- MODIFIED IMPORTS ---
from database.crud import bot_setting as crud_bot_setting
from database.crud import user as crud_user
# --- ------------------ ---
from shared.keyboards import get_gift_management_keyboard
from shared.translator import _
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

(MENU, GET_WELCOME_AMOUNT) = range(2)
(GET_UNIVERSAL_AMOUNT, CONFIRM_UNIVERSAL_GIFT) = range(2, 4)


async def show_gift_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    settings = await crud_bot_setting.load_bot_settings()
    welcome_amount = settings.get('welcome_gift_amount', 0) if settings else 0
    
    if welcome_amount > 0:
        amount_str = _("financials_gift.welcome_gift_amount_set", amount=f"{welcome_amount:,}")
    else:
        amount_str = _("financials_gift.welcome_gift_not_set")

    text = _("financials_gift.menu_title", current_gift=amount_str)
    keyboard = get_gift_management_keyboard()

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return MENU

async def prompt_for_welcome_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("financials_gift.prompt_welcome_gift"), parse_mode=ParseMode.HTML)
    return GET_WELCOME_AMOUNT

async def save_welcome_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = int(update.message.text.strip())
        if amount < 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_gift.invalid_amount"))
        return GET_WELCOME_AMOUNT

    await crud_bot_setting.save_bot_settings({'welcome_gift_amount': amount})
    
    if amount > 0:
        feedback = _("financials_gift.welcome_gift_save_success", amount=f"{amount:,}")
    else:
        feedback = _("financials_gift.welcome_gift_disabled")
        
    await update.message.reply_text(feedback)
    
    from .settings import show_financial_menu
    query = context.user_data.get('financial_menu_query')
    await show_financial_menu(update, context, query_to_use=query)
    
    return ConversationHandler.END

async def prompt_for_universal_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("financials_gift.prompt_universal_gift"), parse_mode=ParseMode.HTML)
    return GET_UNIVERSAL_AMOUNT

async def prompt_for_gift_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_gift.invalid_amount"))
        return GET_UNIVERSAL_AMOUNT

    context.user_data['universal_gift_amount'] = amount
    
    text = _("financials_gift.universal_gift_confirm_prompt", amount=f"{amount:,}", keyword=f"<code>{_('financials_gift.confirm_keyword')}</code>")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    return CONFIRM_UNIVERSAL_GIFT

async def process_universal_gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    confirmation = update.message.text.strip()
    if confirmation != _('financials_gift.confirm_keyword'):
        await update.message.reply_text(_("financials_gift.confirmation_failed"))
        from .settings import show_financial_menu
        query = context.user_data.get('financial_menu_query')
        await show_financial_menu(update, context, query_to_use=query)
        return ConversationHandler.END

    amount = context.user_data.get('universal_gift_amount')
    admin_user = update.effective_user

    await update.message.reply_text(_("financials_gift.processing_universal_gift"))

    affected_users_count = await crud_user.increase_balance_for_all_users(amount)

    if affected_users_count is None:
        await update.message.reply_text(_("financials_gift.db_error"))
    elif affected_users_count > 0:
        user_ids = await crud_user.get_all_user_ids()
        
        context.job_queue.run_once(send_gift_notification_job, 1, 
                           data={'user_ids': user_ids, 'amount': amount}, 
                           name=f"universal_gift_{update.effective_chat.id}")
        
        feedback = _("financials_gift.universal_gift_success_admin", count=affected_users_count)
        await update.message.reply_text(feedback)

        log_message = _("log.universal_gift_sent", 
                        amount=f"{amount:,}", 
                        count=affected_users_count, 
                        admin_name=admin_user.full_name)
        await send_log(context.bot, log_message)
    else:
        await update.message.reply_text(_("financials_gift.no_users_found"))

    from .settings import show_financial_menu
    query = context.user_data.get('financial_menu_query')
    await show_financial_menu(update, context, query_to_use=query)
    return ConversationHandler.END

async def send_gift_notification_job(context: ContextTypes.DEFAULT_TYPE):
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
        
        await asyncio.sleep(0.1)

    log_message = _("log.universal_gift_notification_finished", count=sent_count)
    await send_log(context.bot, log_message)
    LOGGER.info(f"Universal gift notification job finished. Sent to {sent_count} users.")

# --- END OF FILE modules/financials/actions/gift.py (REVISED) ---