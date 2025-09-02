# FILE: modules/reminder/actions/jobs.py (نسخه نهایی با قابلیت حذف خودکار)

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


# ==================== بخش اصلی جاب روزانه ====================

# FILE: modules/reminder/actions/jobs.py
# فقط این تابع را به طور کامل جایگزین کنید

async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    # --- 🟢 بخش اضافه شده برای منقضی کردن فاکتورها 🟢 ---
    from database.db_manager import load_bot_settings, load_non_renewal_users, expire_old_pending_invoices
    
    admin_id = context.job.chat_id
    bot_username = context.bot.username
    LOGGER.info(f"Executing daily job for admin {admin_id}...")

    try:
        # 1. منقضی کردن فاکتورهای قدیمی در ابتدای جاب
        expired_count = await expire_old_pending_invoices()
        if expired_count > 0:
            log_message = f"🧾 **گزارش انقضای فاکتور**\n\nتعداد `{expired_count}` فاکتور پرداخت نشده که بیش از ۲۴ ساعت از ایجادشان گذشته بود، به صورت خودکار منقضی شدند."
            await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)
            LOGGER.info(f"Successfully expired {expired_count} old pending invoices.")
        # --- -------------------------------------------------- ---

        # 2. ادامه منطق قبلی برای ارسال یادآورها
        settings = await load_bot_settings()
        users_map = await load_users_map()
        
        all_users = await get_all_users()
        if all_users is None:
            await context.bot.send_message(admin_id, "⚠️ **گزارش روزانه:**\n\nربات نتوانست لیست کاربران را از پنل مرزبان دریافت کند.", parse_mode=ParseMode.MARKDOWN)
            return

        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        non_renewal_list = await load_non_renewal_users()
        
        expiring_users = []
        low_data_users = []

        for user in all_users:
            username = user.get('username')
            if not username: continue
            
            status = user.get('status')
            normalized_name = normalize_username(username)

            if status != 'active' or normalized_name in non_renewal_list:
                continue
            
            is_expiring, is_low_data, expire_date = False, False, None
            expire_ts = user.get('expire')
            if expire_ts:
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                now = datetime.datetime.now()
                if now < expire_date < (now + datetime.timedelta(days=days_threshold)):
                    is_expiring = True

            data_limit = user.get('data_limit') or 0
            used_traffic = user.get('used_traffic') or 0
            if data_limit > 0:
                remaining_traffic = data_limit - used_traffic
                if remaining_traffic < (data_gb_threshold * GB_IN_BYTES):
                    is_low_data = True
            
            customer_telegram_id = users_map.get(normalized_name)
            if customer_telegram_id and (is_expiring or is_low_data):
                try:
                    customer_message = f"🔔 **یادآور اشتراک: `{username}`**\n\n"
                    if is_expiring and expire_date:
                        time_left = expire_date - datetime.datetime.now()
                        customer_message += f"⏳ کمتر از **{time_left.days + 1} روز** تا پایان اشتراک شما باقی مانده است.\n"
                    if is_low_data:
                        remaining_gb = (data_limit - used_traffic) / GB_IN_BYTES
                        customer_message += f"📉 کمتر از **{remaining_gb:.2f} گیگابایت** از حجم شما باقی مانده است.\n"
                    customer_message += "\nبرای جلوگیری از هرگونه قطعی، لطفاً نسبت به تمدید اشتراک خود اقدام نمایید."
                    
                    # --- 🟢 اصلاح callback_data برای یادآور تمدید 🟢 ---
                    # این اصلاح تضمین می‌کند که نام کاربری به درستی ارسال شود
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ درخواست تمدید", callback_data=f"customer_renew_request_{username}")],
                        [InlineKeyboardButton("❌ عدم تمدید این دوره", callback_data=f"customer_do_not_renew_{username}")]
                    ])
                    # --- ---------------------------------------------- ---
                    
                    await context.bot.send_message(
                        chat_id=customer_telegram_id, text=customer_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    LOGGER.warning(f"Failed to send reminder to customer {customer_telegram_id} for user {username}: {e}")

            if is_expiring: expiring_users.append(user)
            if is_low_data and user not in expiring_users: low_data_users.append(user)
        
        # --- ارسال گزارش به ادمین ---
        if any([expiring_users, low_data_users]):
            jalali_today = jdatetime.datetime.now().strftime('%Y/%m/%d')
            report_parts = [f"🔔 **گزارش یادآور روزانه - {jalali_today}**\n"]
            def format_user_line(u, reason):
                uname = u.get('username', 'USERNAME_MISSING')
                return f"▪️ <a href='https://t.me/{bot_username}?start=details_{uname}'>{uname}</a> - <i>{reason}</i>"
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
            message = "\n".join(report_parts)
            await context.bot.send_message(admin_id, message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            LOGGER.info("No items to report today. Reminder job finished.")
        
        # --- اجرای جاب حذف خودکار پس از ارسال یادآورها ---
        await auto_delete_expired_users(context)

    except Exception as e:
        LOGGER.error(f"Critical error in daily job: {e}", exc_info=True)
        try:
            error_message = f"❌ **خطای بحرانی** در اجرای جاب روزانه رخ داد: `{escape_markdown(str(e), 2)}`"
            await context.bot.send_message(admin_id, error_message, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as notify_error:
            LOGGER.error(f"Failed to notify admin about the job failure: {notify_error}")

# ==================== تابع جدید برای حذف خودکار ====================
async def auto_delete_expired_users(context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.db_manager import load_bot_settings, get_all_managed_users, cleanup_marzban_user_data
    
    LOGGER.info("Starting auto-delete job for expired users...")
    
    settings = await load_bot_settings()
    grace_days = settings.get('auto_delete_grace_days', 0)

    # اگر دوره ارفاق 0 باشد، قابلیت غیرفعال است
    if grace_days <= 0:
        LOGGER.info("Auto-delete is disabled (grace period is 0). Skipping.")
        return

    all_users = await get_all_users()
    if all_users is None:
        LOGGER.error("Auto-delete job failed: Could not fetch users from Marzban API.")
        return

    managed_users_set = set(await get_all_managed_users())
    if not managed_users_set:
        LOGGER.info("No bot-managed users found. Auto-delete job finished.")
        return
        
    deleted_users = []
    now = datetime.datetime.now()
    grace_period = datetime.timedelta(days=grace_days)

    for user in all_users:
        username = user.get('username')
        if not username: continue
            
        normalized_username = normalize_username(username)

        # شرط ۱: کاربر باید تحت مدیریت این ربات باشد
        if normalized_username not in managed_users_set:
            continue
            
        # شرط ۲: کاربر باید غیرفعال باشد
        if user.get('status') == 'active':
            continue
            
        # شرط ۳: باید تاریخ انقضا داشته باشد و دوره ارفاق گذشته باشد
        expire_ts = user.get('expire')
        if expire_ts:
            expire_date = datetime.datetime.fromtimestamp(expire_ts)
            if now > (expire_date + grace_period):
                LOGGER.info(f"User '{username}' is expired for more than {grace_days} days. Deleting...")
                success, _ = await delete_user_api(username)
                if success:
                    await cleanup_marzban_user_data(normalized_username)
                    deleted_users.append(username)
                else:
                    LOGGER.error(f"Failed to delete user '{username}' from Marzban panel.")
    
    if deleted_users:
        safe_deleted_list = ", ".join(f"`{u}`" for u in deleted_users)
        log_message = (
            f"🗑️ *گزارش حذف خودکار*\n\n"
            f"{len(deleted_users)} کاربر منقضی شده که دوره ارفاق آن‌ها به پایان رسیده بود، با موفقیت از سیستم حذف شدند:\n"
            f"{safe_deleted_list}"
        )
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        LOGGER.info("Auto-delete job finished. No users met the criteria for deletion.")


# ==================== توابع زمان‌بندی (بدون تغییر) ====================
async def schedule_initial_daily_job(application: Application):
    from database.db_manager import load_bot_settings
    try:
        settings = await load_bot_settings()
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
    LOGGER.info(f"Daily job (reminders & cleanup) scheduled for {job_time.strftime('%H:%M')} Tehran time.")