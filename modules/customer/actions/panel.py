# FILE: modules/customer/actions/panel.py (نسخه اصلاح‌شده با منوی انتخاب نوع پلن)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- MODIFIED: Import both necessary keyboards ---
from shared.keyboards import get_customer_purchase_menu_keyboard, get_plan_type_selection_keyboard
from modules.general.actions import send_main_menu

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    منوی اصلی خرید و پرداخت مشتری را نمایش می‌دهد.
    این تابع همچنین به عنوان نقطه بازگشت از منوی انتخاب نوع پلن عمل می‌کند.
    """
    reply_markup = get_customer_purchase_menu_keyboard()
    
    text = "🛍️ *پنل خرید و پرداخت*\n\nاز این بخش می‌توانید سرویس جدید سفارش دهید یا رسید پرداخت خود را ارسال کنید."
    
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )

# --- NEW FUNCTION ---
async def show_plan_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    منوی انتخاب بین پلن حجمی و پلن نامحدود را نمایش می‌دهد.
    """
    query = update.callback_query
    await query.answer()

    # متن راهنما برای منوی جدید
    text = (
        "💡 *انتخاب نوع پلن*\n\n"
        "لطفاً نوع سرویس مورد نظر خود را انتخاب کنید:\n\n"
        "📊 **پلن حجمی:** سرویس با حجم و زمان دلخواه شما و قیمت‌گذاری هوشمند.\n"
        "💎 **پلن نامحدود:** سرویس با حجم بی‌نهایت و قابلیت انتخاب تعداد کاربر همزمان."
    )
    
    # دریافت کیبورد جدید از ماژول اشتراکی
    reply_markup = await get_plan_type_selection_keyboard()

    # ویرایش پیام فعلی و نمایش منوی جدید
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
# --- END NEW FUNCTION ---

async def close_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پنل خرید مشتری را می‌بندد و او را به منوی اصلی بازمی‌گرداند.
    """
    query = update.callback_query
    await query.answer()
    
    await send_main_menu(update, context, message_text="به منوی اصلی بازگشتید.")