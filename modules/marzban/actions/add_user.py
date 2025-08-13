# ===== IMPORTS & DEPENDENCIES =====
import datetime
import qrcode
import io
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# --- Local Imports ---
from .constants import (
    ADD_USER_USERNAME, ADD_USER_DATALIMIT, ADD_USER_EXPIRE, ADD_USER_CONFIRM,
    GB_IN_BYTES
)
from .data_manager import (
    load_template_config, load_users_map, save_users_map, normalize_username
)
# CORRECTED: Import keyboards and callbacks from the new shared location
from shared.keyboards import get_user_management_keyboard
from shared.callbacks import cancel_conversation
from .api import create_user_api, get_user_data
from modules.auth import admin_only_conv

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== ADD USER CONVERSATION FUNCTIONS =====

@admin_only_conv
async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop('customer_user_id', None)
    template_config = await load_template_config()
    LOGGER.info(f"[Add User] Admin {update.effective_user.id} starting manual user creation.")

    if not template_config.get("template_username"):
        LOGGER.warning("[Add User] Template check failed: 'template_username' not found.")
        await update.message.reply_text(
            "❌ **خطا: الگوی کاربری تنظیم نشده است.**\n"
            "لطفاً ابتدا یک کاربر را از طریق دکمه «⚙️ تنظیم کاربر الگو» به عنوان الگو انتخاب کنید.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_user_management_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "**۱/۳:** لطفاً **نام کاربری** جدید را وارد کنید.\n(برای لغو /cancel)",
        reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_user'] = {}
    return ADD_USER_USERNAME

@admin_only_conv
async def add_user_for_customer_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    customer_user_id = int(query.data.split('_')[-1])
    context.user_data['customer_user_id'] = customer_user_id

    template_config = await load_template_config()
    LOGGER.info(f"[Add User] Starting creation for customer {customer_user_id}.")

    if not template_config.get("template_username"):
        LOGGER.warning("[Add User] Template check failed for customer request.")
        await query.message.reply_text("❌ **خطا: الگوی کاربری تنظیم نشده است.**", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    await query.edit_message_text(f"✅ درخواست تایید شد. در حال ساخت کانفیگ برای کاربر `{customer_user_id}`.", parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="**۱/۳:** لطفاً **نام کاربری** جدید را برای این مشتری وارد کنید:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_user'] = {}
    return ADD_USER_USERNAME

async def add_user_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = normalize_username(update.message.text)
    if not username or ' ' in username:
        await update.message.reply_text("❌ نام کاربری نامعتبر است. لطفاً یک نام کاربری بدون فاصله وارد کنید.")
        return ADD_USER_USERNAME

    await update.message.reply_text(f"در حال بررسی نام کاربری «{username}»...")
    existing_user = await get_user_data(username)
    if existing_user:
        error_message = f"❌ **خطا: کاربری با نام `{username}` از قبل وجود دارد.**\n\nلطفاً یک نام کاربری دیگر وارد کنید."
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_USERNAME

    context.user_data['new_user']['username'] = username
    await update.message.reply_text(f"✅ نام کاربری `{username}` تایید شد.\n\n**۲/۳:** لطفاً **حجم (GB)** را وارد کنید (برای نامحدود عدد `0` را وارد کنید).", parse_mode=ParseMode.MARKDOWN)
    return ADD_USER_DATALIMIT

async def add_user_get_datalimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        data_gb = int(update.message.text)
        if data_gb < 0: raise ValueError
        context.user_data['new_user']['data_limit_gb'] = data_gb
        await update.message.reply_text(
            f"✅ حجم: `{data_gb if data_gb > 0 else 'نامحدود'}` GB\n\n**۳/۳:** لطفاً **مدت زمان اشتراک** را به **روز** وارد کنید (برای نامحدود عدد `0` را وارد کنید).",
            parse_mode=ParseMode.MARKDOWN
        )
        return ADD_USER_EXPIRE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فقط عدد صحیح و مثبت (یا صفر) وارد کنید.")
        return ADD_USER_DATALIMIT

async def add_user_get_expire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        expire_days = int(update.message.text)
        if expire_days < 0: raise ValueError
        context.user_data['new_user']['expire_days'] = expire_days

        user_info = context.user_data['new_user']
        username, data_gb = user_info['username'], user_info['data_limit_gb']

        summary = (
            f"**تایید اطلاعات کاربر جدید:**\n\n"
            f"▫️ **نام کاربری:** `{username}`\n"
            f"▫️ **حجم:** `{data_gb if data_gb > 0 else 'نامحدود'}` GB\n"
            f"▫️ **مدت زمان:** `{expire_days if expire_days > 0 else 'نامحدود'}` روز"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید و ساخت", callback_data="confirm_add_user")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_add_user")]
        ])
        await update.message.reply_text(summary, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_CONFIRM
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فقط عدد صحیح و مثبت (یا صفر) وارد کنید.")
        return ADD_USER_EXPIRE

async def add_user_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Final step: Creates the user via API, saves link, and notifies customer.
    CORRECTED: Removes the UUID from the template proxies before creating
    a new user to force Marzban to generate a new, unique UUID.
    """
    query = update.callback_query
    await query.answer()

    template_config = await load_template_config()
    if not template_config.get("template_username"):
        await query.edit_message_text("❌ **خطا: الگوی کاربری تنظیم نشده است.**", parse_mode=ParseMode.MARKDOWN)
        return await cancel_conversation(update, context)

    user_info = context.user_data.get('new_user')
    if not user_info:
        await query.edit_message_text("خطا: اطلاعات کاربر در حافظه موقت یافت نشد.")
        return await cancel_conversation(update, context)

    await query.edit_message_text(f"در حال ساخت کاربر `{user_info['username']}` در پنل مرزبان...")

    data_limit = user_info['data_limit_gb'] * GB_IN_BYTES if user_info['data_limit_gb'] > 0 else 0
    expire = int((datetime.datetime.now() + datetime.timedelta(days=user_info['expire_days'])).timestamp()) if user_info['expire_days'] > 0 else 0
    
    # --- CRUCIAL FIX: Clean the template proxies ---
    proxies_from_template = template_config.get('proxies', {})
    
    # Remove the 'id' (UUID) from the vless proxy settings if it exists
    if 'vless' in proxies_from_template and 'id' in proxies_from_template['vless']:
        del proxies_from_template['vless']['id']
    
    # You can add similar logic for other proxy types like 'vmess' if you use them
    # if 'vmess' in proxies_from_template and 'id' in proxies_from_template['vmess']:
    #     del proxies_from_template['vmess']['id']

    payload = {
        "username": user_info['username'],
        "inbounds": template_config.get('inbounds', {}),
        "expire": expire,
        "data_limit": data_limit,
        "proxies": proxies_from_template, # Use the cleaned proxies
        "data_limit_reset_strategy": "no_reset",
        "status": "active"
    }
    
    LOGGER.info(f"PAYLOAD for creating user '{user_info['username']}': {payload}")
    
    success, result = await create_user_api(payload)
    
    # ... (The rest of the function for sending messages remains exactly the same) ...
    customer_id = context.user_data.get('customer_user_id')
    admin_id = update.effective_user.id
    if success:
        new_user_data = result
        marzban_username = user_info['username']
        final_customer_id = customer_id if customer_id else admin_id
        admin_confirmation_text = f"✅ کاربر `{marzban_username}` با موفقیت در پنل ساخته شد."
        admin_keyboard = None
        if customer_id:
            callback_string = f"fin_send_req:{final_customer_id}:{marzban_username}"
            admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💰 ارسال اطلاعات پرداخت به مشتری", callback_data=callback_string)]])
            admin_confirmation_text += "\n\nمی‌توانید اطلاعات پرداخت را برای مشتری ارسال کنید."
        await query.edit_message_text(admin_confirmation_text, reply_markup=admin_keyboard, parse_mode=ParseMode.MARKDOWN)
        users_map = await load_users_map()
        users_map[marzban_username] = final_customer_id
        await save_users_map(users_map)
        if customer_id:
            subscription_url = new_user_data.get('subscription_url', '')
            if subscription_url:
                customer_message = (f"🎉 اشتراک شما با موفقیت ساخته شد! 🎉\n\n"
                                    f"می‌توانید با کپی کردن لینک زیر یا اسکن QR Code، کانفیگ را به کلاینت خود اضافه کنید:\n\n"
                                    f"`{subscription_url}`")
                qr_image = qrcode.make(subscription_url)
                bio = io.BytesIO()
                bio.name = 'qrcode.png'
                qr_image.save(bio, 'PNG')
                bio.seek(0)
                try:
                    await context.bot.send_photo(chat_id=customer_id, photo=bio, caption=customer_message, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    LOGGER.warning(f"User created, but failed to send message to customer {customer_id}: {e}", exc_info=True)
                    await query.message.reply_text(f"⚠️ کاربر ساخته شد، اما ارسال پیام به مشتری با خطا مواجه شد.\n`{subscription_url}`")
            else:
                LOGGER.warning(f"User {marzban_username} created but no subscription_url was returned.")
                await query.message.reply_text("⚠️ کاربر ساخته شد اما لینک اشتراکی از پنل دریافت نشد.")
    else:
        error_message = f"❌ **خطا در ساخت کاربر:**\n\n`{result}`"
        await query.edit_message_text(error_message, parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(
        chat_id=admin_id,
        text="به منوی مدیریت کاربران بازگشتید:",
        reply_markup=get_user_management_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("عملیات ساخت کاربر لغو شد.")
    return await cancel_conversation(update, context)