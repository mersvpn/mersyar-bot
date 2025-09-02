# FILE: modules/customer/actions/guide.py (نسخه نهایی با import صحیح)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes # <-- مطمئن شوید این خط وجود دارد
from telegram.constants import ParseMode

from database import db_manager

LOGGER = logging.getLogger(__name__)

# ==================== REPLACE THIS FUNCTION in modules/customer/actions/guide.py ====================
async def show_guides_to_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches guides from DB and displays them as a two-column keyboard to the customer."""
    query = update.callback_query
    
    guides = await db_manager.get_all_guides()

    message_text = "📚 لطفاً راهنمای مورد نظر خود را انتخاب کنید:"
    keyboard = []

    if not guides:
        message_text = "در حال حاضر هیچ راهنمایی ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید."
    else:
        # --- منطق جدید برای ساخت کیبورد دو ستونه ---
        it = iter(guides)
        for guide1 in it:
            row = []
            row.append(InlineKeyboardButton(guide1['title'], callback_data=f"customer_show_guide_{guide1['guide_key']}"))
            try:
                # تلاش برای گرفتن آیتم بعدی برای ستون دوم
                guide2 = next(it)
                row.append(InlineKeyboardButton(guide2['title'], callback_data=f"customer_show_guide_{guide2['guide_key']}"))
            except StopIteration:
                # اگر تعداد راهنماها فرد باشد، ردیف آخر یک دکمه خواهد داشت
                pass
            keyboard.append(row)
        # --- پایان منطق جدید ---
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="customer_back_to_main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # منطق ارسال/ویرایش پیام بدون تغییر باقی می‌ماند
    if query:
        await query.answer()
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=message_text,
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )
# ====================================================================================================

# ==================== REPLACE THIS FUNCTION in modules/customer/actions/guide.py ====================
async def send_guide_content_to_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the content of a selected guide, with photo and buttons, to the customer."""
    query = update.callback_query
    await query.answer()
    
    guide_key = query.data.split('customer_show_guide_')[-1]
    
    guide = await db_manager.get_guide(guide_key)
    
    if not guide:
        await query.edit_message_text("❌ متاسفانه این راهنما یافت نشد.")
        return

    # --- منطق جدید برای ساخت دک-مه‌های سفارشی ---
    keyboard = []
    custom_buttons = guide.get('buttons')
    if custom_buttons and isinstance(custom_buttons, list):
        for btn_data in custom_buttons:
            # برای هر دکمه یک ردیف جداگانه ایجاد می‌کنیم
            keyboard.append([
                InlineKeyboardButton(btn_data['text'], url=btn_data['url'])
            ])

    # دکمه بازگشت همیشه در انتها اضافه می‌شود
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست راهنماها", callback_data="customer_back_to_guides")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    # --- پایان منطق جدید ---

    content = guide.get('content') or ""
    photo_file_id = guide.get('photo_file_id')

    # اگر راهنما عکس داشت
    if photo_file_id:
        # پیام قبلی (لیست دکمه‌ها) را حذف می‌کنیم
        await query.message.delete()
        # و یک پیام جدید با عکس ارسال می‌کنیم
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo_file_id,
            caption=content,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    # اگر راهنما فقط متن داشت
    else:
        await query.edit_message_text(
            text=content,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
# ====================================================================================================