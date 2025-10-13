# --- START OF FILE modules/broadcaster/actions/main.py (REVISED) ---

import logging
import asyncio
import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

from shared.translator import _
from shared.keyboards import get_broadcaster_menu_keyboard, get_message_builder_cancel_keyboard, get_deeplink_targets_keyboard
# --- MODIFIED IMPORTS ---
from database.crud import broadcast as crud_broadcast
from database.crud import user as crud_user
# --- ------------------ ---

LOGGER = logging.getLogger(__name__)

# States
(
    BUILDER_MENU, AWAITING_CONTENT, AWAITING_BUTTON_TYPE,
    AWAITING_BUTTON_TARGET_MENU, AWAITING_BUTTON_URL, AWAITING_BUTTON_TEXT,
    AWAITING_PREVIEW_CONFIRMATION, AWAITING_TARGET_TYPE, AWAITING_SINGLE_USER_ID
) = range(9)

def _get_builder_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if 'builder' not in context.user_data:
        context.user_data['builder'] = { 'photo_id': None, 'text': None, 'buttons': [] }
    return context.user_data['builder']

def _build_reply_markup_from_data(builder_data: dict) -> InlineKeyboardMarkup | None:
    if not builder_data.get('buttons'): return None
    keyboard = []
    for row_data in builder_data['buttons']:
        row = []
        for btn_data in row_data:
            btn = InlineKeyboardButton(btn_data['text'], url=btn_data.get('url'), callback_data=btn_data.get('callback_data'))
            row.append(btn)
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

async def _send_or_edit_builder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    builder_data = _get_builder_data(context)
    chat_id = update.effective_chat.id
    menu_message_id = context.user_data.get('builder_menu_id')
    
    photo_status = "✅" if builder_data['photo_id'] else "❌"
    text_status = "✅" if builder_data.get('text') else "❌"
    
    buttons_preview = ""
    if builder_data.get('buttons'):
        for i, row in enumerate(builder_data['buttons']):
            if not row: continue
            button_texts = [f"[{btn['text']}]" for btn in row]
            buttons_preview += f"\nRow {i+1}: {' '.join(button_texts)}"
    else:
        buttons_preview = _("broadcaster.builder.no_buttons")

    menu_text = _("broadcaster.builder.menu_title", photo_status=photo_status, text_status=text_status, buttons_preview=buttons_preview)
    
    keyboard_layout = [
        [InlineKeyboardButton(_("broadcaster.builder.buttons.edit_content"), callback_data="builder_edit_content")],
        [
            InlineKeyboardButton(_("broadcaster.builder.buttons.add_button_row"), callback_data="builder_add_button_row"),
            InlineKeyboardButton(_("broadcaster.builder.buttons.add_button_to_last_row"), callback_data="builder_add_to_last_row"),
        ],
        [InlineKeyboardButton(_("broadcaster.builder.buttons.delete_last_button"), callback_data="builder_delete_last")],
        [InlineKeyboardButton(_("broadcaster.builder.buttons.preview_and_send"), callback_data="builder_preview")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_layout)

    if menu_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_id,
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        except TelegramError as e:
            if "message to edit not found" in str(e).lower():
                context.user_data.pop('builder_menu_id', None)
            elif "message is not modified" not in str(e).lower():
                LOGGER.warning(f"Could not edit builder menu (will send new): {e}")

    sent_message = await context.bot.send_message(
        chat_id=chat_id,
        text=menu_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    context.user_data['builder_menu_id'] = sent_message.message_id


async def start_message_builder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data['in_builder_mode'] = True
    
    _get_builder_data(context)
    context.user_data['is_single_send'] = (update.message.text == _("keyboards.broadcaster_menu.send_custom_single"))
    await update.message.reply_text(_("broadcaster.builder.start_message"), reply_markup=get_message_builder_cancel_keyboard())
    await _send_or_edit_builder_menu(update, context)
    return BUILDER_MENU

async def prompt_for_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.message.delete()
    sent_message = await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=_("broadcaster.builder.prompt_content")
    )
    context.user_data['prompt_message_id'] = sent_message.message_id
    return AWAITING_CONTENT

async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    builder_data = _get_builder_data(context)
    if update.message.photo:
        builder_data['photo_id'] = update.message.photo[-1].file_id
        builder_data['text'] = update.message.caption_html
    elif update.message.text:
        builder_data['photo_id'] = None
        builder_data['text'] = update.message.text_html
    
    await update.message.delete()
    prompt_message_id = context.user_data.pop('prompt_message_id', None)
    if prompt_message_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=prompt_message_id)
        except TelegramError:
            pass
    await _send_or_edit_builder_menu(update, context)
    return BUILDER_MENU

