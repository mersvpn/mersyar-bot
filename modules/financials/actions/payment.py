# FILE: modules/financials/actions/payment.py
# (نسخه کامل و نهایی با تمام توابع و فاصله‌گذاری صحیح)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode

from modules.marzban.actions.data_manager import load_financials
from shared.keyboards import get_admin_main_menu_keyboard, get_customer_main_menu_keyboard
from modules.general.actions import start as back_to_main_menu_action
from config import config

LOGGER = logging.getLogger(__name__)

GET_PRICE = 0

async def start_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.effective_user

    if not user or user.id not in config.AUTHORIZED_USER_IDS:
        if query:
            await query.answer("⛔️ شما اجازه دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    
    try:
        prefix, customer_id, marzban_username = query.data.split(':', 2)
        if prefix != "fin_send_req": raise ValueError("Invalid callback data")
    except (ValueError, IndexError):
        LOGGER.error(f"Invalid callback data for payment request: {query.data}")
        await query.edit_message_text("❌ خطا: اطلاعات دکمه نامعتبر است.")
        return ConversationHandler.END
        
    context.user_data['payment_info'] = {'customer_id': int(customer_id), 'marzban_username': marzban_username}
    
    await query.edit_message_text(
        text=f"در حال آماده‌سازی پیام پرداخت برای کاربر `{marzban_username}`.\n\nلطفاً **مبلغ اشتراک** را به تومان وارد کنید (فقط عدد):",
        parse_mode=ParseMode.MARKDOWN
    )
    return GET_PRICE

async def send_payment_details_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    payment_info = context.user_data.get('payment_info')
    if not payment_info:
        await update.message.reply_text("❌ خطا: اطلاعات کاربر یافت نشد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
        
    customer_id = payment_info['customer_id']
    price_str = update.message.text.strip()
    
    try:
        price_int = int(price_str)
        formatted_price = f"{price_int:,}"
    except ValueError:
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً مبلغ را فقط به صورت عدد وارد کنید.")
        return GET_PRICE
        
    financials = await load_financials()
    card_holder = financials.get("card_holder")
    card_number = financials.get("card_number")
    extra_text = "راهنمای پرداخت"

    if not all([card_holder, card_number]):
        await update.message.reply_text(
            "❌ **خطا: اطلاعات مالی (نام صاحب حساب یا شماره کارت) تنظیم نشده است.**",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    try:
        payment_message = (
            f"**پرداخت هزینه اشتراک**\n\n"
            f"مبلغ قابل پرداخت: **{formatted_price} تومان**\n\n"
            f"▫️ **نام صاحب حساب:** {card_holder}\n"
            f"▫️ **شماره کارت:** `{card_number}`\n\n"
            f"_{extra_text}_\n\n"
            "⚠️ لطفاً پس از پرداخت، **عکس رسید** را در همین گفتگو ارسال نمایید."
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💳 کپی شماره کارت", callback_data=f"copy_text:{card_number}"),
                InlineKeyboardButton("💰 کپی مبلغ", callback_data=f"copy_text:{price_int}")
            ],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="payment_back_to_menu")]
        ])
        
        await context.bot.send_message(
            chat_id=customer_id, text=payment_message,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
        await update.message.reply_text(f"✅ پیام پرداخت با موفقیت برای کاربر (ID: {customer_id}) ارسال شد.")
        
    except Exception as e:
        LOGGER.error(f"Failed to send payment details to customer {customer_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ خطا در ارسال پیام به مشتری.")
    
    context.user_data.clear()
    await update.message.reply_text("به منوی اصلی بازگشتید:", reply_markup=get_admin_main_menu_keyboard())
    return ConversationHandler.END

async def cancel_payment_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات ارسال اطلاعات پرداخت لغو شد.", reply_markup=get_admin_main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

payment_request_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_payment_request, pattern=r'^fin_send_req:')],
    states={
        GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_payment_details_to_user)]
    },
    fallbacks=[
        CommandHandler('cancel', cancel_payment_request),
        CommandHandler('start', back_to_main_menu_action)
    ],
    conversation_timeout=300,
    per_user=True,
    per_chat=True
)

