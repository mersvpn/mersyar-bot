# FILE: modules/customer/actions/purchase.py (REVISED AND CORRECTED)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from config import config
from shared.keyboards import (
    get_back_to_main_menu_keyboard,
    get_customer_shop_keyboard 
)

LOGGER = logging.getLogger(__name__)

CONFIRM_PURCHASE = 0

async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the purchase conversation and presents confirmation buttons.
    """
    keyboard = [
        [InlineKeyboardButton("✅ بله، درخواست را ارسال کن", callback_data="confirm_purchase_request")],
        [InlineKeyboardButton("❌ خیر، بازگشت به فروشگاه", callback_data="back_to_shop_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "آیا از درخواست خرید اشتراک جدید اطمینان دارید؟"

    await update.message.reply_text(
        text=text, 
        reply_markup=reply_markup
    )
    
    # Send another message to change the reply keyboard for the duration of the conversation
    await update.message.reply_text(
        "برای لغو کلی و بازگشت به منوی اصلی از دکمه زیر استفاده کنید.",
        reply_markup=get_back_to_main_menu_keyboard()
    )

    return CONFIRM_PURCHASE

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Confirms the purchase, notifies admin, and ends the conversation.
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

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=message_to_admin,
                    reply_markup=admin_keyboard, parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception as e:
                LOGGER.error(f"Failed to send purchase notification to admin {admin_id}: {e}")
    
    return ConversationHandler.END

async def back_to_shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the 'back_to_shop_menu' callback.
    Deletes the inline message and sends a new message with the shop keyboard.
    """
    query = update.callback_query
    await query.answer()
    
    # Delete the confirmation message to clean up the chat
    await query.message.delete()
    
    # Send a new message to restore the shop keyboard
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="به فروشگاه بازگشتید.",
        reply_markup=get_customer_shop_keyboard()
    )
    
    return ConversationHandler.END

async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if config.SUPPORT_USERNAME:
        clean_username = config.SUPPORT_USERNAME.lstrip('@')
        support_link = f"https://t.me/{clean_username}"
        message = (
            "برای ارتباط با تیم پشتیبانی و دریافت راهنمایی، لطفاً روی لینک زیر کلیک کنید:\n\n"
            f"➡️ **[@{clean_username}]({support_link})** ⬅️"
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await update.message.reply_text("متاسفانه در حال حاضر امکان ارتباط با پشتیبانی وجود ندارد.")