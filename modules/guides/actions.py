# --- START OF FILE modules/guides/actions.py ---
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, error
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode

from database.crud import guide as crud_guide
from shared.keyboards import get_admin_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

(LIST_GUIDES, GUIDE_MENU, CONFIRM_DELETE, BUTTON_MENU, 
 EDIT_TITLE, EDIT_CONTENT, EDIT_PHOTO, 
 GET_BUTTON_TEXT, GET_BUTTON_URL, SELECT_BUTTON_TO_DELETE, EDIT_KEY) = range(11)

def build_guides_list_keyboard(guides: list) -> InlineKeyboardMarkup:
    from shared.translator import _
    keyboard = []
    it = iter(guides)
    for guide1 in it:
        row = []
        emojis1 = "".join(filter(None, ["📝" if guide1.content else None, "🖼️" if guide1.photo_file_id else None, "🔗" if guide1.buttons else None])) or "📄"
        row.append(InlineKeyboardButton(f"{emojis1} {guide1.title}", callback_data=f"guide_manage_{guide1.guide_key}"))
        try:
            guide2 = next(it)
            emojis2 = "".join(filter(None, ["📝" if guide2.content else None, "🖼️" if guide2.photo_file_id else None, "🔗" if guide2.buttons else None])) or "📄"
            row.append(InlineKeyboardButton(f"{emojis2} {guide2.title}", callback_data=f"guide_manage_{guide2.guide_key}"))
        except StopIteration: pass
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton(_("guides.button_add_new"), callback_data="guide_add_new")])
    keyboard.append([InlineKeyboardButton(_("guides.button_back_to_main"), callback_data="guide_back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def build_guide_manage_keyboard(guide_key: str, guide) -> InlineKeyboardMarkup:
    from shared.translator import _
    photo_text = _("guides.button_photo_edit_delete") if guide.photo_file_id else _("guides.button_photo_add_edit")
    
    final_keyboard_layout = [
        [InlineKeyboardButton(_("guides.button_preview"), callback_data=f"guide_view_{guide_key}")],
        [
            InlineKeyboardButton(_("guides.button_edit_title"), callback_data="guide_edit_title"), 
            InlineKeyboardButton(_("guides.button_edit_content"), callback_data="guide_edit_content")
        ],
        [InlineKeyboardButton(_("guides.button_manage_buttons"), callback_data="guide_edit_buttons")],
        [
            InlineKeyboardButton(photo_text, callback_data="guide_edit_photo"), 
            InlineKeyboardButton(_("guides.button_delete_guide"), callback_data=f"guide_delete_confirm_{guide_key}")
        ],
        [InlineKeyboardButton(_("guides.button_back_to_list"), callback_data="guide_back_to_list")]
    ]
    return InlineKeyboardMarkup(final_keyboard_layout)

def build_buttons_manage_keyboard(guide) -> InlineKeyboardMarkup:
    from shared.translator import _
    keyboard = []
    buttons = guide.buttons or []
    if not buttons:
        keyboard.append([InlineKeyboardButton(_("guides.no_buttons_yet"), callback_data="noop")])
    keyboard.append([InlineKeyboardButton(_("guides.button_add_new_button"), callback_data="guide_btn_add")])
    if buttons:
        keyboard.append([InlineKeyboardButton(_("guides.button_delete_a_button"), callback_data="guide_btn_delete_prompt")])
    keyboard.append([InlineKeyboardButton(_("guides.button_back_to_guide_management"), callback_data=f"guide_manage_{guide.guide_key}")])
    return InlineKeyboardMarkup(keyboard)

async def start_guide_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    guides = await crud_guide.get_all_guides()
    text = _("guides.menu_title")
    reply_markup = build_guides_list_keyboard(guides)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return LIST_GUIDES

async def show_guide_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    guide_key = query.data.split('guide_manage_')[-1]
    context.user_data['current_guide_key'] = guide_key
    
    guide = await crud_guide.get_guide_by_key(guide_key)
    if not guide:
        await query.answer(_("guides.error_guide_not_found"), show_alert=True)
        return await start_guide_management(update, context)
        
    await query.answer()
    text = _("guides.manage_guide_title", title=guide.title)
    reply_markup = build_guide_manage_keyboard(guide_key, guide)
    
    if query.message.photo:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU

async def prompt_for_new_guide_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query; await query.answer()
    await query.edit_message_text(_("guides.step1_ask_key"), parse_mode=ParseMode.MARKDOWN); return EDIT_KEY

async def process_new_guide_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    guide_key = update.message.text.strip().lower().replace(" ", "_")
    if not guide_key.isascii() or ' ' in guide_key or not guide_key:
        await update.message.reply_text(_("guides.invalid_key")); return EDIT_KEY
    if await crud_guide.get_guide_by_key(guide_key):
        await update.message.reply_text(_("guides.key_already_exists")); return EDIT_KEY
    
    context.user_data['current_guide_key'] = guide_key
    await crud_guide.add_or_update_guide({'guide_key': guide_key, 'title': "عنوان موقت", 'content': "محتوای موقت"})
    
    await update.message.reply_text(_("guides.guide_created_success", gkey=f"`{guide_key}`"))
    
    guide = await crud_guide.get_guide_by_key(guide_key)
    text = _("guides.manage_guide_title", title=guide.title)
    reply_markup = build_guide_manage_keyboard(guide_key, guide)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU

async def prompt_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    action = query.data.split('_', 2)[2]
    prompts = {'title': ("guides.prompt_edit_title", EDIT_TITLE), 'content': ("guides.prompt_edit_content", EDIT_CONTENT), 'photo': ("guides.prompt_edit_photo", EDIT_PHOTO)}
    if action not in prompts:
        await query.answer(_("guides.invalid_action"), show_alert=True); return GUIDE_MENU
    
    prompt_key, next_state = prompts[action]
    await query.answer()
    await query.edit_message_text(_(prompt_key), parse_mode=ParseMode.MARKDOWN)
    return next_state

async def _process_edit_and_return(update: Update, context: ContextTypes.DEFAULT_TYPE, new_data: dict, feedback_key: str) -> int:
    from shared.translator import _
    guide_key = context.user_data['current_guide_key']
    
    updated_guide_data = {'guide_key': guide_key, **new_data}
    await crud_guide.add_or_update_guide(updated_guide_data)
    
    await update.message.reply_text(_(feedback_key))
    
    new_guide = await crud_guide.get_guide_by_key(guide_key)
    text = _("guides.manage_guide_title", title=new_guide.title)
    await update.message.reply_text(text, reply_markup=build_guide_manage_keyboard(guide_key, new_guide), parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU

async def process_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _process_edit_and_return(update, context, {'title': update.message.text.strip()}, "guides.title_updated_success")

async def process_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _process_edit_and_return(update, context, {'content': update.message.text_html}, "guides.content_updated_success")
    
async def process_edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    if update.message.photo:
        return await _process_edit_and_return(update, context, {'photo_file_id': update.message.photo[-1].file_id}, "guides.photo_updated_success")
    elif update.message.text and update.message.text.strip().lower() == 'حذف':
        return await _process_edit_and_return(update, context, {'photo_file_id': None}, "guides.photo_deleted_success")
    else:
        await update.message.reply_text(_("guides.invalid_photo_input")); return EDIT_PHOTO

async def show_buttons_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data['guide_menu_message_id'] = query.message.message_id
    
    guide_key = context.user_data['current_guide_key']
    guide = await crud_guide.get_guide_by_key(guide_key)
    text = _("guides.buttons_menu_title", title=guide.title)
    
    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, message_id=context.user_data['guide_menu_message_id'],
            text=text, reply_markup=build_buttons_manage_keyboard(guide), parse_mode=ParseMode.MARKDOWN
        )
    except error.BadRequest as e:
        if "Message is not modified" not in str(e): LOGGER.error(f"Error editing buttons menu: {e}")
    return BUTTON_MENU

async def prompt_for_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query; await query.answer()
    context.user_data['new_button'] = {}
    await query.edit_message_text(_("guides.step1_ask_button_text")); return GET_BUTTON_TEXT

async def get_button_text_and_prompt_for_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    context.user_data['new_button']['text'] = update.message.text.strip()
    await update.message.reply_text(_("guides.step2_ask_button_url")); return GET_BUTTON_URL

async def get_button_url_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    url = update.message.text.strip()
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(_("guides.invalid_url"))
        return GET_BUTTON_URL
        
    context.user_data['new_button']['url'] = url
    
    guide_key = context.user_data['current_guide_key']
    guide = await crud_guide.get_guide_by_key(guide_key)
    buttons = guide.buttons or []
    buttons.append(context.user_data.pop('new_button'))
    
    await crud_guide.add_or_update_guide({'guide_key': guide_key, 'buttons': buttons})
    
    try:
        await update.message.delete()
        if 'guide_menu_message_id' in context.user_data:
             await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['guide_menu_message_id']
            )
    except Exception as e:
        LOGGER.warning(f"Could not delete messages during button save: {e}")

    new_guide = await crud_guide.get_guide_by_key(guide_key)
    
    text = _("guides.buttons_menu_title", title=new_guide.title)
    reply_markup = build_buttons_manage_keyboard(new_guide)
    sent_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data['guide_menu_message_id'] = sent_message.message_id
    
    return BUTTON_MENU
    
async def prompt_to_delete_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query; await query.answer()
    guide = await crud_guide.get_guide_by_key(context.user_data['current_guide_key'])
    buttons = guide.buttons or []
    if not buttons:
        await query.answer(_("guides.no_buttons_to_delete"), show_alert=True); return BUTTON_MENU
    keyboard = [[InlineKeyboardButton(_("guides.button_delete_prefix", text=btn['text']), callback_data=f"guide_btn_delete_do_{i}")] for i, btn in enumerate(buttons)]
    keyboard.append([InlineKeyboardButton(_("guides.button_back"), callback_data=f"guide_edit_buttons")])
    await query.edit_message_text(_("guides.prompt_select_button_to_delete"), reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_BUTTON_TO_DELETE

async def do_delete_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    button_index = int(query.data.split('_')[-1])
    guide_key = context.user_data['current_guide_key']
    guide = await crud_guide.get_guide_by_key(guide_key)
    buttons = guide.buttons or []
    if 0 <= button_index < len(buttons):
        removed_btn = buttons.pop(button_index)
        await crud_guide.add_or_update_guide({'guide_key': guide_key, 'buttons': buttons})
        await query.answer(_("guides.button_deleted_success", text=removed_btn['text']), show_alert=True)
    else:
        await query.answer(_("guides.error_button_not_found"), show_alert=True)
    await show_buttons_menu(update, context)
    return BUTTON_MENU

async def view_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    guide_key = context.user_data.get('current_guide_key') or query.data.split('guide_view_')[-1]
    guide = await crud_guide.get_guide_by_key(guide_key)
    keyboard = [[InlineKeyboardButton(_("guides.button_back_to_guide_management"), callback_data=f"guide_manage_{guide_key}")]]
    if guide.buttons:
        for btn in guide.buttons: keyboard.insert(0, [InlineKeyboardButton(btn['text'], url=btn['url'])])
    
    text = f"**{guide.title}**\n\n{guide.content or ''}"
    
    if guide.photo_file_id:
        await query.message.delete()
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=guide.photo_file_id, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    return GUIDE_MENU

async def confirm_delete_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query; await query.answer()
    guide = await crud_guide.get_guide_by_key(context.user_data['current_guide_key'])
    keyboard = [[InlineKeyboardButton(_("guides.button_confirm_delete"), callback_data=f"guide_delete_do_{guide.guide_key}"), InlineKeyboardButton(_("guides.button_cancel_delete"), callback_data=f"guide_manage_{guide.guide_key}")]]
    await query.edit_message_text(_("guides.delete_confirm_prompt", title=guide.title), reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DELETE

async def do_delete_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    
    guide_key = query.data.removeprefix('guide_delete_do_')
    success = await crud_guide.delete_guide(guide_key)
    await query.answer(_("guides.delete_success_feedback") if success else _("guides.delete_error_feedback"), show_alert=True)

    guides = await crud_guide.get_all_guides()
    
    text = _("guides.menu_title")
    reply_markup = build_guides_list_keyboard(guides)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    return LIST_GUIDES
async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    target_message = update.message or (query and query.message)
    if query:
        await query.answer(); await query.message.delete()
    await context.bot.send_message(chat_id=target_message.chat_id, text=_("guides.back_to_main_menu_feedback"), reply_markup=get_admin_main_menu_keyboard())
    context.user_data.clear(); return ConversationHandler.END

# --- END OF FILE modules/guides/actions.py ---