async def send_renewal_invoice_to_user(context: ContextTypes.DEFAULT_TYPE, user_telegram_id: int, username: str, renewal_days: int, price: int):
    """
    Sends an invoice to the user after the admin renews their service.
    This version has updated text and a direct action button.
    """
    financials = await load_financials()
    card_holder = financials.get("card_holder", "تنظیم نشده")
    card_number = financials.get("card_number", "تنظیم نشده")
    
    if card_number == "تنظیم نشده":
        LOGGER.warning(f"Attempted to send invoice for {username} but financials are not set.")
        return

    formatted_price = f"{price:,}"
    invoice_text = (
        f"✅ سرویس شما با نام کاربری `{username}` با موفقیت برای **{renewal_days} روز** دیگر تمدید شد.\n\n"
        f"🧾 **صورتحساب:**\n"
        f" - مبلغ قابل پرداخت: `{formatted_price}` تومان\n"
        f" - شماره کارت: `{card_number}`\n"
        f" - به نام: `{card_holder}`\n\n"
        f"لطفاً پس از واریز، با استفاده از دکمه زیر، رسید خود را برای ما ارسال کنید."
    )
    customer_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="start_receipt_upload")]
    ])

    try:
        await context.bot.send_message(
            chat_id=user_telegram_id,
            text=invoice_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=customer_keyboard
        )
        LOGGER.info(f"Renewal invoice sent to user {user_telegram_id} for username {username}.")
    except Exception as e:
        LOGGER.error(f"Failed to send renewal invoice to {user_telegram_id} for user {username}: {e}")

async def handle_copy_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text_to_copy = query.data.split(':', 1)[1]
    await query.answer(text=f"کپی شد:\n{text_to_copy}", show_alert=True)

async def handle_payment_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="به منوی اصلی بازگشتید.",
        reply_markup=get_customer_main_menu_keyboard()
    )

async def send_manual_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends a pre-filled invoice to a customer based on their saved subscription details.
    Triggered by the admin from the user details panel.
    """
    query = update.callback_query
    await query.answer()

    username = query.data.split('_', 2)[-1]

    from modules.marzban.actions.data_manager import load_users_map, normalize_username
    users_map = await load_users_map()
    customer_id = users_map.get(normalize_username(username))
    if not customer_id:
        await query.answer(f"❌ کاربر تلگرام برای {username} یافت نشد.", show_alert=True)
        return

    from database.db_manager import get_user_note
    note_data = await get_user_note(normalize_username(username))
    price = note_data.get('subscription_price')
    duration = note_data.get('subscription_duration')

    if not price or not duration:
        await query.answer("❌ اطلاعات اشتراک (قیمت و مدت) برای این کاربر ثبت نشده است.", show_alert=True)
        return

    financials = await load_financials()
    card_holder = financials.get("card_holder", "تنظیم نشده")
    card_number = financials.get("card_number", "تنظیم نشده")
    
    if card_number == "تنظیم نشده":
        await query.answer("❌ اطلاعات مالی (شماره کارت) در ربات تنظیم نشده است.", show_alert=True)
        return

    formatted_price = f"{price:,}"
    invoice_text = (
        f"🧾 **صورتحساب اشتراک**\n\n"
        f"▫️ **سرویس:** `{username}`\n"
        f"▫️ **دوره:** {duration} روزه\n"
        f"▫️ **مبلغ قابل پرداخت:** `{formatted_price}` تومان\n\n"
        f"**پرداخت به:**\n"
        f" - شماره کارت: `{card_number}`\n"
        f" - به نام: `{card_holder}`\n\n"
        f"لطفاً پس از واریز، با استفاده از دکمه زیر، رسید خود را برای ما ارسال کنید."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="start_receipt_upload")]
    ])

    try:
        await context.bot.send_message(
            chat_id=customer_id,
            text=invoice_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        await query.answer("✅ صورتحساب با موفقیت برای کاربر ارسال شد.", show_alert=True)
    except Exception as e:
        LOGGER.error(f"Failed to send manual invoice to customer {customer_id} for user {username}: {e}")
        await query.answer(f"❌ خطا در ارسال پیام به کاربر. (ID: {customer_id})", show_alert=True)