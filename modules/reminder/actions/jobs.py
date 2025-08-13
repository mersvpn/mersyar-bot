# ===== IMPORTS & DEPENDENCIES =====
import datetime
import logging
import jdatetime
from telegram.ext import ContextTypes, Application
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

# --- Local Imports ---
from modules.marzban.actions.data_manager import (
    load_settings,
    load_reminders,
    load_users_map,
    load_non_renewal_users,
    normalize_username
)
from modules.marzban.actions.api import get_all_users
from modules.marzban.actions.constants import GB_IN_BYTES

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

async def schedule_initial_daily_job(application: Application):
    """Schedules the daily reminder job when the bot starts up."""
    try:
        settings_data = await load_settings()
        admin_id = application.bot_data.get('admin_id_for_jobs')
        if not admin_id:
            return
        reminder_time_str = settings_data.get('reminder_time', "09:00")
        time_obj = datetime.datetime.strptime(reminder_time_str, '%H:%M').time()
        await schedule_daily_job(application, time_obj)
    except (ValueError, TypeError) as e:
        LOGGER.error(f"❌ Invalid time format in settings.json. Job not scheduled. Error: {e}", exc_info=True)
    except Exception as e:
        LOGGER.error(f"❌ Unexpected error during initial job scheduling. Error: {e}", exc_info=True)

async def schedule_daily_job(application: Application, time_obj: datetime.time):
    """Schedules or reschedules the daily reminder job."""
    admin_id = application.bot_data.get('admin_id_for_jobs')
    if not admin_id:
        LOGGER.warning("Cannot schedule job: admin_id_for_jobs not found.")
        return
    job_queue = application.job_queue
    if not job_queue:
        LOGGER.warning("Cannot schedule job: JobQueue not available.")
        return
    job_name = f"daily_reminder_check_for_{admin_id}"
    for job in job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
        LOGGER.info(f"Removed existing reminder job: {job.name}")
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    run_time_tehran = datetime.time(hour=time_obj.hour, minute=time_obj.minute, tzinfo=tehran_tz)
    job_queue.run_daily(
        callback=check_users_for_reminders,
        time=run_time_tehran,
        chat_id=admin_id,
        name=job_name
    )
    LOGGER.info(f"✅ Daily reminder job scheduled for {run_time_tehran} Tehran Time.")

