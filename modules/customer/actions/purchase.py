# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# --- Local Imports ---
from config import config

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- CONSTANTS ---
CONFIRM_PURCHASE = range(1)

# ===== PURCHASE CONVERSATION FUNCTIONS =====

async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the purchase conversation, triggered by a main menu button
    or a callback from a broadcast message.
    """
    keyboard = [
        [InlineKeyboardButton("✅ بله، درخواست را ارسال کن", callback_data="confirm_purchase_request")],
        [InlineKeyboardButton("❌ خیر، منصرف شدم", callback_data="cancel_purchase_request")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "آیا از درخواست خرید اشتراک جدید اطمینان دارید؟"

    query = update.callback_query
    if query:
        # Flow for CallbackQuery (e.g., from a broadcast button)
        await query.answer()
        # Send a new message, as we can't edit the original broadcast message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        # Flow for Message (from the main menu button)
        await update.message.reply_text(text, reply_markup=reply_markup)

    return CONFIRM_PURCHASE

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirms the purchase request, notifies admins, and ends the conversation."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    await query.edit_message_text(
        "✅ درخواست شما برای خرید اشتراک با موفقیت برای ادمین ارسال شد.\n\n"
        "لطفاً منتظر بمانید، به زودی با شما تماس گرفته خواهد شد."
    )

    if config.AUTHORIZED_USER_IDS:
        user_info = f"کاربر {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\nUser ID: `{user.id}`"

        message_to_admin = (
            f"🔔 **درخواست خرید جدید** 🔔\n\n"
            f"{user_info}\n\n"
            "این کاربر قصد خرید اشتراک جدید را دارد."
        )
        # Provide a convenient button for the admin to create a config for this user
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ساخت کانفیگ برای این کاربر", callback_data=f"create_user_for_{user.id}")]
        ])

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_to_admin,
                    reply_markup=admin_keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send purchase notification to admin {admin_id} for user {user.id}: {e}", exc_info=True)

    return ConversationHandler.END

async def cancel_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the purchase request and ends the conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("درخواست خرید اشتراک لغو شد.")
    return ConversationHandler.END

# ===== OTHER ACTION FUNCTIONS =====
async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Support' button, providing a link to the support username."""
    if config.SUPPORT_USERNAME:
        # Ensure the username is clean and doesn't have a leading '@'
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
        # This case should ideally not be reached if the button isn't shown, but it's a good fallback.
        await update.message.reply_text("متاسفانه در حال حاضر امکان ارتباط با پشتیبانی وجود ندارد.")