# FILE: modules/guides/actions.py (نسخه نهایی کامل و یکپارچه)

import logging
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, error
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode

from database import db_manager
from shared.keyboards import get_admin_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

# --- وضعیت‌های کامل مکالمه ---
(LIST_GUIDES, GUIDE_MENU, CONFIRM_DELETE, BUTTON_MENU, 
 EDIT_TITLE, EDIT_CONTENT, EDIT_PHOTO, 
 GET_BUTTON_TEXT, GET_BUTTON_URL, SELECT_BUTTON_TO_DELETE, EDIT_KEY) = range(11)

# --- توابع کمکی برای ساخت کیبورد ---

def build_guides_list_keyboard(guides: list) -> InlineKeyboardMarkup:
    keyboard = []
    it = iter(guides)
    for guide1 in it:
        row = []
        emojis1 = "".join(filter(None, ["📝" if guide1.get('content') else None, "🖼️" if guide1.get('photo_file_id') else None, "🔗" if guide1.get('buttons') else None]))
        if not emojis1: emojis1 = "📄"
        row.append(InlineKeyboardButton(f"{emojis1} {guide1['title']}", callback_data=f"guide_manage_{guide1['guide_key']}"))
        try:
            guide2 = next(it)
            emojis2 = "".join(filter(None, ["📝" if guide2.get('content') else None, "🖼️" if guide2.get('photo_file_id') else None, "🔗" if guide2.get('buttons') else None]))
            if not emojis2: emojis2 = "📄"
            row.append(InlineKeyboardButton(f"{emojis2} {guide2['title']}", callback_data=f"guide_manage_{guide2['guide_key']}"))
        except StopIteration:
            pass
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("➕ افزودن راهنمای جدید", callback_data="guide_add_new")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="guide_back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def build_guide_manage_keyboard(guide_key: str, guide: dict) -> InlineKeyboardMarkup:
    photo_text = "🖼️ افزودن/تغییر عکس" if not guide.get('photo_file_id') else "🖼️ تغییر/حذف عکس"
    
    final_keyboard_layout = [
        [InlineKeyboardButton("👁️‍🗨️ پیش‌نمایش برای کاربر", callback_data=f"guide_view_{guide_key}")],
        [
            InlineKeyboardButton("✏️ ویرایش عنوان", callback_data="guide_edit_title"), 
            InlineKeyboardButton("✍️ ویرایش متن", callback_data="guide_edit_content")
        ],
        [
            InlineKeyboardButton(photo_text, callback_data="guide_edit_photo"), 
            InlineKeyboardButton("🔗 تنظیم دکمه‌ها", callback_data="guide_edit_buttons")
        ],
        # Combine Delete and Back buttons into a single row
        [
            InlineKeyboardButton("🗑️ حذف کامل", callback_data=f"guide_delete_confirm_{guide_key}"),
            InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="guide_back_to_list")
        ]
    ]

    return InlineKeyboardMarkup(final_keyboard_layout)


