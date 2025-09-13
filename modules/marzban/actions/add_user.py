# FILE: modules/marzban/actions/add_user.py (REVISED)

import datetime
import qrcode
import io
import logging
import copy
import secrets
import string
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from .constants import (
    ADD_USER_USERNAME, ADD_USER_DATALIMIT, ADD_USER_EXPIRE, ADD_USER_CONFIRM,
    GB_IN_BYTES
)
from database.db_manager import (
    load_template_config_db, link_user_to_telegram, save_user_note,
    add_user_to_managed_list
)
from shared.keyboards import get_user_management_keyboard
# V V V V V THE FIX IS HERE (IMPORT) V V V V V
from modules.general.actions import end_conversation_and_show_menu
# ^ ^ ^ ^ ^ THE FIX IS HERE (IMPORT) ^ ^ ^ ^ ^
from .api import create_user_api, get_user_data
from .data_manager import normalize_username
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

# =============================================================================
#  1. تابع اصلی و قابل استفاده مجدد برای ساخت کاربر
# =============================================================================

def generate_random_username(length=8):
    """Generates a random username."""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

async def create_marzban_user_from_template(
    data_limit_gb: int,
    expire_days: int,
    username: Optional[str] = None,
    max_ips: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Creates a new Marzban user based on the saved template.
    This is the core, reusable function. It handles username collisions and max_ips.

    Args:
        data_limit_gb: Data limit in Gigabytes.
        expire_days: Subscription duration in days.
        username: (Optional) The desired username. If None, a random one is generated.
        max_ips: (Optional) The maximum number of simultaneous connections.
    
    Returns:
        A dictionary with the new user's data on success, None on failure.
    """
    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
        LOGGER.error("[Core Create User] Template user is not configured in the database.")
        return None

    # --- Initial Username Setup ---
    base_username = username
    if not base_username:
        base_username = generate_random_username()
        LOGGER.info(f"[Core Create User] No username provided, generated random: {base_username}")
    else:
        base_username = normalize_username(base_username)

    # --- Payload Preparation ---
    data_limit = data_limit_gb * GB_IN_BYTES if data_limit_gb > 0 else 0
    expire = int((datetime.datetime.now() + datetime.timedelta(days=expire_days)).timestamp()) if expire_days > 0 else 0
    
    proxies_from_template = copy.deepcopy(template_config.get('proxies', {}))
    if 'vless' in proxies_from_template and 'id' in proxies_from_template['vless']: del proxies_from_template['vless']['id']
    if 'vmess' in proxies_from_template and 'id' in proxies_from_template['vmess']: del proxies_from_template['vmess']['id']
    
    payload = {
        "inbounds": template_config.get('inbounds', {}),
        "expire": expire,
        "data_limit": data_limit,
        "proxies": proxies_from_template,
        "status": "active"
    }

    if max_ips is not None and max_ips > 0:
        payload["on_hold_max_ips"] = max_ips
        LOGGER.info(f"[Core Create User] Setting max_online_ips to {max_ips} for user {base_username}.")

    # --- Create User with Collision Handling ---
    current_username = base_username
    for attempt in range(4): # Try original name + 3 variations
        payload["username"] = current_username
        
        LOGGER.debug(f"[Core Create User - Attempt {attempt+1}] Trying to create user '{current_username}'...")
        LOGGER.debug(f"[Core Create User] Payload for Marzban API: {payload}")
        
        success, result = await create_user_api(payload)
        
        if success:
            LOGGER.info(f"[Core Create User] Successfully created user '{current_username}' via API.")
            return result
        
        if isinstance(result, str) and "already exists" in result:
            LOGGER.warning(f"[Core Create User] Username '{current_username}' already exists. Generating a new one.")
            suffix = ''.join(secrets.choice(string.digits) for _ in range(3))
            current_username = f"{base_username}_{suffix}"
            continue
        else:
            LOGGER.error(f"[Core Create User] Failed to create user '{current_username}'. API response: {result}")
            return None

    LOGGER.error(f"[Core Create User] Failed to create user after 4 attempts. Last tried username: '{current_username}'.")
    return None

# =============================================================================
#  2. مکالمه افزودن کاربر به صورت دستی توسط ادمین
# =============================================================================

async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop('customer_user_id', None)
    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
        await update.message.reply_text(
            "❌ **خطا: الگوی کاربری تنظیم نشده است.**\n"
            "لطفاً ابتدا یک کاربر را از طریق «⚙️ تنظیم کاربر الگو» انتخاب کنید.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=get_user_management_keyboard()
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "**۱/۳:** لطفاً **نام کاربری** جدید را وارد کنید.\n(برای لغو /cancel)",
        reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_user'] = {}
    return ADD_USER_USERNAME

async def add_user_for_customer_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    customer_user_id = int(query.data.split('_')[-1])
    context.user_data['customer_user_id'] = customer_user_id
    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
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

    existing_user = await get_user_data(username)
    if existing_user and "error" not in existing_user:
        await update.message.reply_text(f"❌ **خطا: کاربری با نام `{username}` از قبل وجود دارد.**", parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_USERNAME
    
    context.user_data['new_user']['username'] = username
    await update.message.reply_text(
        f"✅ نام کاربری `{username}` قابل استفاده است.\n\n"
        f"**۲/۳:** لطفاً **حجم (GB)** را وارد کنید (برای نامحدود: `0`).",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADD_USER_DATALIMIT

async def add_user_get_datalimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        data_gb = int(update.message.text)
        if data_gb < 0: raise ValueError
        context.user_data['new_user']['data_limit_gb'] = data_gb
        await update.message.reply_text(
            f"✅ حجم: `{data_gb if data_gb > 0 else 'نامحدود'}` GB\n\n**۳/۳:** لطفاً **مدت زمان** را به **روز** وارد کنید (برای نامحدود: `0`).",
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
    query = update.callback_query
    await query.answer()
    
    admin_user = update.effective_user
    await query.edit_message_text(f"در حال ساخت کاربر...", parse_mode=ParseMode.MARKDOWN)

    user_info = context.user_data.get('new_user')
    if not user_info:
        await query.edit_message_text("خطا: اطلاعات کاربر در حافظه موقت یافت نشد.")
        return ConversationHandler.END

    new_user_data = await create_marzban_user_from_template(
        data_limit_gb=user_info['data_limit_gb'],
        expire_days=user_info['expire_days'],
        username=user_info['username']
    )
    
    if new_user_data:
        marzban_username = new_user_data['username'] # Use the username returned by API
        normalized_username = normalize_username(marzban_username)

        await add_user_to_managed_list(normalized_username)
        
        note_data = {
            'subscription_duration': user_info['expire_days'], 
            'subscription_data_limit_gb': user_info['data_limit_gb'],
            'subscription_price': 0
        }
        await save_user_note(normalized_username, note_data)
        
        admin_mention = escape_markdown(admin_user.full_name, version=2)
        safe_username = escape_markdown(marzban_username, version=2)
        log_message = (
            f"➕ *اشتراک جدید ایجاد شد*\n\n"
            f"▫️ **نام کاربری:** `{safe_username}`\n"
            f"▫️ **حجم:** {user_info['data_limit_gb']} GB\n"
            f"▫️ **مدت:** {user_info['expire_days']} روز\n"
            f"👤 **توسط ادمین:** {admin_mention}"
        )
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)

        customer_id = context.user_data.get('customer_user_id')
        if customer_id:
            await link_user_to_telegram(normalized_username, customer_id)
            subscription_url = new_user_data.get('subscription_url', '')
            if subscription_url:
                data_limit_str = f"{user_info['data_limit_gb']} GB" if user_info['data_limit_gb'] > 0 else "نامحدود"
                expire_days_str = f"{user_info['expire_days']} روز" if user_info['expire_days'] > 0 else "نامحدود"
                
                customer_message = (
                    f"🎉 **اشتراک شما با موفقیت ساخته شد!** 🎉\n\n"
                    f"مشخصات سرویس شما:\n"
                    f"▫️ **نام کاربری:** `{marzban_username}`\n"
                    f"▫️ **حجم:** {data_limit_str}\n"
                    f"▫️ **مدت اعتبار:** {expire_days_str}\n\n"
                    f"🔗 **لینک اشتراک:**\n`{subscription_url}`\n\n"
                    f"💡 لطفاً لینک اشتراک بالا را کپی کرده و طبق راهنمای اتصال، در برنامه خود وارد کنید."
                )
                
                qr_image = qrcode.make(subscription_url)
                bio = io.BytesIO()
                bio.name = 'qrcode.png'
                qr_image.save(bio, 'PNG')
                bio.seek(0)
                try:
                    await context.bot.send_photo(chat_id=customer_id, photo=bio, caption=customer_message, parse_mode=ParseMode.MARKDOWN)
                    callback_string = f"fin_send_req:{customer_id}:{marzban_username}"
                    admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💰 ارسال صورتحساب", callback_data=callback_string)]])
                    await context.bot.send_message(chat_id=update.effective_user.id, text=f"پیام حاوی کانفیگ برای مشتری {customer_id} ارسال شد.", reply_markup=admin_keyboard)
                except Exception as e:
                    LOGGER.warning(f"Failed to send message to customer {customer_id}: {e}")
                    await context.bot.send_message(chat_id=update.effective_user.id, text=f"⚠️ کاربر ساخته شد, اما ارسال پیام به مشتری خطا داد.\n`{subscription_url}`")
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("مشاهده جزئیات کاربر", callback_data=f"user_details_{marzban_username}_all_1")
        ]])
        await query.edit_message_text(f"✅ کاربر `{marzban_username}` با موفقیت ساخته شد.", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    else:
        error_message = f"❌ **خطا در ساخت کاربر:**\n\n`{new_user_data}`"
        await query.edit_message_text(error_message, parse_mode=ParseMode.MARKDOWN)
    
        context.user_data.clear()
    return ConversationHandler.END


async def cancel_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the user creation conversation and returns to the main menu."""
    query = update.callback_query
    if query:
        await query.answer()
        # We don't need to edit the message text here as `end_conversation_and_show_menu` handles it.
    
    # Directly call the standard fallback function
    return await end_conversation_and_show_menu(update, context)