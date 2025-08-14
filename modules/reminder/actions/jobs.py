import datetime
import logging
import jdatetime
from telegram.ext import ContextTypes, Application
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from modules.marzban.actions.data_manager import (
    load_settings, load_reminders, load_users_map,
    load_non_renewal_users, normalize_username
)
from modules.marzban.actions.api import get_all_users
from modules.marzban.actions.constants import GB_IN_BYTES

LOGGER = logging.getLogger(__name__)

async def schedule_initial_daily_job(application: Application):
    try:
        settings = await load_settings()
        admin_id = application.bot_data.get('admin_id_for_jobs')
        if not admin_id: return
        time_str = settings.get('reminder_time', "09:00")
        time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
        await schedule_daily_job(application, time_obj)
    except Exception as e:
        LOGGER.error(f"Error scheduling job: {e}", exc_info=True)

async def schedule_daily_job(application: Application, time_obj: datetime.time):
    admin_id = application.bot_data.get('admin_id_for_jobs')
    if not admin_id: return
    jq = application.job_queue
    if not jq: return
    job_name = f"daily_reminder_{admin_id}"
    for job in jq.get_jobs_by_name(job_name): job.schedule_removal()
    tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    jq.run_daily(check_users_for_reminders, datetime.time(time_obj.hour, time_obj.minute, tzinfo=tz), chat_id=admin_id, name=job_name)
    LOGGER.info(f"Daily job scheduled for {time_obj.strftime('%H:%M')} Tehran time.")

async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = context.job.chat_id
    bot_username = context.application.bot.username
    LOGGER.info(f"Running daily reminder job for admin {admin_id}...")
    try:
        settings = await load_settings()
        daily_notes = settings.get("daily_admin_notes_list", [])
        manual_reminders = await load_reminders()
        all_users = await get_all_users()
        if all_users is None:
            await context.bot.send_message(admin_id, "Reminder job failed: Could not fetch users.")
            return

        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        non_renewal_list = await load_non_renewal_users()
        
        expiring = []
        low_data = []

        for user in all_users:
            username, status = user.get('username'), user.get('status')
            if not username or status != 'active' or normalize_username(username) in non_renewal_list:
                continue

            expire_ts = user.get('expire')
            if expire_ts:
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                if datetime.datetime.now() < expire_date < (datetime.datetime.now() + datetime.timedelta(days=days_threshold)):
                    expiring.append(user)

            data_limit = user.get('data_limit', 0)
            if data_limit > 0 and (data_limit - user.get('used_traffic', 0)) < (data_gb_threshold * GB_IN_BYTES):
                if user not in expiring:
                    low_data.append(user)

        if not expiring and not low_data and not manual_reminders and not daily_notes:
            return

        jalali_today = jdatetime.datetime.now().strftime('%Y/%m/%d')
        message = f"🔔 **گزارش یادآور روزانه - {jalali_today}** 🔔\n\n"

        if daily_notes:
            message += "🗒️ **یادداشت‌های روز:**\n"
            for note in daily_notes:
                title = note.get('title', 'بدون عنوان')
                text = note.get('text', '')
                message += f"▪️ **{escape_markdown(title, version=2)}**\n`{escape_markdown(text, version=2)}`\n\n"
            message += "—" * 15 + "\n\n"

        def format_user_line(u, reason):
            return f"▪️ <a href='https://t.me/{bot_username}?start=details_{u['username']}'>{u['username']}</a> - <i>{reason}</i>\n"

        if expiring:
            message += "⏳ **کاربران در آستانه انقضا:**\n"
            for u in expiring:
                time_left = datetime.datetime.fromtimestamp(u['expire']) - datetime.datetime.now()
                message += format_user_line(u, f"{time_left.days + 1} روز مانده")
            message += "\n"

        if low_data:
            message += "📉 **کاربران با حجم کم:**\n"
            for u in low_data:
                rem_gb = (u.get('data_limit', 0) - u.get('used_traffic', 0)) / GB_IN_BYTES
                message += format_user_line(u, f"~{rem_gb:.1f} GB مانده")
            message += "\n"

        if manual_reminders:
            message += "📝 **پیگیری‌های دستی:**\n"
            for u, n in manual_reminders.items():
                escaped = escape_markdown(n, version=1).replace('\n', ' ')
                message += f"▪️ <a href='https://t.me/{bot_username}?start=details_{u}'>{u}</a> - <i>{escaped}</i>\n"
        
        parse_mode_to_use = ParseMode.HTML if manual_reminders or expiring or low_data else ParseMode.MARKDOWN_V2
        await context.bot.send_message(
            admin_id, message,
            parse_mode=parse_mode_to_use,
            disable_web_page_preview=True
        )
    except Exception as e:
        LOGGER.error(f"Critical error in daily reminder job: {e}", exc_info=True)