async def add_button_row(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _get_builder_data(context)['buttons'].append([])
    return await prompt_for_button_type(update, context)

async def add_button_to_last_row(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _get_builder_data(context)['buttons']:
        _get_builder_data(context)['buttons'].append([])
    return await prompt_for_button_type(update, context)

async def prompt_for_button_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton(_("broadcaster.builder.buttons.url_button"), callback_data="btn_type_url")],
        [InlineKeyboardButton(_("broadcaster.builder.buttons.deeplink_button"), callback_data="btn_type_deeplink")],
        [InlineKeyboardButton(_("broadcaster.builder.buttons.back_to_builder"), callback_data="builder_back_to_menu")]
    ]
    await query.edit_message_text(_("broadcaster.builder.prompt_button_type"), reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAITING_BUTTON_TYPE

async def prompt_for_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.edit_message_text(_("broadcaster.builder.prompt_button_url"))
    return AWAITING_BUTTON_URL

async def prompt_for_deeplink_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.edit_message_text(_("broadcaster.builder.prompt_deeplink_target"), reply_markup=get_deeplink_targets_keyboard())
    return AWAITING_BUTTON_TARGET_MENU

async def process_button_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    builder_data = _get_builder_data(context)
    target_data = update.message.text if update.message else update.callback_query.data
    builder_data['temp_button_target'] = {'url': target_data} if target_data.startswith("http") else {'callback_data': target_data}
    prompt_text = _("broadcaster.builder.prompt_button_text")
    if update.callback_query:
        await update.callback_query.edit_message_text(prompt_text)
    else:
        await update.message.reply_text(prompt_text)
    return AWAITING_BUTTON_TEXT

async def process_button_text_and_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    builder_data = _get_builder_data(context)
    button_text = update.message.text.strip()
    new_button = {'text': button_text}
    new_button.update(builder_data.pop('temp_button_target', {}))
    if not builder_data['buttons']: builder_data['buttons'].append([])
    builder_data['buttons'][-1].append(new_button)
    await update.message.delete()
    await _send_or_edit_builder_menu(update, context)
    return BUILDER_MENU

async def delete_last_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    builder_data = _get_builder_data(context)
    if builder_data['buttons']:
        last_row = builder_data['buttons'][-1]
        if last_row:
            last_row.pop()
            await query.answer(_("broadcaster.builder.feedback.last_button_deleted"))
            if not last_row: builder_data['buttons'].pop()
        else:
            builder_data['buttons'].pop()
            await query.answer(_("broadcaster.builder.feedback.last_row_deleted"))
    else:
        await query.answer(_("broadcaster.builder.feedback.no_buttons_to_delete"), show_alert=True)
    await _send_or_edit_builder_menu(update, context)
    return BUILDER_MENU

async def back_to_builder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _send_or_edit_builder_menu(update, context)
    return BUILDER_MENU

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.message.delete()
    builder_data = _get_builder_data(context)
    text = builder_data.get('text')
    photo_id = builder_data.get('photo_id')
    reply_markup = _build_reply_markup_from_data(builder_data)

    if not text and not photo_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=_("broadcaster.builder.errors.empty_message"))
        await _send_or_edit_builder_menu(update, context)
        return BUILDER_MENU
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=_("broadcaster.builder.preview_title"), parse_mode=ParseMode.HTML)
    if photo_id:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_id, caption=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    keyboard = [
        [InlineKeyboardButton(_("broadcaster.builder.buttons.confirm_send"), callback_data="preview_confirm")],
        [InlineKeyboardButton(_("broadcaster.builder.buttons.back_to_builder"), callback_data="builder_back_to_menu")]
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=_("broadcaster.builder.confirm_send_prompt"), reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAITING_PREVIEW_CONFIRMATION

async def prompt_for_target_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('is_single_send'):
        await update.callback_query.edit_message_text(_("broadcaster.builder.prompt_single_user"))
        return AWAITING_SINGLE_USER_ID
    else:
        return await schedule_broadcast(update, context)

async def schedule_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_ids: list = None) -> int:
    """Schedules the broadcast job by passing data directly to the job context."""
    builder_data = _get_builder_data(context)
    
    # --- ✨ SQLAlchemy Integration: No more db_manager ✨ ---
    job_data = {
        "admin_id": update.effective_chat.id,
        "message_content": {
            "text": builder_data.get('text'),
            "photo_id": builder_data.get('photo_id'),
            "buttons": builder_data.get('buttons', [])
        },
        "target_user_ids": target_user_ids
    }
    context.job_queue.run_once(send_broadcast_message_job, 1, data=job_data, name=f"broadcast_{update.effective_chat.id}")
    
    if update.callback_query:
        await update.callback_query.message.delete()
        
    return await cancel_builder(update, context)

