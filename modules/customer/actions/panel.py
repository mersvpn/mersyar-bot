# FILE: modules/customer/actions/panel.py (نسخه اصلاح شده)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# ایمپورت کردن کیبورد جدید از ماژول اشتراکی
from shared.keyboards import get_customer_purchase_menu_keyboard

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    منوی اصلی خرید و پرداخت مشتری را با گزینه‌های جدید نمایش می‌دهد.
    """
    # استفاده مستقیم از تابع جدید برای ساخت کیبورد
    reply_markup = get_customer_purchase_menu_keyboard()
    
    # به‌روزرسانی متن پیام برای هماهنگی با گزینه‌های جدید
    text = "🛍️ *پنل خرید و پرداخت*\n\nاز این بخش می‌توانید سرویس جدید سفارش دهید یا رسید پرداخت خود را ارسال کنید."
    
    query = update.callback_query
    if query:
        # اگر از طریق دکمه بازگشت فراخوانی شود، پیام قبلی ویرایش می‌شود
        await query.answer()
        await query.edit_message_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # اگر از منوی اصلی فراخوانی شود، پیام جدیدی ارسال می‌شود
        await update.message.reply_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )


async def close_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پیام پنل خرید مشتری را می‌بندد (حذف می‌کند).
    این تابع بدون تغییر باقی می‌ماند.
    """
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        # در صورتی که پیام قبلاً حذف شده باشد، خطایی رخ ندهد
        pass