import logging
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    filters, CallbackQueryHandler, CommandHandler
)
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from modules.marzban.actions.data_manager import load_settings, save_settings
from shared.callbacks import cancel_conversation
from .settings import show_tools_menu
from modules.auth import admin_only_conv

LOGGER = logging.getLogger(__name__)

(
    MAIN_MENU, LIST_NOTES, VIEW_NOTE,
    ADD_GET_TITLE, ADD_GET_TEXT, CONFIRM_DELETE,
    EDIT_CHOICE, EDIT_GET_TITLE, EDIT_GET_TEXT
) = range(9)
NOTES_KEY = "daily_admin_notes_list"

async def _build_main_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE, is_entry: bool = False):
    keyboard = [
        [InlineKeyboardButton("➕ افزودن یادداشت جدید", callback_data="dnote_add_prompt")],
        [InlineKeyboardButton(" L️ لیست یادداشت‌ها", callback_data="dnote_list_prompt")],
        [InlineKeyboardButton("🔙 بازگشت به ابزارها", callback_data="dnote_back_to_tools")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🗒️ **مدیریت یادداشت‌های روزانه**\n\nلطفاً یک گزینه را انتخاب کنید."
    
    if is_entry:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def _build_list_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = await load_settings()
    notes = settings.get(NOTES_KEY, [])
    keyboard = []
    text = " L️ **لیست یادداشت‌ها**\n\n"

    if not notes:
        text += "هیچ یادداشتی برای نمایش وجود ندارد."
    else:
        text += "برای مشاهده، ویرایش یا حذف، روی عنوان کلیک کنید."
        for note in sorted(notes, key=lambda x: x.get('title', '')):
            keyboard.append([InlineKeyboardButton(note.get("title", "بدون عنوان"), callback_data=f"dnote_view_{note['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="dnote_main_menu_prompt")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def _build_view_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note_id = context.user_data.get('current_note_id')
    settings = await load_settings()
    notes = settings.get(NOTES_KEY, [])
    note_to_show = next((note for note in notes if note.get("id") == note_id), None)

    if not note_to_show:
        await update.callback_query.answer("خطا: یادداشت یافت نشد.", show_alert=True)
        await _build_list_message(update, context)
        return LIST_NOTES

    title = escape_markdown(note_to_show.get('title', ''))
    body = escape_markdown(note_to_show.get('text', ''))
    text = f"**عنوان:** {title}\n\n**متن:**\n{body}"
    keyboard = [
        [
            InlineKeyboardButton("✏️ ویرایش", callback_data="dnote_edit_prompt"),
            InlineKeyboardButton("🗑️ حذف", callback_data="dnote_delete_prompt")
        ],
        [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="dnote_list_prompt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return VIEW_NOTE

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    is_entry = update.message is not None
    if is_entry:
        context.user_data['main_menu_message'] = update.message
    
    await _build_main_menu_message(update, context, is_entry=is_entry)
    return MAIN_MENU

async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await _build_list_message(update, context)
    return LIST_NOTES

async def view_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data['current_note_id'] = update.callback_query.data.split('_')[-1]
    return await _build_view_message(update, context)

async def add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("۱/۲ - لطفاً **عنوان** یادداشت را وارد کنید.")
    return ADD_GET_TITLE

async def add_get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_note_title'] = update.message.text
    await update.message.reply_text("✅ عنوان ذخیره شد.\n\n۲/۲ - لطفاً **متن کامل** یادداشت را وارد کنید.")
    return ADD_GET_TEXT

async def add_get_text_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = await load_settings()
    notes = settings.setdefault(NOTES_KEY, [])
    notes.append({
        "id": str(uuid.uuid4()),
        "title": context.user_data.pop('new_note_title', 'Untitled'),
        "text": update.message.text
    })
    await save_settings(settings)
    
    await update.message.reply_text("✅ یادداشت جدید با موفقیت ذخیره شد.")

    # Rebuild main menu correctly
    class FakeCallbackQuery:
        def __init__(self, message):
            self.message = message
        async def answer(self):
            pass
        async def edit_message_text(self, text, reply_markup, parse_mode):
            # To avoid message clutter, delete the confirmation and send a new menu
            await self.message.delete()
            await context.bot.send_message(
                chat_id=self.message.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

    # Use the original message that started the conversation for context
    original_message = context.user_data.pop('main_menu_message', update.message)
    fake_query = FakeCallbackQuery(original_message)
    fake_update = Update(update.update_id, callback_query=fake_query)

    await _build_main_menu_message(fake_update, context)
    return MAIN_MENU

async def delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data="dnote_delete_confirm")],
        [InlineKeyboardButton("❌ خیر", callback_data=f"dnote_view_{context.user_data['current_note_id']}")]
    ]
    await update.callback_query.edit_message_text("آیا از حذف این یادداشت اطمینان دارید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DELETE

async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note_id = context.user_data.pop('current_note_id')
    settings = await load_settings()
    notes = settings.get(NOTES_KEY, [])
    notes[:] = [note for note in notes if note.get("id") != note_id]
    await save_settings(settings)
    await update.callback_query.answer("یادداشت حذف شد.")
    return await list_notes(update, context)

async def edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    keyboard = [
        [
            InlineKeyboardButton("ویرایش عنوان", callback_data="dnote_edit_title"),
            InlineKeyboardButton("ویرایش متن", callback_data="dnote_edit_text")
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"dnote_view_{context.user_data['current_note_id']}")]
    ]
    await update.callback_query.edit_message_text("کدام بخش را ویرایش می‌کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_CHOICE

async def edit_get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data['edit_field'] = 'title'
    await update.callback_query.edit_message_text("لطفاً **عنوان** جدید را وارد کنید.")
    return EDIT_GET_TITLE

async def edit_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data['edit_field'] = 'text'
    await update.callback_query.edit_message_text("لطفاً **متن** جدید را وارد کنید.")
    return EDIT_GET_TEXT

async def edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note_id = context.user_data.get('current_note_id')
    field = context.user_data.pop('edit_field', None)
    
    if not note_id or not field:
        await update.message.reply_text("خطا: اطلاعات ویرایش یافت نشد. لطفاً دوباره تلاش کنید.")
        # Fallback to the main menu
        class FakeCQ:
            def __init__(self, msg): self.message = msg
            async def answer(self): pass
            async def edit_message_text(self, **kwargs): await self.message.reply_text(**kwargs)
        fake_update = Update(update.update_id, callback_query=FakeCQ(update.message))
        return await main_menu(fake_update, context)

    settings = await load_settings()
    notes = settings.get(NOTES_KEY, [])
    
    note_to_edit = next((note for note in notes if note.get("id") == note_id), None)
    
    confirmation_msg = None
    if note_to_edit:
        note_to_edit[field] = update.message.text
        await save_settings(settings)
        confirmation_msg = await update.message.reply_text("✅ یادداشت با موفقیت ویرایش شد.")
    else:
        await update.message.reply_text("خطا: یادداشت برای ویرایش یافت نشد.")

    # Rebuild the view message correctly to prevent freezing
    class FakeCallbackQuery:
        def __init__(self, message, data):
            self.message = message
            self.data = data
        async def answer(self):
            pass
        async def edit_message_text(self, text, reply_markup, parse_mode):
            # Clean up previous messages and send a fresh new one
            await update.message.delete()
            if confirmation_msg:
                await confirmation_msg.delete()
            
            original_message = context.user_data.get('main_menu_message')
            if original_message:
                await original_message.delete()

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

    original_message = context.user_data.pop('main_menu_message', update.message)
    fake_query = FakeCallbackQuery(original_message, f"dnote_view_{note_id}")
    fake_update = Update(update.update_id, callback_query=fake_query)
    
    return await _build_view_message(fake_update, context)
async def back_to_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.message.delete()
    await show_tools_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END

daily_notes_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^🗒️ مدیریت یادداشت‌ها$'), admin_only_conv(main_menu))],
    states={
        MAIN_MENU: [
            CallbackQueryHandler(add_prompt, pattern='^dnote_add_prompt$'),
            CallbackQueryHandler(list_notes, pattern='^dnote_list_prompt$'),
        ],
        ADD_GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_title)],
        ADD_GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_get_text_and_save)],
        LIST_NOTES: [
            CallbackQueryHandler(view_note, pattern=r'^dnote_view_'),
            CallbackQueryHandler(main_menu, pattern='^dnote_main_menu_prompt$'),
        ],
        VIEW_NOTE: [
            CallbackQueryHandler(edit_prompt, pattern='^dnote_edit_prompt$'),
            CallbackQueryHandler(delete_prompt, pattern='^dnote_delete_prompt$'),
            CallbackQueryHandler(list_notes, pattern='^dnote_list_prompt$'),
        ],
        CONFIRM_DELETE: [
            CallbackQueryHandler(delete_confirm, pattern='^dnote_delete_confirm$'),
            CallbackQueryHandler(view_note, pattern=r'^dnote_view_'),
        ],
        EDIT_CHOICE: [
            CallbackQueryHandler(edit_get_title, pattern='^dnote_edit_title$'),
            CallbackQueryHandler(edit_get_text, pattern='^dnote_edit_text$'),
            CallbackQueryHandler(view_note, pattern=r'^dnote_view_'),
        ],
        EDIT_GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_save)],
        EDIT_GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_save)],
    },
    fallbacks=[
        CallbackQueryHandler(back_to_tools, pattern='^dnote_back_to_tools$'),
        CommandHandler('cancel', cancel_conversation)
    ],
    conversation_timeout=600,
    per_user=True,
    per_chat=True
)