async def process_single_user_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = int(update.message.text.strip())
        return await schedule_broadcast(update, context, target_user_ids=[user_id])
    except (ValueError, TypeError):
        await update.message.reply_text(_("broadcaster.builder.errors.invalid_user_id"))
        return AWAITING_SINGLE_USER_ID

async def cancel_builder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cleans up user_data and returns to the main broadcast menu."""
    context.user_data.clear()
    
    query = update.callback_query
    message = query.message if query else update.message
    
    if query and query.message:
        try:
            await query.message.delete()
        except TelegramError: 
            pass
            
    class DummyUpdate:
        def __init__(self, msg):
            self.message = msg
            
    await show_broadcast_menu(DummyUpdate(message), context)
    return ConversationHandler.END

async def show_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = get_broadcaster_menu_keyboard()
    await update.message.reply_text(_("broadcaster.main_menu_prompt"), reply_markup=keyboard)

async def send_broadcast_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executes the broadcast, then logs the result to the database."""
    job_data = context.job.data
    admin_id = job_data.get("admin_id")
    message_content = job_data.get("message_content", {})
    target_user_ids = job_data.get("target_user_ids", [])

    LOGGER.info(f"Starting broadcast job for admin {admin_id}")
    
    text = message_content.get("text")
    photo_id = message_content.get("photo_id")
    buttons = message_content.get("buttons", [])
    reply_markup = _build_reply_markup_from_data({'buttons': buttons})

    if not target_user_ids:
        target_user_ids = await crud_user.get_all_user_ids()

    if not target_user_ids:
        LOGGER.warning("Broadcast job stopped: No target users found.")
        await context.bot.send_message(admin_id, _("broadcaster.errors.no_users_found"))
        return
        
    total, success, failure = len(target_user_ids), 0, 0

    for user_id in target_user_ids:
        try:
            if photo_id:
                await context.bot.send_photo(chat_id=user_id, photo=photo_id, caption=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            else:
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            success += 1
        except TelegramError as e:
            failure += 1
            LOGGER.warning(f"Broadcast failed for user {user_id}: {e}")
        await asyncio.sleep(0.1)

    # --- ✨ SQLAlchemy Integration: Log the final result ✨ ---
    await crud_broadcast.log_broadcast(
        admin_id=admin_id,
        message_content=message_content,
        success_count=success,
        failure_count=failure
    )
    # --- ---------------------------------------------------- ---

    report = _("broadcaster.job_report", total=total, success=success, failure=failure)
    await context.bot.send_message(admin_id, report, parse_mode=ParseMode.HTML)
    from shared.keyboards import get_admin_main_menu_keyboard
    await context.bot.send_message(chat_id=admin_id, text=_("broadcaster.back_to_main"), reply_markup=get_admin_main_menu_keyboard())
    LOGGER.info(f"Job for admin {admin_id} finished. Success: {success}, Failure: {failure}")

# --- END OF FILE modules/broadcaster/actions/main.py (REVISED) ---