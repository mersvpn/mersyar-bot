# FILE: modules/customer/actions/purchase.py
# (نسخه نهایی با بازگشت صحیح به منوی اصلی و رفع خطای پارسر)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from config import config
# Import both admin and customer keyboards
from shared.keyboards import get_customer_main_menu_keyboard, get_admin_main_menu_keyboard
from . import panel

LOGGER = logging.getLogger(__name__)

CONFIRM_PURCHASE = 0 # Simplified state machine

async def _send_final_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Helper function to send the correct main menu (admin or customer) at the end of a conversation.
    """
    user_id = update.effective_user.id
    
    # Decide which keyboard to show based on user's role
    if user_id in config.AUTHORIZED_USER_IDS:
        final_keyboard = get_admin_main_menu_keyboard()
        message_text = "شما به منوی اصلی ادمین بازگشتید."
    else:
        final_keyboard = get_customer_main_menu_keyboard()
        message_text = "شما به منوی اصلی بازگشتید."

    await context.bot.send_message(
        chat_id=user_id,
        text=message_text,
        reply_markup=final_keyboard
    )

async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the purchase conversation by EDITING the customer panel message.
    """
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("✅ بله، درخواست را ارسال کن", callback_data="confirm_purchase_request")],
        [InlineKeyboardButton("❌ خیر، بازگشت", callback_data="back_to_customer_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "آیا از درخواست خرید اشتراک جدید اطمینان دارید؟"

    await query.edit_message_text(text=text, reply_markup=reply_markup)

    return CONFIRM_PURCHASE

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Confirms the purchase, notifies admin, and properly ends the conversation by showing the main menu.
    """
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    await query.edit_message_text(
        "✅ درخواست شما برای خرید اشتراک با موفقیت برای ادمین ارسال شد.\n\n"
        "لطفاً منتظر بمانید، به زودی با شما تماس گرفته خواهد شد."
    )

    if config.AUTHORIZED_USER_IDS:
        safe_full_name = escape_markdown(user.full_name, version=2)
        user_info = f"کاربر {safe_full_name}"
        if user.username:
            safe_username = escape_markdown(user.username, version=2)
            user_info += f" \(@{safe_username}\)"
        
        user_info += f"\nUser ID: `{user.id}`"

        message_to_admin = (
            f"🔔 *درخواست خرید جدید* 🔔\n\n"
            f"{user_info}\n\n"
            "این کاربر قصد خرید اشتراک جدید را دارد\."
        )
        
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ساخت کانفیگ برای این کاربر", callback_data=f"create_user_for_{user.id}")]
        ])

        # ======================== START: FIX for notification logic ========================
        # The conditional "if admin_id != user.id" is removed to ensure the message is always sent.
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_to_admin,
                    reply_markup=admin_keyboard,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception as e:
                LOGGER.error(f"Failed to send purchase notification to admin {admin_id} for user {user.id}: {e}", exc_info=True)
        # ========================= END: FIX for notification logic =========================

    await _send_final_menu_message(update, context)

    return ConversationHandler.END


async def cancel_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancels the purchase request and properly ends the conversation by showing the main menu.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("درخواست خرید اشتراک لغو شد.")

    await _send_final_menu_message(update, context)
    
    return ConversationHandler.END

async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if config.SUPPORT_USERNAME:
        clean_username = config.SUPPORT_USERNAME.lstrip('@')
        support_link = f"https://t.me/{clean_username}"
        message = (
            "برای ارتباط با تیم پشتیبانی و دریافت راهنمایی، لطفاً روی لینک زیر کلیک کنید:\n\n"
            f"➡️ **[@{clean_username}]({support_link})** ⬅️"
        )
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text("متاسفانه در حال حاضر امکان ارتباط با پشتیبانی وجود ندارد.")