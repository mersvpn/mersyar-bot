# FILE: modules/financials/actions/payment.py (نسخه نهایی با رفع مشکل بازگشت به پنل ادمین)
import qrcode
import io
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from modules.marzban.actions.api import add_data_to_user_api

# --- Local Imports ---
from database.db_manager import (
    load_financials, get_pending_invoice, update_invoice_status,
    link_user_to_telegram, get_user_note, get_telegram_id_from_marzban_username,
    create_pending_invoice
)
from shared.keyboards import get_admin_main_menu_keyboard
# --- FIX: Import the new central menu function and remove the old keyboard import ---
from modules.general.actions import send_main_menu, start as back_to_main_menu_action
from config import config
from modules.marzban.actions.add_user import create_marzban_user_from_template

LOGGER = logging.getLogger(__name__)

# =============================================================================
#  مکالمه ارسال صورتحساب دستی توسط ادمین
# =============================================================================
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
    marzban_username = payment_info['marzban_username']
    price_str = update.message.text.strip()
    
    try:
        price_int = int(price_str)
        if price_int <= 0: raise ValueError("Price must be positive.")
        formatted_price = f"{price_int:,}"
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً مبلغ را فقط به صورت عدد مثبت وارد کنید.")
        return GET_PRICE
        
    financials = await load_financials()
    card_holder = financials.get("card_holder")
    card_number = financials.get("card_number")

    if not all([card_holder, card_number]):
        await update.message.reply_text(
            "❌ **خطا: اطلاعات مالی (نام صاحب حساب یا شماره کارت) تنظیم نشده است.**",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    user_note = await get_user_note(marzban_username)
    if not user_note:
        LOGGER.error(f"Could not find user_note for manually created user '{marzban_username}' when sending invoice.")
        await update.message.reply_text(f"❌ خطا: اطلاعات اشتراک برای کاربر `{marzban_username}` یافت نشد.")
        return ConversationHandler.END

    plan_details = {
        'username': marzban_username,
        'volume': user_note.get('subscription_data_limit_gb', 0),
        'duration': user_note.get('subscription_duration', 0)
    }

    invoice_id = await create_pending_invoice(customer_id, plan_details, price_int)
    if not invoice_id:
        LOGGER.error(f"Failed to create pending_invoice for manual user '{marzban_username}'.")
        await update.message.reply_text("❌ خطا در ایجاد فاکتور در دیتابیس.")
        return ConversationHandler.END

    LOGGER.info(f"Created pending invoice #{invoice_id} for manually added user '{marzban_username}'.")

    try:
        payment_message = (
            f"🧾 *صورتحساب اشتراک*\n"
            f"*شماره فاکتور: `{invoice_id}`*\n\n"
            f"▫️ **سرویس:** `{marzban_username}`\n"
            f"▫️ **مبلغ قابل پرداخت:** `{formatted_price}` تومان\n\n"
            f"**اطلاعات پرداخت:**\n"
            f" \- شماره کارت: `{card_number}`\n"
            f" \- به نام: `{card_holder}`\n\n"
            "لطفاً پس از واریز، با استفاده از دکمه زیر، رسید خود را برای ما ارسال کنید."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="customer_send_receipt")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="payment_back_to_menu")]
        ])
        
        await context.bot.send_message(
            chat_id=customer_id, text=payment_message,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
        await update.message.reply_text(f"✅ فاکتور #{invoice_id} با موفقیت برای کاربر (ID: {customer_id}) ارسال شد.")
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

async def send_renewal_invoice_to_user(context: ContextTypes.DEFAULT_TYPE, user_telegram_id: int, username: str, renewal_days: int, price: int, data_limit_gb: int):
    """
    Creates a pending invoice and sends it to the user after a successful renewal.
    """
    try:
        financials = await load_financials()
        card_holder = financials.get("card_holder")
        card_number = financials.get("card_number")

        if not card_holder or not card_number:
            LOGGER.error(f"Cannot send renewal invoice to {username} ({user_telegram_id}) because financial settings are not configured.")
            return

        plan_details = {
            'username': username,
            'volume': data_limit_gb,
            'duration': renewal_days
        }
        invoice_id = await create_pending_invoice(user_telegram_id, plan_details, price)
        if not invoice_id:
            LOGGER.error(f"Failed to create a pending invoice for user {username} during renewal.")
            return

        formatted_price = f"{price:,}"
        invoice_text = (
            f"🧾 *صورتحساب تمدید اشتراک*\n"
            f"*شماره فاکتور: `{invoice_id}`*\n\n"
            f"▫️ **سرویس:** `{username}`\n"
            f"▫️ **دوره تمدید:** {renewal_days} روز\n"
            f"▫️ **مبلغ قابل پرداخت:** `{formatted_price}` تومان\n\n"
            f"**اطلاعات پرداخت:**\n"
            f" \- شماره کارت: `{card_number}`\n"
            f" \- به نام: `{card_holder}`\n\n"
            "لطفاً پس از واریز، با استفاده از دکمه زیر، رسید خود را برای ما ارسال کنید."
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="customer_send_receipt")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="payment_back_to_menu")]
        ])

        await context.bot.send_message(
            chat_id=user_telegram_id,
            text=invoice_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        LOGGER.info(f"Renewal invoice #{invoice_id} successfully sent to user {username} ({user_telegram_id}).")

    except TelegramError as e:
        if "bot was blocked by the user" in str(e).lower():
            LOGGER.warning(f"Could not send renewal invoice to {user_telegram_id} because the user has blocked the bot.")
        else:
            LOGGER.error(f"A Telegram error occurred while sending renewal invoice to {user_telegram_id}: {e}", exc_info=True)
    except Exception as e:
        LOGGER.error(f"An unexpected error occurred in send_renewal_invoice_to_user for user {username}: {e}", exc_info=True)

async def handle_copy_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass

# --- FIX: تابع handle_payment_back_button اصلاح شد تا از تابع کمکی مرکزی استفاده کند ---
async def handle_payment_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # به جای ارسال مستقیم کیبورد، تابع کمکی را فراخوانی می‌کنیم
    await send_main_menu(update, context, message_text="به منوی اصلی بازگشتید.")

async def send_manual_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_', 2)[-1]
    admin_chat_id = update.effective_chat.id
    try:
        customer_id = await get_telegram_id_from_marzban_username(username)
        if not customer_id:
            await context.bot.send_message(admin_chat_id, f"❌ **خطا:** کاربر تلگرام برای `{username}` یافت نشد.", parse_mode=ParseMode.MARKDOWN)
            return
            
        note_data = await get_user_note(username)
        price = note_data.get('subscription_price')
        duration = note_data.get('subscription_duration')
        
        if not price or not duration:
            callback_string = f"fin_send_req:{customer_id}:{username}"
            admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💰 ایجاد و ارسال صورتحساب", callback_data=callback_string)]])
            await context.bot.send_message(admin_chat_id, 
                f"اطلاعات اشتراک برای `{username}` ثبت نشده است. لطفاً به صورت دستی یک صورتحساب برای او ایجاد کنید.", 
                reply_markup=admin_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            return

        financials = await load_financials()
        card_holder = financials.get("card_holder", "تنظیم نشده")
        card_number = financials.get("card_number", "تنظیم نشده")
        
        if card_number == "تنظیم نشده":
            await context.bot.send_message(admin_chat_id, "❌ **خطا:** اطلاعات مالی تنظیم نشده است.", parse_mode=ParseMode.MARKDOWN)
            return

        plan_details = {
            'username': username,
            'volume': note_data.get('subscription_data_limit_gb', 0),
            'duration': duration
        }
        invoice_id = await create_pending_invoice(customer_id, plan_details, price)
        if not invoice_id:
            await context.bot.send_message(admin_chat_id, "❌ **خطا:** ایجاد فاکتور در دیتابیس با مشکل مواجه شد.")
            return

        formatted_price = f"{price:,}"
        invoice_text = (
            f"🧾 *صورتحساب اشتراک*\n"
            f"*شماره فاکتور: `{invoice_id}`*\n\n"
            f"▫️ **سرویس:** `{username}`\n▫️ **دوره:** {duration} روزه\n"
            f"▫️ **مبلغ قابل پرداخت:** `{formatted_price}` تومان\n\n"
            f"**پرداخت به:**\n - شماره کارت: `{card_number}`\n - به نام: `{card_holder}`\n\n"
            f"لطفاً پس از واریز، با استفاده از دکمه زیر، رسید خود را برای ما ارسال کنید."
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="customer_send_receipt")]])
        await context.bot.send_message(chat_id=customer_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        await context.bot.send_message(admin_chat_id, f"✅ فاکتور #{invoice_id} با موفقیت برای کاربر `{username}` (ID: {customer_id}) ارسال شد.", parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        LOGGER.error(f"Failed to send manual invoice for user {username}: {e}", exc_info=True)
        await context.bot.send_message(admin_chat_id, f"❌ **خطای ناشناخته**.", parse_mode=ParseMode.MARKDOWN)

async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # No need to import save_subscription_note here, it's handled inside the logic
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer("⏳ در حال پردازش تاییدیه...")

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        LOGGER.error(f"Invalid invoice_id in callback data: {query.data}")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا:** شماره فاکتور نامعتبر است.")
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=query.message.caption + "\n\n⚠️ **این فاکتور قبلاً پردازش شده یا یافت نشد.**")
        return

    customer_id = invoice['user_id']
    plan_details = invoice['plan_details']
    marzban_username = plan_details.get('username')

    if not marzban_username:
        LOGGER.error(f"Invoice #{invoice_id} has no username in plan_details.")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا:** نام کاربری در اطلاعات فاکتور یافت نشد.")
        return

    from modules.marzban.actions.api import get_user_data
    existing_user = await get_user_data(marzban_username)

    # This block handles payments for users that already exist (e.g., manual invoices)
    # It will now be skipped if the user does not exist.
    if existing_user and "error" not in existing_user:
        LOGGER.info(f"User '{marzban_username}' already exists. Confirming payment for invoice #{invoice_id}.")
        await update_invoice_status(invoice_id, 'approved')
        
        try:
            await context.bot.send_message(
                chat_id=customer_id,
                text=f"✅ پرداخت شما برای فاکتور شماره `{invoice_id}` با موفقیت تایید شد. سرویس شما (`{marzban_username}`) فعال است."
            )
        except Exception as e:
            LOGGER.error(f"Failed to send manual payment confirmation to customer {customer_id}: {e}")

        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n**✅ پرداخت برای کاربر موجود (`{marzban_username}`) تایید شد.**\n"
                                            f"(توسط: {admin_user.full_name})",
            parse_mode=ParseMode.MARKDOWN
        )
        return # End execution here as no new user needs to be created

    # This block handles creation of a new user
    LOGGER.info(f"User '{marzban_username}' not found. Creating new user for invoice #{invoice_id}.")
    
    # ✨✨✨ KEY FIX HERE ✨✨✨
    # Correctly define all variables from plan_details at the beginning of the block
    plan_type = plan_details.get("plan_type")
    duration_days = plan_details.get('duration')
    price = plan_details.get('price')
    max_ips = plan_details.get('max_ips') 

    if plan_type == "unlimited":
        data_limit_gb = 0
    else:
        data_limit_gb = plan_details.get('volume')

    if not all([data_limit_gb is not None, duration_days is not None, price is not None]):
        LOGGER.error(f"Invoice #{invoice_id} has incomplete plan_details for user creation: {plan_details}")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا:** اطلاعات پلن در فاکتور برای ساخت کاربر ناقص است.")
        return

    try:
        new_user_data = await create_marzban_user_from_template(
            data_limit_gb=data_limit_gb, 
            expire_days=duration_days,
            username=marzban_username,
            max_ips=max_ips
        )
        if not new_user_data or 'username' not in new_user_data:
            raise Exception("Failed to create user in Marzban, received empty response.")
    except Exception as e:
        LOGGER.error(f"Failed to create Marzban user for invoice #{invoice_id}: {e}", exc_info=True)
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا در ساخت کاربر در مرزبان.**")
        return
    
    # Now the condition will work correctly
    if price > 0 and duration_days > 0:
        from database.db_manager import save_subscription_note
        try:
            await save_subscription_note(
                username=marzban_username,
                duration=duration_days,
                price=price,
                data_limit_gb=data_limit_gb
            )
            LOGGER.info(f"Successfully saved subscription note for new user '{marzban_username}'.")
        except Exception as e:
            LOGGER.error(f"CRITICAL: Failed to save subscription note for '{marzban_username}' after creation: {e}", exc_info=True)
    
    # ... The rest of the function remains the same ...
    await link_user_to_telegram(marzban_username, customer_id)
    await update_invoice_status(invoice_id, 'approved')
    
    try:

        subscription_url = new_user_data.get('subscription_url')
        if subscription_url:
            qr_image = qrcode.make(subscription_url)
            bio = io.BytesIO()
            bio.name = 'qrcode.png'
            qr_image.save(bio, 'PNG')
            bio.seek(0)

            volume_text = "نامحدود" if plan_type == "unlimited" else f"{data_limit_gb} گیگابایت"
            user_limit_text = f"\n👥 **تعداد کاربر:** {max_ips} دستگاه همزمان" if max_ips else ""

            caption = (
                "🎉 **اشتراک شما با موفقیت فعال شد!**\n\n"
                f"👤 **نام کاربری:** `{marzban_username}`\n"
                f"📦 **حجم:** {volume_text}\n"
                f"🗓️ **مدت:** {duration_days} روز{user_limit_text}\n\n"
                "👇 **برای اتصال از روش‌های زیر استفاده کنید:**\n\n"
                "1️⃣ **اسکن QR کد:**\n"
                "کد QR بالا را با برنامه خود اسکن کنید.\n\n"
                "2️⃣ **کپی لینک** (روی لینک زیر کلیک کنید تا کپی شود):\n"
                f"`{subscription_url}`"
            )
            
            await context.bot.send_photo(
                chat_id=customer_id,
                photo=bio,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            fallback_message = (
                "✅ پرداخت شما تایید شد و سرویس جدیدتان با موفقیت ساخته شد!\n\n"
                f"👤 **نام کاربری:** `{marzban_username}`\n"
                "⚠️ متاسفانه لینک اتصال خودکار ساخته نشد. لطفاً از ادمین درخواست کنید."
            )
            await context.bot.send_message(
                chat_id=customer_id, text=fallback_message, parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        LOGGER.error(f"Failed to send success message/photo to customer {customer_id} for invoice #{invoice_id}: {e}", exc_info=True)
    
    final_caption = query.message.caption + (
        f"\n\n**✅ پرداخت تایید و سرویس `{marzban_username}` با موفقیت ساخته شد.**\n"
        f"(توسط: {admin_user.full_name})"
    )
    await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.MARKDOWN)
    
    # Using `send_message` instead of `send_main_menu` for admin confirmation
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="سرویس جدید با موفقیت برای کاربر فعال شد.",
        reply_markup=get_admin_main_menu_keyboard()
    )

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass

