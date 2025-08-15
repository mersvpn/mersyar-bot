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
        if not admin_id:
            LOGGER.warning("Cannot schedule daily job: Admin ID not found in bot_data.")
            return
        time_str = settings.get('reminder_time', "09:00")
        time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
        await schedule_daily_job(application, time_obj)
    except Exception as e:
        LOGGER.error(f"Failed to schedule initial daily job: {e}", exc_info=True)

async def schedule_daily_job(application: Application, time_obj: datetime.time):
    admin_id = application.bot_data.get('admin_id_for_jobs')
    if not admin_id: return
    
    job_queue = application.job_queue
    if not job_queue:
        LOGGER.warning("JobQueue is not available. Cannot schedule job.")
        return
        
    job_name = f"daily_reminder_job_{admin_id}"
    for job in job_queue.get_jobs_by_name(job_name): job.schedule_removal()

    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    job_time = datetime.time(hour=time_obj.hour, minute=time_obj.minute, tzinfo=tehran_tz)
    
    job_queue.run_daily(
        callback=check_users_for_reminders,
        time=job_time,
        chat_id=admin_id,
        name=job_name
    )
    LOGGER.info(f"Daily reminder job successfully scheduled for {job_time.strftime('%H:%M')} Tehran time.")

async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = context.job.chat_id
    bot_username = context.application.bot.username
    LOGGER.info(f"Executing daily reminder job for admin {admin_id}...")

    try:
        settings = await load_settings()
        daily_notes = settings.get("daily_admin_notes_list", [])
        manual_reminders = await load_reminders()
        all_users = await get_all_users()

        if all_users is None:
            await context.bot.send_message(admin_id, "⚠️ **گزارش روزانه:**\n\nربات نتوانست لیست کاربران را از پنل مرزبان دریافت کند.")
            return

        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        non_renewal_list = await load_non_renewal_users()
        
        expiring_users = []
        low_data_users = []

        for user in all_users:
            username = user.get('username')
            status = user.get('status')
            normalized_name = normalize_username(username or '')

            if not username or status != 'active' or normalized_name in non_renewal_list:
                continue
                
            # --- This is the corrected and safe section ---
            expire_ts = user.get('expire')
            if expire_ts: # expire can be None
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                now = datetime.datetime.now()
                if now < expire_date < (now + datetime.timedelta(days=days_threshold)):
                    expiring_users.append(user)

            data_limit = user.get('data_limit') or 0 # Safely handle None, convert to 0
            if data_limit > 0:
                used_traffic = user.get('used_traffic') or 0 # Safely handle None
                remaining_traffic = data_limit - used_traffic
                if remaining_traffic < (data_gb_threshold * GB_IN_BYTES):
                    if user not in expiring_users:
                        low_data_users.append(user)
            # --- End of corrected section ---

        should_send_report = any([expiring_users, low_data_users, manual_reminders, daily_notes])
        if not should_send_report:
            LOGGER.info("No items to report today. Daily job finished.")
            return

        jalali_today = jdatetime.datetime.now().strftime('%Y/%m/%d')
        report_parts = [f"🔔 **گزارش یادآور روزانه - {jalali_today}**\n"]

        if daily_notes:
            report_parts.append("🗒️ **یادداشت‌های روز:**")
            for note in daily_notes:
                title = note.get('title', 'بدون عنوان')
                text = note.get('text', '')
                report_parts.append(f"▪️ **{escape_markdown(title, 2)}**\n`{escape_markdown(text, 2)}`")
            report_parts.append("\n" + "—" * 15 + "\n")

        def format_user_line(u, reason):
            return f"▪️ <a href='https://t.me/{bot_username}?start=details_{u['username']}'>{u['username']}</a> - <i>{reason}</i>"

        if expiring_users:
            report_parts.append("⏳ **کاربران در آستانه انقضا:**")
            for u in expiring_users:
                time_left = datetime.datetime.fromtimestamp(u['expire']) - datetime.datetime.now()
                report_parts.append(format_user_line(u, f"{time_left.days + 1} روز مانده"))
        
        if low_data_users:
            report_parts.append("\n📉 **کاربران با حجم کم:**")
            for u in low_data_users:
                rem_gb = ((u.get('data_limit') or 0) - (u.get('used_traffic') or 0)) / GB_IN_BYTES
                report_parts.append(format_user_line(u, f"~{rem_gb:.1f} GB مانده"))

        if manual_reminders:
            report_parts.append("\n📝 **پیگیری‌های دستی:**")
            for u, n in manual_reminders.items():
                escaped_note = escape_markdown(n.replace('\n', ' '), 1)
                report_parts.append(format_user_line({'username': u}, escaped_note))

        message = "\n".join(report_parts)
        parse_mode = ParseMode.HTML if any([expiring_users, low_data_users, manual_reminders]) else ParseMode.MARKDOWN_V2

        await context.bot.send_message(
            admin_id, message, parse_mode=parse_mode, disable_web_page_preview=True
        )
    except Exception as e:
        LOGGER.error(f"Critical error in daily reminder job: {e}", exc_info=True)
        try:
            await context.bot.send_message(admin_id, f"❌ **خطای بحرانی** در اجرای جاب روزانه رخ داد: `{e}`")
        except Exception as notify_error:
            LOGGER.error(f"Failed to notify admin about the job failure: {notify_error}")