async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    The main daily job that checks all users and sends reminders if needed.
    Includes the daily admin note at the top of the report.
    """
    application = context.application
    admin_id = context.job.chat_id
    bot_username = application.bot.username
    LOGGER.info(f"Running daily reminder job for admin {admin_id}...")
    try:
        settings = await load_settings()
        manual_reminders = await load_reminders()
        users_map = await load_users_map()
        non_renewal_list = await load_non_renewal_users()
        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        daily_note = settings.get("daily_admin_note", "")
        all_users = await get_all_users()
        if all_users is None:
            LOGGER.error("Reminder Job: Could not get user list from Marzban. Skipping job run.")
            await context.bot.send_message(admin_id, "❌ **خطای جاب یادآور**: عدم امکان دریافت لیست کاربران از پنل مرزبان.")
            return
        admin_expiring_soon, admin_low_data = [], []
        for user in all_users:
            username = user.get('username')
            if not username: continue
            normalized_user = normalize_username(username)
            if user.get('status') != 'active' or normalized_user in non_renewal_list: continue
            is_expiring, is_low_data = False, False
            if user.get('expire'):
                expire_date = datetime.datetime.fromtimestamp(user['expire'])
                if datetime.datetime.now() < expire_date < (datetime.datetime.now() + datetime.timedelta(days=days_threshold)):
                    is_expiring = True
            data_limit = user.get('data_limit') or 0
            if data_limit > 0:
                used_traffic = user.get('used_traffic') or 0
                if (data_limit - used_traffic) < (data_gb_threshold * GB_IN_BYTES):
                    is_low_data = True
            customer_telegram_id = users_map.get(normalized_user)
            if (is_expiring or is_low_data) and customer_telegram_id:
                try:
                    customer_message = f"🔔 **یادآور تمدید اشتراک: `{normalized_user}`**\n\n"
                    if is_expiring:
                        time_left = datetime.datetime.fromtimestamp(user['expire']) - datetime.datetime.now()
                        customer_message += f"⏳ اشتراک شما کمتر از `{time_left.days + 1}` روز دیگر منقضی می‌شود.\n"
                    if is_low_data:
                        remaining_gb = (data_limit - used_traffic) / GB_IN_BYTES
                        customer_message += f"📉 حجم باقیمانده شما کمتر از `{remaining_gb:.2f}` گیگابایت است.\n"
                    customer_message += "\nبرای جلوگیری از قطعی، لطفاً اشتراک خود را تمدید کنید."
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ درخواست تمدید", callback_data=f"customer_renew_request_{normalized_user}")],
                        [InlineKeyboardButton("❌ عدم تمدید (عدم دریافت یادآور)", callback_data=f"customer_do_not_renew_{normalized_user}")]
                    ])
                    await application.bot.send_message(
                        chat_id=customer_telegram_id, text=customer_message,
                        reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    LOGGER.warning(f"Failed to send reminder to customer {customer_telegram_id} for user {normalized_user}: {e}")
            if is_expiring: admin_expiring_soon.append(user)
            if is_low_data and not is_expiring: admin_low_data.append(user)
        if not admin_expiring_soon and not admin_low_data and not manual_reminders and not daily_note:
            LOGGER.info("Reminder Job: No users or notes needed admin attention today. Job finished successfully."); return
        jalali_today = jdatetime.datetime.now().strftime('%Y/%m/%d')
        message = f"🔔 **گزارش یادآور روزانه - {jalali_today}** 🔔\n\n"
        if daily_note:
            message += f"🗒️ **یادداشت روز:**\n`{daily_note}`\n\n"
            message += "—" * 15 + "\n\n"
        def format_user_line(u, reason):
            details_link = f"https://t.me/{bot_username}?start=details_{u['username']}"
            return f"▪️ <a href='{details_link}'>{u['username']}</a> - <i>{reason}</i>\n"
        if admin_expiring_soon:
            message += "⏳ **کاربران در آستانه انقضا:**\n"
            for user in admin_expiring_soon:
                time_left = datetime.datetime.fromtimestamp(user['expire']) - datetime.datetime.now()
                reason = f"{time_left.days+1} روز مانده"
                message += format_user_line(user, reason)
            message += "\n"
        if admin_low_data:
            message += "📉 **کاربران با حجم کم:**\n"
            for user in admin_low_data:
                remaining_gb = ((user.get('data_limit') or 0) - (user.get('used_traffic') or 0)) / GB_IN_BYTES
                reason = f"~{remaining_gb:.1f} GB مانده"
                message += format_user_line(user, reason)
            message += "\n"
        if manual_reminders:
            message += "📝 **پیگیری‌های دستی:**\n"
            for username, note in manual_reminders.items():
                escaped_note = escape_markdown(note, version=1).replace('\n', ' ')
                details_link = f"https://t.me/{bot_username}?start=details_{username}"
                message += f"▪️ <a href='{details_link}'>{username}</a> - <i>یادداشت: {escaped_note}</i>\n"
        await context.bot.send_message(
            chat_id=admin_id,
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        LOGGER.info("Admin reminder message sent. Job finished successfully.")
    except Exception as e:
        LOGGER.error(f"Critical error in daily reminder job: {e}", exc_info=True)
        try:
            await application.bot.send_message(admin_id, f"❌ **خطای بحرانی** ❌\n\nاجرای جاب یادآور خودکار با خطای جدی مواجه شد. لطفاً لاگ‌های ربات را بررسی کنید.\n\n**Error:** `{e}`")
        except Exception as notify_error:
            LOGGER.error(f"Failed to even notify admin about the job failure: {notify_error}", exc_info=True)