async def send_custom_plan_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_details: dict, invoice_id: int):
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    
    volume = plan_details.get('volume')
    duration = plan_details.get('duration')
    price = plan_details.get('price')
    
    if not all([volume, duration, price]):
        LOGGER.error(f"Incomplete plan details for user {user_id}: {plan_details}")
        await context.bot.send_message(chat_id=user_id, text="❌ خطایی در پردازش اطلاعات پلن شما رخ داد.")
        return

    financials = await load_financials()
    card_holder = financials.get("card_holder", "تنظیم نشده")
    card_number = financials.get("card_number", "تنظیم نشده")
    
    if "تنظیم نشده" in [card_holder, card_number]:
        LOGGER.error(f"Financial settings are not configured. Cannot send invoice to {user_id}.")
        await context.bot.send_message(chat_id=user_id, text="❌ متاسفانه در حال حاضر امکان صدور فاکتور وجود ندارد.")
        return

    formatted_price = f"{price:,.0f}"
    invoice_text = (
        f"🧾 *صورتحساب پلن دلخواه شما*\n"
        f"*شماره فاکتور: `{invoice_id}`*\n\n"
        f"▫️ **حجم سرویس:** {volume} گیگابایت\n"
        f"▫️ **مدت زمان:** {duration} روز\n"
        f"-------------------------------------\n"
        f"💳 **مبلغ قابل پرداخت:** `{formatted_price}` تومان\n\n"
        f"**اطلاعات پرداخت:**\n"
        f" \- شماره کارت: `{card_number}`\n"
        f" \- به نام: `{card_holder}`\n\n"
        "لطفاً پس از واریز، با استفاده از دکمه زیر، رسید خود را برای ما ارسال کنید."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="customer_send_receipt")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="payment_back_to_menu")]
    ])
    
    try:
        await context.bot.send_message(
            chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        LOGGER.info(f"Custom plan invoice #{invoice_id} sent to user {user_id}.")
    except Exception as e:
        LOGGER.error(f"Failed to send custom plan invoice #{invoice_id} to user {user_id}: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=user_id, text="❌ خطایی در ارسال صورتحساب رخ داد.")
        except Exception:
            pass

async def confirm_manual_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer("⏳ در حال تایید پرداخت...")

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        LOGGER.error(f"Invalid invoice_id in callback data for manual confirmation: {query.data}")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا:** شماره فاکتور نامعتبر است.")
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=query.message.caption + "\n\n⚠️ **این فاکتور قبلاً پردازش شده یا یافت نشد.**")
        return

    success = await update_invoice_status(invoice_id, 'approved')
    if not success:
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا در به‌روزرسانی وضعیت فاکتور در دیتابیس.**")
        return
        
    LOGGER.info(f"Admin {admin_user.id} confirmed payment for manual invoice #{invoice_id}.")
    
    customer_id = invoice['user_id']
    try:
        await context.bot.send_message(
            chat_id=customer_id,
            text=f"✅ پرداخت شما برای فاکتور شماره `{invoice_id}` با موفقیت تایید شد."
        )
    except Exception as e:
        LOGGER.error(f"Failed to send manual payment confirmation to customer {customer_id}: {e}")

    await query.edit_message_caption(
        caption=query.message.caption + f"\n\n**✅ پرداخت با موفقیت تایید شد.**\n"
                                        f"(توسط: {admin_user.full_name})",
        parse_mode=ParseMode.MARKDOWN
    )

# =============================================================================
#  NEW: Handler for Approving Additional Data Purchase
# =============================================================================

async def approve_data_top_up(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the admin's approval for an additional data purchase.
    Adds data to the user's account via Marzban API.
    """
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer("⏳ در حال افزودن حجم...")

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        LOGGER.error(f"Invalid invoice_id in callback data for data top-up: {query.data}")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا:** شماره فاکتور نامعتبر است.")
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_caption(caption=query.message.caption + "\n\n⚠️ **این فاکتور قبلاً پردازش شده یا یافت نشد.**")
        return

    plan_details = invoice.get('plan_details', {})
    marzban_username = plan_details.get('username')
    data_gb_to_add = plan_details.get('volume')
    customer_id = invoice.get('user_id')

    if not all([marzban_username, data_gb_to_add, customer_id]):
        LOGGER.error(f"Invoice #{invoice_id} has incomplete details for data top-up: {plan_details}")
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ **خطا:** اطلاعات فاکتور ناقص است.")
        return

    # Call the API to add data to the user
    success, message = await add_data_to_user_api(marzban_username, data_gb_to_add)

    if success:
        await update_invoice_status(invoice_id, 'approved')
        LOGGER.info(f"Admin {admin_user.id} approved data top-up for '{marzban_username}' (Invoice #{invoice_id}). API Message: {message}")
        
        # Notify the customer
        try:
            await context.bot.send_message(
                chat_id=customer_id,
                text=f"✅ پرداخت شما برای فاکتور `{invoice_id}` تایید شد.\n\n"
                     f"**{data_gb_to_add} گیگابایت** حجم اضافه به سرویس شما افزوده شد."
            )
        except Exception as e:
            LOGGER.error(f"Failed to send data top-up confirmation to customer {customer_id}: {e}")

        # Update the admin's message
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n**✅ حجم با موفقیت به `{marzban_username}` اضافه شد.**\n"
                                            f"(توسط: {admin_user.full_name})",
            parse_mode=ParseMode.MARKDOWN
        )

    else:
        # If API call fails
        LOGGER.error(f"Failed to add data for '{marzban_username}' via API. Reason: {message}")
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n❌ **خطا در ارتباط با پنل مرزبان:**\n`{message}`"
        )    