def build_buttons_manage_keyboard(guide: dict) -> InlineKeyboardMarkup:
    keyboard = []
    buttons = guide.get('buttons') or []
    if not buttons:
        keyboard.append([InlineKeyboardButton("در حال حاضر هیچ دکمه‌ای وجود ندارد.", callback_data="noop")])

    keyboard.append([InlineKeyboardButton("➕ افزودن دکمه جدید", callback_data="guide_btn_add")])
    if buttons:
        keyboard.append([InlineKeyboardButton("🗑️ حذف یک دکمه", callback_data="guide_btn_delete_prompt")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به مدیریت راهنما", callback_data=f"guide_manage_{guide['guide_key']}")])
    return InlineKeyboardMarkup(keyboard)

# --- توابع اصلی مکالمه ---

async def start_guide_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guides = await db_manager.get_all_guides()
    text = "📚 **تنظیمات آموزش**\n\nاز این بخش می‌توانید راهنماهای آموزشی برای کاربران را مدیریت کنید."
    reply_markup = build_guides_list_keyboard(guides)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
    return LIST_GUIDES

# ==================== REPLACE THIS FUNCTION in modules/guides/actions.py ====================
async def show_guide_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the management panel for a specific guide."""
    query = update.callback_query
    # Split by a unique prefix to correctly extract the key
    guide_key = query.data.split('guide_manage_')[-1]
    context.user_data['current_guide_key'] = guide_key
    
    guide = await db_manager.get_guide(guide_key)
    if not guide:
        await query.answer("❌ راهنما یافت نشد.", show_alert=True)
        # Attempt to gracefully return to the main list
        return await start_guide_management(update, context)
        
    await query.answer()
    text = f"⚙️ **مدیریت راهنمای: {guide['title']}**"
    reply_markup = build_guide_manage_keyboard(guide_key, guide)
    
    # --- منطق جدید برای مدیریت بازگشت از پیام عکس ---
    if query.message.photo:
        # اگر پیام قبلی یک عکس بود (از پیش‌نمایش آمده)، آن را حذف کن و پیام جدید بفرست
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # اگر پیام قبلی متن بود، آن را ویرایش کن
        await query.edit_message_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
        
    return GUIDE_MENU
# =======================================================================================

async def prompt_for_new_guide_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    text = ("**مرحله ۱: شناسه یکتا**\n\nیک شناسه انگلیسی، کوتاه و بدون فاصله وارد کنید (مثلاً `android_guide`).\n\nاین شناسه قابل تغییر نیست.\nبرای لغو /cancel را ارسال کنید.")
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN); return EDIT_KEY

async def process_new_guide_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guide_key = update.message.text.strip().lower().replace(" ", "_")
    if not guide_key.isascii() or ' ' in guide_key or not guide_key:
        await update.message.reply_text("❌ شناسه نامعتبر است. لطفاً فقط از حروف انگلیسی و بدون فاصله استفاده کنید."); return EDIT_KEY
    existing_guide = await db_manager.get_guide(guide_key)
    if existing_guide:
        await update.message.reply_text("❌ این شناسه قبلاً استفاده شده است."); return EDIT_KEY
    
    context.user_data['current_guide_key'] = guide_key
    await db_manager.add_or_update_guide(guide_key, "عنوان موقت", "محتوای موقت")
    
    await update.message.reply_text(f"✅ راهنمای `{guide_key}` ایجاد شد. حالا می‌توانید جزئیات آن را تکمیل کنید.")
    
    guide = await db_manager.get_guide(guide_key)
    text = f"⚙️ **مدیریت راهنمای: {guide['title']}**"
    reply_markup = build_guide_manage_keyboard(guide_key, guide)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU

async def prompt_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action = query.data.split('_', 2)[2]
    prompts = {
        'title': ("✏️ **ویرایش عنوان**\n\nلطفاً عنوان جدید را وارد کنید.", EDIT_TITLE),
        'content': ("✍️ **ویرایش متن**\n\nلطفاً متن کامل جدید را وارد کنید.", EDIT_CONTENT),
        'photo': ("🖼️ **افزودن/تغییر عکس**\n\nلطفاً عکس جدید را ارسال کنید. برای حذف عکس فعلی، کلمه `حذف` را بفرستید.", EDIT_PHOTO),
    }
    if action not in prompts:
        await query.answer("❌ عملیات نامعتبر.", show_alert=True); return GUIDE_MENU
    prompt_text, next_state = prompts[action]
    await query.answer()
    await query.edit_message_text(prompt_text, parse_mode=ParseMode.MARKDOWN)
    return next_state

async def process_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guide_key = context.user_data['current_guide_key']
    new_title = update.message.text.strip()
    guide = await db_manager.get_guide(guide_key)
    await db_manager.add_or_update_guide(guide_key, new_title, guide.get('content'), guide.get('photo_file_id'), guide.get('buttons'))
    await update.message.reply_text("✅ عنوان با موفقیت به‌روزرسانی شد.")
    new_guide = await db_manager.get_guide(guide_key)
    text = f"⚙️ **مدیریت راهنمای: {new_guide['title']}**"
    await update.message.reply_text(text, reply_markup=build_guide_manage_keyboard(guide_key, new_guide), parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU

async def process_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guide_key = context.user_data['current_guide_key']
    new_content = update.message.text_html
    guide = await db_manager.get_guide(guide_key)
    await db_manager.add_or_update_guide(guide_key, guide['title'], new_content, guide.get('photo_file_id'), guide.get('buttons'))
    await update.message.reply_text("✅ متن با موفقیت به‌روزرسانی شد.")
    guide = await db_manager.get_guide(guide_key)
    text = f"⚙️ **مدیریت راهنمای: {guide['title']}**"
    await update.message.reply_text(text, reply_markup=build_guide_manage_keyboard(guide_key, guide), parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU
    
async def process_edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guide_key = context.user_data['current_guide_key']
    guide = await db_manager.get_guide(guide_key)
    new_photo_id = None
    if update.message.photo:
        new_photo_id = update.message.photo[-1].file_id
        feedback = "✅ عکس با موفقیت به‌روزرسانی شد."
    elif update.message.text and update.message.text.strip().lower() == 'حذف':
        new_photo_id = None
        feedback = "✅ عکس با موفقیت حذف شد."
    else:
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عکس ارسال کنید یا کلمه `حذف` را بنویسید."); return EDIT_PHOTO
    await db_manager.add_or_update_guide(guide_key, guide['title'], guide.get('content'), new_photo_id, guide.get('buttons'))
    await update.message.reply_text(feedback)
    guide = await db_manager.get_guide(guide_key)
    text = f"⚙️ **مدیریت راهنمای: {guide['title']}**"
    await update.message.reply_text(text, reply_markup=build_guide_manage_keyboard(guide_key, guide), parse_mode=ParseMode.MARKDOWN)
    return GUIDE_MENU

# ==================== ۱. این تابع را جایگزین کنید ====================
async def show_buttons_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
    # اگر از طریق کلیک روی دکمه آمده‌ایم، اطلاعات را از query می‌خوانیم
    if query:
        await query.answer()
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        context.user_data['guide_menu_message_id'] = message_id # ذخیره برای بازگشت‌ها
    # اگر از تابع دیگری (مثل ذخیره دکمه) آمده‌ایم، اطلاعات را از context می‌خوانیم
    else:
        chat_id = update.effective_chat.id
        message_id = context.user_data['guide_menu_message_id']

    guide_key = context.user_data['current_guide_key']
    guide = await db_manager.get_guide(guide_key)
    
    text = f"🔗 **تنظیم دکمه‌ها برای: {guide['title']}**"
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text, 
            reply_markup=build_buttons_manage_keyboard(guide), 
            parse_mode=ParseMode.MARKDOWN
        )
    except error.BadRequest as e:
        if "Message is not modified" not in str(e):
             LOGGER.error(f"Error editing buttons menu: {e}")

    return BUTTON_MENU

async def prompt_for_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    context.user_data['new_button'] = {}
    await query.edit_message_text("**مرحله ۱/۲: متن دکمه**\n\nلطفاً متنی که می‌خواهید روی دکمه نمایش داده شود را وارد کنید.")
    return GET_BUTTON_TEXT

async def get_button_text_and_prompt_for_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_button']['text'] = update.message.text.strip()
    sent_message = await update.message.reply_text(
        "**مرحله ۲/۲: لینک دکمه**\n\nلطفاً URL کامل (لینک) را وارد کنید (باید با http یا https شروع شود)."
    )
    # ذخیره message_id برای حذف در مرحله بعد
    context.user_data['last_bot_message_id'] = sent_message.message_id
    return GET_BUTTON_URL

# ==================== ۲. این تابع را نیز جایگزین کنید ====================
async def get_button_url_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ لینک نامعتبر است. لطفاً یک URL کامل وارد کنید.")
        return GET_BUTTON_URL
        
    context.user_data['new_button']['url'] = url
    
    guide_key = context.user_data['current_guide_key']
    guide = await db_manager.get_guide(guide_key)
    buttons = guide.get('buttons') or []
    buttons.append(context.user_data['new_button'])
    
    await db_manager.add_or_update_guide(
        guide_key, 
        guide['title'], 
        guide.get('content'), 
        guide.get('photo_file_id'), 
        buttons
    )
    
  
    try:
        await update.message.delete()
        if 'last_bot_message_id' in context.user_data:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data.pop('last_bot_message_id')
            )
    except Exception as e:
        LOGGER.warning(f"Could not delete messages during button save: {e}")

    # ارسال یک پیام جدید با منوی آپدیت شده
    new_guide = await db_manager.get_guide(guide_key)
    text = f"🔗 **تنظیم دکمه‌ها برای: {new_guide['title']}**"
    sent_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=build_buttons_manage_keyboard(new_guide),
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['buttons_menu_message'] = sent_message
    
    context.user_data.pop('new_button', None)
    return BUTTON_MENU
    
async def prompt_to_delete_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    guide_key = context.user_data['current_guide_key']
    guide = await db_manager.get_guide(guide_key)
    buttons = guide.get('buttons') or []
    if not buttons:
        await query.answer("هیچ دکمه‌ای برای حذف وجود ندارد.", show_alert=True); return BUTTON_MENU
    keyboard = [[InlineKeyboardButton(f"🗑️ حذف: {btn['text']}", callback_data=f"guide_btn_delete_do_{i}")] for i, btn in enumerate(buttons)]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"guide_edit_buttons")])
    await query.edit_message_text("لطفاً دکمه‌ای که می‌خواهید حذف شود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_BUTTON_TO_DELETE

async def do_delete_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    button_index = int(query.data.split('_')[-1])
    guide_key = context.user_data['current_guide_key']
    guide = await db_manager.get_guide(guide_key)
    buttons = guide.get('buttons') or []
    if 0 <= button_index < len(buttons):
        removed_btn = buttons.pop(button_index)
        await db_manager.add_or_update_guide(guide_key, guide['title'], guide.get('content'), guide.get('photo_file_id'), buttons)
        await query.answer(f"دکمه '{removed_btn['text']}' حذف شد.", show_alert=True)
    else:
        await query.answer("❌ خطای غیرمنتظره. دکمه یافت نشد.", show_alert=True)
    new_guide = await db_manager.get_guide(guide_key)
    await show_buttons_menu(update, context)
    return BUTTON_MENU

async def view_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    guide_key = context.user_data.get('current_guide_key') or query.data.split('guide_view_')[-1]
    guide = await db_manager.get_guide(guide_key)
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به مدیریت راهنما", callback_data=f"guide_manage_{guide_key}")]]
    if guide.get('buttons'):
        for btn in guide['buttons']: keyboard.insert(0, [InlineKeyboardButton(btn['text'], url=btn['url'])])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"**{guide['title']}**\n\n{guide.get('content') or ''}"
    
    if guide.get('photo_file_id'):
        await query.message.delete()
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=guide['photo_file_id'], caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    return GUIDE_MENU

async def confirm_delete_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    guide_key = context.user_data['current_guide_key']
    guide = await db_manager.get_guide(guide_key)
    keyboard = [[InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"guide_delete_do_{guide_key}"), InlineKeyboardButton("❌ خیر، بازگرد", callback_data=f"guide_manage_{guide_key}")]]
    await query.edit_message_text(f"⚠️ آیا از حذف راهنمای «{guide['title']}» مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_DELETE

async def do_delete_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    guide_key = query.data.split('_')[-1]
    success = await db_manager.delete_guide(guide_key)
    await query.answer("✅ راهنما با موفقیت حذف شد." if success else "❌ خطا در حذف.", show_alert=True)
    return await start_guide_management(update, context)

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    target_message = update.message or (query and query.message)
    if query:
        await query.answer(); await query.message.delete()
    await context.bot.send_message(chat_id=target_message.chat_id, text="به منوی اصلی بازگشتید.", reply_markup=get_admin_main_menu_keyboard())
    context.user_data.clear(); return ConversationHandler.END