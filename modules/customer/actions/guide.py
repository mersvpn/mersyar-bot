# FILE: modules/customer/actions/guide.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import db_manager

LOGGER = logging.getLogger(__name__)

async def show_guides_to_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    guides = await db_manager.get_all_guides()

    message_text = "📚 لطفاً راهنمای مورد نظر خود را انتخاب کنید:"
    keyboard = []

    if not guides:
        message_text = "در حال حاضر هیچ راهنمایی ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
    else:
        it = iter(guides)
        for guide1 in it:
            row = []
            row.append(InlineKeyboardButton(guide1['title'], callback_data=f"customer_show_guide_{guide1['guide_key']}"))
            try:
                guide2 = next(it)
                row.append(InlineKeyboardButton(guide2['title'], callback_data=f"customer_show_guide_{guide2['guide_key']}"))
            except StopIteration:
                pass
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("✖️ بستن", callback_data="close_guide_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # (✨ FIX) Handle both Message and CallbackQuery entry points
    chat_id = update.effective_chat.id
    query = update.callback_query

    if query:
        await query.answer()
        # Delete the broadcast message and send the guide menu as a new message
        if query.message:
            await query.message.delete()
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )

async def send_guide_content_to_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    guide_key = query.data.split('customer_show_guide_')[-1]
    guide = await db_manager.get_guide(guide_key)
    
    if not guide:
        await query.edit_message_text("❌ متاسفانه این راهنما یافت نشد.")
        return

    keyboard = []
    custom_buttons = guide.get('buttons')
    if custom_buttons and isinstance(custom_buttons, list):
        for btn_data in custom_buttons:
            keyboard.append([InlineKeyboardButton(btn_data['text'], url=btn_data['url'])])

    keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست راهنماها", callback_data="customer_back_to_guides")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    content = guide.get('content') or ""
    photo_file_id = guide.get('photo_file_id')

    if photo_file_id:
        await query.message.delete()
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo_file_id,
            caption=content,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await query.edit_message_text(
            text=content,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

async def close_guide_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the guide menu message."""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass

# FILE: modules/customer/actions/guide.py

async def show_guides_as_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    A wrapper for show_guides_to_customer that ENSURES a new message is sent.
    This is used for the inline button on the subscription message to prevent it from being edited away.
    """
    query = update.callback_query
    if query:
        await query.answer() # Acknowledge the button press
        
    # (✨ BUG FIX) Create a more complete DummyUpdate object that includes 'effective_chat'.
    # This prevents crashes when the wrapped function tries to access it.
    class DummyUpdate:
        def __init__(self, original_update):
            self.message = original_update.effective_message
            self.effective_chat = original_update.effective_chat
            # By setting callback_query to None, we force show_guides_to_customer
            # to send a new message instead of trying to edit one.
            self.callback_query = None

    # Pass the original update object to the constructor to get all necessary attributes.
    await show_guides_to_customer(DummyUpdate(update), context)