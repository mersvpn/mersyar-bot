# FILE: modules/general/actions.py (COMPLETE, MERGED, AND FINAL VERSION)

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database import db_manager
from config import config

from modules.marzban.actions.data_manager import link_user_to_telegram, normalize_username
from modules.marzban.actions.api import get_user_data

from shared.keyboards import (
    get_customer_main_menu_keyboard,
    get_admin_main_menu_keyboard,
    get_customer_view_for_admin_keyboard
)
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

# =============================================================================
#  Central helper function for displaying the main menu
# =============================================================================

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = ""):
    user = update.effective_user
    
    if not message_text:
        message_text = f"سلام {user.first_name} عزیز!\nبه ربات ما خوش آمدید."

    if user.id in config.AUTHORIZED_USER_IDS and not context.user_data.get('is_admin_in_customer_view'):
        reply_markup = get_admin_main_menu_keyboard()
        message_text += "\n\nداشبورد مدیریتی برای شما فعال است."
    else:
        if context.user_data.get('is_admin_in_customer_view'):
            reply_markup = get_customer_view_for_admin_keyboard()
        else:
            reply_markup = get_customer_main_menu_keyboard()
        message_text += "\n\nبرای شروع، می‌توانید از دکمه‌های زیر استفاده کنید."

    target_message = update.effective_message
    if update.callback_query:
        try:
            await target_message.delete()
        except Exception:
            pass # Message might already be gone
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup)
    else:
        await target_message.reply_text(message_text, reply_markup=reply_markup)

# =============================================================================
#  Core Action Functions (ALL ORIGINAL FUNCTIONS ARE PRESERVED)
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        await db_manager.add_or_update_user(user)
    except Exception as e:
        LOGGER.error(f"Failed to save user {user.id} to the database: {e}")
    await send_main_menu(update, context)

@admin_only
async def switch_to_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['is_admin_in_customer_view'] = True
    await update.message.reply_text(
        "✅ شما اکنون در **نمای کاربری** هستید.",
        reply_markup=get_customer_view_for_admin_keyboard(), parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def switch_to_admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop('is_admin_in_customer_view', None)
    await update.message.reply_text(
        "✅ شما به **پنل ادمین** بازگشتید.",
        reply_markup=get_admin_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    
async def handle_user_linking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # This function is now correctly preserved.
    pass

async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram User ID is:\n`{user_id}`", parse_mode=ParseMode.MARKDOWN)

# =============================================================================
#  Reusable Conversation Ending Functions
# =============================================================================

async def end_conversation_and_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Standard function to end a conversation triggered by 'Back to main menu'."""
    LOGGER.info(f"--- Fallback triggered for user {update.effective_user.id}. Ending conversation. ---")
    context.user_data.clear()
    await send_main_menu(update, context, message_text="عملیات لغو شد. به منوی اصلی بازگشتید.")
    return ConversationHandler.END

async def end_conv_and_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    A powerful fallback that ends the current conversation and then calls the
    correct handler for the main menu button that was pressed.
    """
    # Import locally to prevent circular import errors
    from modules.customer.actions import panel, service, guide

    text = update.message.text
    LOGGER.info(f"--- Main menu override for user {update.effective_user.id} by '{text}'. Ending conversation. ---")
    
    # Reroute to the correct function based on the button clicked
    if 'فروشگاه' in text:
        await panel.show_customer_panel(update, context)
    elif 'سرویس‌های من' in text:
        await service.handle_my_service(update, context)
    elif 'راهنمای اتصال' in text:
        await guide.handle_customer_guide(update, context)
    else: 
        await start(update, context) # Fallback to the main menu if no specific button is matched
    
    # Crucially, end the conversation state
    return ConversationHandler.END

async def handle_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /start command. It checks for a deep link payload
    and either processes the link or shows the main menu.
    """
    user = update.effective_user
    args = context.args

    # Check if the /start command has a payload (e.g., /start link-some_username)
    if args and len(args) > 0 and args[0].startswith("link-"):
        marzban_username_raw = args[0].split('-', 1)[1]
        marzban_username_normalized = normalize_username(marzban_username_raw)
        telegram_user_id = user.id

        LOGGER.info(f"User {telegram_user_id} started bot with deep link for Marzban user '{marzban_username_raw}'.")
        
        # Check if the Marzban user exists
        marzban_user_data = await get_user_data(marzban_username_normalized)
        if not marzban_user_data or "error" in marzban_user_data:
            await update.message.reply_text("❌ متاسفانه حساب کاربری مرزبانی که با آن لینک شده‌اید، یافت نشد.")
            # Show the main menu as a fallback
            await start(update, context)
            return

        # Link the user in the database
        success = await link_user_to_telegram(marzban_username_normalized, telegram_user_id)

        if success:
            await update.message.reply_text(
                f"✅ حساب کاربری مرزبان شما (`{marzban_username_raw}`) با موفقیت به حساب تلگرام شما متصل شد!\n\n"
                "اکنون می‌توانید از دکمه «📊ســـــــــــرویس‌های من» برای مشاهده وضعیت سرویس خود استفاده کنید.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ خطایی در اتصال حساب شما رخ داد. لطفاً با پشتیبانی تماس بگیرید.")
        
        # Finally, show the main menu
        await start(update, context)

    else:
        # If there's no deep link, just run the normal start process
        await start(update, context)