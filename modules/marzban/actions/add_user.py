# FILE: modules/marzban/actions/add_user.py (FIXED WITH LAZY IMPORTS)

import datetime
import qrcode
import io
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from shared.log_channel import send_log
from telegram.helpers import escape_markdown

from .constants import (
    ADD_USER_USERNAME, ADD_USER_DATALIMIT, ADD_USER_EXPIRE, ADD_USER_CONFIRM,
    GB_IN_BYTES
)
# --- START OF FIX: The global import from db_manager is removed ---
# from database.db_manager import (
#     load_template_config_db, link_user_to_telegram, save_user_note
# )
# --- END OF FIX ---

from shared.keyboards import get_user_management_keyboard
from shared.callbacks import cancel_conversation
from .api import create_user_api, get_user_data
from .data_manager import normalize_username

LOGGER = logging.getLogger(__name__)

async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- LAZY IMPORT ---
    from database.db_manager import load_template_config_db
    # --- END LAZY IMPORT ---
    
    context.user_data.pop('customer_user_id', None)
    
    template_config = await load_template_config_db()
    LOGGER.info(f"[Add User] Admin {update.effective_user.id} starting manual user creation.")

    if not template_config.get("template_username"):
        LOGGER.warning("[Add User] Template check failed: 'template_username' not found in DB.")
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

async def add_user_for_customer_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- LAZY IMPORT ---
    from database.db_manager import load_template_config_db
    # --- END LAZY IMPORT ---

    query = update.callback_query
    await query.answer()
    customer_user_id = int(query.data.split('_')[-1])
    context.user_data['customer_user_id'] = customer_user_id

    template_config = await load_template_config_db()
    LOGGER.info(f"[Add User] Starting creation for customer {customer_user_id}.")

    if not template_config.get("template_username"):
        LOGGER.warning("[Add User] Template check failed for customer request in DB.")
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
    
    if existing_user and "error" not in existing_user:
        error_message = f"❌ **خطا: کاربری با نام `{username}` از قبل وجود دارد.**\n\nلطفاً یک نام کاربری دیگر وارد کنید."
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_USERNAME
    
    context.user_data['new_user']['username'] = username
    await update.message.reply_text(
        f"✅ نام کاربری `{username}` قابل استفاده است.\n\n"
        f"**۲/۳:** لطفاً **حجم (GB)** را وارد کنید (برای نامحدود عدد `0` را وارد کنید).",
        parse_mode=ParseMode.MARKDOWN
    )
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

# ==================== REPLACE THIS FUNCTION in modules/marzban/actions/add_user.py ====================
async def add_user_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import copy
    from database.db_manager import (
        load_template_config_db, link_user_to_telegram, save_user_note,
        add_user_to_managed_list  # <-- وارد کردن تابع جدید
    )

    query = update.callback_query
    await query.answer()
    
    admin_user = update.effective_user

    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
        await query.edit_message_text("❌ **خطا: الگوی کاربری تنظیم نشده است.**", parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END

    user_info = context.user_data.get('new_user')
    if not user_info:
        await query.edit_message_text("خطا: اطلاعات کاربر در حافظه موقت یافت نشد.")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(f"در حال ساخت کاربر `{user_info['username']}` در پنل مرزبان...", parse_mode=ParseMode.MARKDOWN)

    data_limit_gb = user_info['data_limit_gb']
    data_limit = data_limit_gb * GB_IN_BYTES if data_limit_gb > 0 else 0
    expire_days = user_info['expire_days']
    expire = int((datetime.datetime.now() + datetime.timedelta(days=expire_days)).timestamp()) if expire_days > 0 else 0
    
    proxies_from_template = copy.deepcopy(template_config.get('proxies', {}))
    if 'vless' in proxies_from_template and 'id' in proxies_from_template['vless']: del proxies_from_template['vless']['id']
    if 'vmess' in proxies_from_template and 'id' in proxies_from_template['vmess']: del proxies_from_template['vmess']['id']
    
    payload = { "username": user_info['username'], "inbounds": template_config.get('inbounds', {}), "expire": expire, "data_limit": data_limit, "proxies": proxies_from_template, "status": "active" }
    
    success, result = await create_user_api(payload)
    
    if success:
        new_user_data = result
        marzban_username = user_info['username']
        normalized_username = normalize_username(marzban_username)

        # --- ثبت مالکیت کاربر ---
        await add_user_to_managed_list(normalized_username)
        # --- پایان ثبت مالکیت ---
        
        note_data = {
            'subscription_duration': expire_days, 
            'subscription_data_limit_gb': data_limit_gb,
            'subscription_price': 0
        }
        await save_user_note(normalized_username, note_data)
        
        admin_mention = escape_markdown(admin_user.full_name, version=2)
        safe_username = escape_markdown(marzban_username, version=2)
        log_message = (
            f"➕ *اشتراک جدید ایجاد شد*\n\n"
            f"▫️ **نام کاربری:** `{safe_username}`\n"
            f"▫️ **حجم:** {data_limit_gb} GB\n"
            f"▫️ **مدت:** {expire_days} روز\n"
            f"👤 **توسط ادمین:** {admin_mention}"
        )
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)

        customer_id = context.user_data.get('customer_user_id')
        if customer_id:
            await link_user_to_telegram(normalized_username, customer_id)
            subscription_url = new_user_data.get('subscription_url', '')
            if subscription_url:
                customer_message = (f"🎉 اشتراک شما با موفقیت ساخته شد!\n\n"
                                    f"لینک اشتراک:\n`{subscription_url}`")
                qr_image = qrcode.make(subscription_url)
                bio = io.BytesIO()
                bio.name = 'qrcode.png'
                qr_image.save(bio, 'PNG')
                bio.seek(0)
                try:
                    await context.bot.send_photo(chat_id=customer_id, photo=bio, caption=customer_message, parse_mode=ParseMode.MARKDOWN)
                    callback_string = f"fin_send_req:{customer_id}:{marzban_username}"
                    admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💰 ارسال اطلاعات پرداخت", callback_data=callback_string)]])
                    await context.bot.send_message(chat_id=update.effective_user.id, text=f"پیام حاوی کانفیگ برای مشتری {customer_id} ارسال شد.", reply_markup=admin_keyboard)
                except Exception as e:
                    LOGGER.warning(f"Failed to send message to customer {customer_id}: {e}")
                    await context.bot.send_message(chat_id=update.effective_user.id, text=f"⚠️ کاربر ساخته شد, اما ارسال پیام به مشتری خطا داد.\n`{subscription_url}`")
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("مشاهده جزئیات کاربر", callback_data=f"user_details_{marzban_username}_all_1")
        ]])
        await query.edit_message_text(f"✅ کاربر `{marzban_username}` با موفقیت ساخته شد.", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    else:
        error_message = f"❌ **خطا در ساخت کاربر:**\n\n`{result}`"
        await query.edit_message_text(error_message, parse_mode=ParseMode.MARKDOWN)
    
    context.user_data.clear()
    return ConversationHandler.END
# ======================================================================================================

async def cancel_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("عملیات ساخت کاربر لغو شد.")
    return await cancel_conversation(update, context)