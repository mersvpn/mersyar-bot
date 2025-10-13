# --- START OF FILE modules/broadcaster/actions/forwarder.py (REVISED) ---

# FILE: modules/broadcaster/actions/forwarder.py (NEW FILE)

import logging
import uuid
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

from shared.translator import _
from shared.keyboards import get_message_builder_cancel_keyboard
# --- MODIFIED IMPORT ---
from database.crud import user as crud_user
# --- ----------------- ---

LOGGER = logging.getLogger(__name__)

# States for the forwarder conversation
AWAITING_MESSAGE, AWAITING_CONFIRMATION = range(2)

async def start_forward_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the forward broadcast conversation."""
    await update.message.reply_text(
        _("broadcaster.forwarder.start_prompt"),
        reply_markup=get_message_builder_cancel_keyboard()
    )
    return AWAITING_MESSAGE

async def ask_for_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the message to be forwarded and asks for admin confirmation."""
    # We need to store the details of the message to be forwarded
    context.user_data['forward_message_id'] = update.message.message_id
    context.user_data['forward_chat_id'] = update.message.chat_id

    keyboard = [
        [
            InlineKeyboardButton(_("broadcaster.forwarder.confirm_button"), callback_data="forward_confirm"),
            InlineKeyboardButton(_("broadcaster.forwarder.cancel_button"), callback_data="forward_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(_("broadcaster.forwarder.confirm_prompt"), reply_markup=reply_markup)
    return AWAITING_CONFIRMATION

async def schedule_forward_job(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Schedules the background job to forward the message to all users."""
    query = update.callback_query
    await query.answer()

    message_id = context.user_data.get('forward_message_id')
    chat_id = context.user_data.get('forward_chat_id')
    
    if not message_id or not chat_id:
        await query.edit_message_text(_("broadcaster.forwarder.error_not_found"))
        return await cancel_forwarder(update, context)

    job_id = f"forward_{uuid.uuid4()}"
    job_data = {
        "admin_id": query.from_user.id,
        "from_chat_id": chat_id,
        "message_id": message_id
    }

    context.job_queue.run_once(forward_message_job, 1, data=job_data, name=job_id)

    await query.edit_message_text(_("broadcaster.forwarder.job_scheduled", job_id=job_id), parse_mode=ParseMode.HTML)
    
    # Clean up and end conversation
    return await cancel_forwarder(update, context)

async def forward_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """The actual job that forwards the message to all users."""
    job_data = context.job.data
    admin_id = job_data['admin_id']
    from_chat_id = job_data['from_chat_id']
    message_id = job_data['message_id']

    user_ids = await crud_user.get_all_user_ids()
    total = len(user_ids)
    success, failure = 0, 0
    
    LOGGER.info(f"Starting forward broadcast job '{context.job.name}' for {total} users.")

    for user_id in user_ids:
        try:
            await context.bot.forward_message(
                chat_id=user_id,
                from_chat_id=from_chat_id,
                message_id=message_id
            )
            success += 1
        except TelegramError as e:
            failure += 1
            LOGGER.warning(f"Forward broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1) # Rate limit: 10 messages per second

    report = _("broadcaster.job_report", job_id=context.job.name, total=total, success=success, failure=failure)
    
    from shared.keyboards import get_admin_main_menu_keyboard
    await context.bot.send_message(admin_id, report, parse_mode=ParseMode.HTML)
    await context.bot.send_message(admin_id, _("broadcaster.back_to_main"), reply_markup=get_admin_main_menu_keyboard())
    LOGGER.info(f"Forward broadcast job '{context.job.name}' finished. Success: {success}, Failure: {failure}")

# FILE: modules/broadcaster/actions/forwarder.py

async def cancel_forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cleans up user_data and returns to the main broadcast menu."""
    from .main import show_broadcast_menu # Local import is kept for safety
    
    context.user_data.pop('forward_message_id', None)
    context.user_data.pop('forward_chat_id', None)
    
    query = update.callback_query
    # Determine the correct message object to pass to the next function
    message = query.message if query else update.message
    
    if query:
        # If it's a callback, delete the message it's attached to.
        try:
            await query.message.delete()
        except Exception:
            pass

    # Create a dummy update object that is guaranteed to have a .message attribute
    class DummyUpdate:
        def __init__(self, msg):
            self.message = msg
    
    # Now call show_broadcast_menu with a clean, predictable update object
    await show_broadcast_menu(DummyUpdate(message), context)
    return ConversationHandler.END

# --- END OF FILE modules/broadcaster/actions/forwarder.py (REVISED) ---