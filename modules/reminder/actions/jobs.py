# FILE: modules/reminder/actions/jobs.py (REVISED FOR I18N)

import datetime
import logging
import jdatetime
from telegram.ext import ContextTypes, Application
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from modules.marzban.actions.data_manager import load_users_map, normalize_username
from modules.marzban.actions.api import get_all_users, delete_user_api
from modules.marzban.actions.constants import GB_IN_BYTES
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    from database.db_manager import load_bot_settings, load_non_renewal_users, expire_old_pending_invoices
    
    admin_id = context.job.chat_id
    bot_username = context.bot.username
    LOGGER.info(f"Executing daily job for admin {admin_id}...")

    try:
        expired_count = await expire_old_pending_invoices()
        if expired_count > 0:
            log_message = _("reminder_jobs.invoice_expiry_report_title")
            log_message += _("reminder_jobs.invoice_expiry_report_body", count=f"`{expired_count}`")
            await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)
            LOGGER.info(f"Successfully expired {expired_count} old pending invoices.")

        settings = await load_bot_settings()
        users_map = await load_users_map()
        
        all_users = await get_all_users()
        if all_users is None:
            await context.bot.send_message(admin_id, _("reminder_jobs.daily_report_panel_error"), parse_mode=ParseMode.MARKDOWN)
            return

        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        non_renewal_list = await load_non_renewal_users()
        
        expiring_users, low_data_users = [], []

        for user in all_users:
            username = user.get('username')
            if not username or user.get('status') != 'active' or normalize_username(username) in non_renewal_list:
                continue
            
            is_expiring, is_low_data, expire_date = False, False, None
            if expire_ts := user.get('expire'):
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                now = datetime.datetime.now()
                if now < expire_date < (now + datetime.timedelta(days=days_threshold)):
                    is_expiring = True
            
            # ✨✨✨ KEY FIX HERE ✨✨✨
            # Ensure that data_limit and used_traffic are never None.
            # `or 0` handles the case where the key exists but its value is None.
            data_limit = user.get('data_limit') or 0
            used_traffic = user.get('used_traffic') or 0
            
            if data_limit > 0 and (data_limit - used_traffic) < (data_gb_threshold * GB_IN_BYTES):
                is_low_data = True
            
            customer_telegram_id = users_map.get(normalize_username(username))
            if customer_telegram_id and (is_expiring or is_low_data):
                try:
                    customer_message = _("reminder_jobs.customer_reminder_title", username=f"`{username}`")
                    if is_expiring and expire_date:
                        time_left = expire_date - datetime.datetime.now()
                        customer_message += _("reminder_jobs.customer_reminder_days_left", days=time_left.days + 1)
                    if is_low_data:
                        remaining_gb = (data_limit - used_traffic) / GB_IN_BYTES
                        customer_message += _("reminder_jobs.customer_reminder_data_left", gb=f"{remaining_gb:.2f}")
                    customer_message += _("reminder_jobs.customer_reminder_footer")
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(_("reminder_jobs.button_request_renewal"), callback_data=f"customer_renew_request_{username}")],
                        [InlineKeyboardButton(_("reminder_jobs.button_do_not_renew"), callback_data=f"customer_do_not_renew_{username}")]
                    ])
                    await context.bot.send_message(
                        chat_id=customer_telegram_id, text=customer_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    LOGGER.warning(f"Failed to send reminder to customer {customer_telegram_id} for user {username}: {e}")

            if is_expiring: expiring_users.append(user)
            if is_low_data and not is_expiring: low_data_users.append(user)
        
        # ... (بقیه تابع بدون تغییر باقی می‌ماند) ...
        if any([expiring_users, low_data_users]):
            jalali_today = jdatetime.datetime.now().strftime('%Y/%m/%d')
            report_parts = [_("reminder_jobs.admin_daily_report_title", date=jalali_today)]
            
            def format_user_line(u, reason):
                uname = u.get('username', 'N/A')
                return f"▪️ <a href='https://t.me/{bot_username}?start=details_{uname}'>{uname}</a> - <i>{reason}</i>"
                
            if expiring_users:
                report_parts.append(_("reminder_jobs.admin_report_expiring_users_title"))
                for u in expiring_users:
                    time_left = datetime.datetime.fromtimestamp(u['expire']) - datetime.datetime.now()
                    reason = _("reminder_jobs.admin_report_expiring_reason", days=time_left.days + 1)
                    report_parts.append(format_user_line(u, reason))
                    
            if low_data_users:
                report_parts.append(_("reminder_jobs.admin_report_low_data_users_title"))
                for u in low_data_users:
                    rem_gb = ((u.get('data_limit', 0)) - (u.get('used_traffic', 0))) / GB_IN_BYTES
                    reason = _("reminder_jobs.admin_report_low_data_reason", gb=f"{rem_gb:.1f}")
                    report_parts.append(format_user_line(u, reason))
                    
            await context.bot.send_message(admin_id, "\n".join(report_parts), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            LOGGER.info("No items to report today. Reminder job finished.")
        
        await auto_delete_expired_users(context)
    except Exception as e:
        LOGGER.error(f"Critical error in daily job: {e}", exc_info=True)
        try:
            error_message = _("reminder_jobs.critical_error_in_job", error=f"`{escape_markdown(str(e), 2)}`")
            await context.bot.send_message(admin_id, error_message, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as notify_error:
            LOGGER.error(f"Failed to notify admin about the job failure: {notify_error}")

async def auto_delete_expired_users(context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    from database.db_manager import load_bot_settings, get_all_managed_users, cleanup_marzban_user_data
    
    LOGGER.info("Starting auto-delete job for expired users...")
    
    settings = await load_bot_settings()
    grace_days = settings.get('auto_delete_grace_days', 0)
    if grace_days <= 0:
        LOGGER.info("Auto-delete is disabled. Skipping."); return

    all_users = await get_all_users()
    if all_users is None:
        LOGGER.error("Auto-delete job failed: Could not fetch users."); return

    managed_users_set = set(await get_all_managed_users())
    if not managed_users_set:
        LOGGER.info("No bot-managed users found. Auto-delete job finished."); return
        
    deleted_users = []
    grace_period = datetime.timedelta(days=grace_days)

    for user in all_users:
        username = user.get('username')
        if not username or user.get('status') == 'active' or normalize_username(username) not in managed_users_set:
            continue
            
        if expire_ts := user.get('expire'):
            expire_date = datetime.datetime.fromtimestamp(expire_ts)
            if datetime.datetime.now() > (expire_date + grace_period):
                LOGGER.info(f"User '{username}' is expired for more than {grace_days} days. Deleting...")
                if (await delete_user_api(username))[0]:
                    await cleanup_marzban_user_data(normalize_username(username))
                    deleted_users.append(username)
                else:
                    LOGGER.error(f"Failed to delete user '{username}' from Marzban panel.")
    
    if deleted_users:
        safe_deleted_list = ", ".join(f"`{u}`" for u in deleted_users)
        log_message = _("reminder_jobs.auto_delete_report_title")
        log_message += _("reminder_jobs.auto_delete_report_body", count=len(deleted_users), users=safe_deleted_list)
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        LOGGER.info("Auto-delete job finished. No users met deletion criteria.")

async def schedule_initial_daily_job(application: Application):
    from database.db_manager import load_bot_settings
    try:
        settings = await load_bot_settings()
        admin_id = application.bot_data.get('admin_id_for_jobs')
        if not admin_id:
            LOGGER.warning("Cannot schedule daily job: Admin ID not found."); return
        time_obj = datetime.datetime.strptime(settings.get('reminder_time', "09:00"), '%H:%M').time()
        await schedule_daily_job(application, time_obj)
    except Exception as e:
        LOGGER.error(f"Failed to schedule initial daily job: {e}", exc_info=True)

async def schedule_daily_job(application: Application, time_obj: datetime.time):
    admin_id = application.bot_data.get('admin_id_for_jobs')
    if not admin_id: return
    
    job_queue = application.job_queue
    if not job_queue: LOGGER.warning("JobQueue is not available. Cannot schedule job."); return
        
    job_name = f"daily_reminder_job_{admin_id}"
    for job in job_queue.get_jobs_by_name(job_name): job.schedule_removal()

    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    job_time = datetime.time(hour=time_obj.hour, minute=time_obj.minute, tzinfo=tehran_tz)
    
    job_queue.run_daily(callback=check_users_for_reminders, time=job_time, chat_id=admin_id, name=job_name)
    LOGGER.info(f"Daily job (reminders & cleanup) scheduled for {job_time.strftime('%H:%M')} Tehran time.")