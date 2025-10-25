# --- START OF FILE modules/reminder/actions/jobs.py ---
import datetime
import logging
import jdatetime
from telegram.ext import ContextTypes, Application
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from modules.marzban.actions.api import get_all_users, delete_user_api, get_user_data
from modules.marzban.actions.constants import GB_IN_BYTES
from shared.log_channel import send_log
from database.crud import (
    bot_setting as crud_bot_setting,
    non_renewal_user as crud_non_renewal,
    pending_invoice as crud_invoice,
    bot_managed_user as crud_managed_user,
    user_note as crud_user_note,
    user as crud_user,marzban_link as crud_marzban_link
)
from modules.marzban.actions.data_manager import cleanup_marzban_user_data, load_users_map
from modules.payment.actions.approval import approve_payment

LOGGER = logging.getLogger(__name__)

async def _perform_auto_renewal(context: ContextTypes.DEFAULT_TYPE, telegram_user_id: int, marzban_username: str, subscription_price: int, **kwargs) -> bool:
    price = float(subscription_price)

    new_balance = await crud_user.decrease_wallet_balance(telegram_user_id, price)
    if new_balance is None:
        LOGGER.error(f"Auto-renew for {marzban_username} aborted: Insufficient funds at the moment of transaction.")
        return False

    LOGGER.info(f"Auto-renewal funds secured for {marzban_username}. Balance deducted. Proceeding to renewal.")

    note_data = await crud_user_note.get_user_note(marzban_username)
    duration = note_data.subscription_duration if note_data else 30
    user_panel_data = await get_user_data(marzban_username)
    volume_gb = (user_panel_data.get('data_limit', 0) / GB_IN_BYTES) if user_panel_data else 0

    plan_details = {
        'username': marzban_username,
        'volume': volume_gb,
        'duration': duration,
        'price': price,
        'invoice_type': 'RENEWAL'
    }
    
    invoice_obj = await crud_invoice.create_pending_invoice({
        'user_id': telegram_user_id,
        'plan_details': plan_details,
        'price': int(price)
    })

    if not invoice_obj:
        LOGGER.critical(f"CRITICAL: Wallet balance for {marzban_username} was deducted, but invoice creation failed. Rolling back payment.")
        await crud_user.increase_wallet_balance(telegram_user_id, price)
        return False

    class MockUser:
        id = 0
        full_name = "سیستم تمدید خودکار"

    class MockQuery:
        data = f"approve_receipt_{invoice_obj.invoice_id}"
        message = type('obj', (object,), {'caption' : f"Auto-approved invoice #{invoice_obj.invoice_id} via auto-renew job"})()
        async def answer(self, *args, **kwargs): pass
        async def edit_message_caption(self, *args, **kwargs): pass
    
    class MockUpdate:
        effective_user = MockUser()
        callback_query = MockQuery()
        
    try:
        await approve_payment(MockUpdate(), context)
        LOGGER.info(f"Auto-renewal for {marzban_username} (Invoice #{invoice_obj.invoice_id}) completed successfully.")
        return True
    except Exception as e:
        LOGGER.critical(f"CRITICAL: Auto-renewal for {marzban_username} failed at approval stage. Rolling back payment. Error: {e}", exc_info=True)
        await crud_user.increase_wallet_balance(telegram_user_id, price)
        return False


async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    
    admin_id = context.job.chat_id
    bot_username = context.bot.username
    LOGGER.info(f"Executing daily job for admin {admin_id}...")

    try:
        expired_count = await crud_invoice.expire_old_pending_invoices()
        if expired_count > 0:
            log_message = _("reminder_jobs.invoice_expiry_report_title")
            log_message += _("reminder_jobs.invoice_expiry_report_body", count=f"`{expired_count}`")
            await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)

        settings = await crud_bot_setting.load_bot_settings()
        all_users_from_panel = await get_all_users()
        if all_users_from_panel is None:
            await context.bot.send_message(admin_id, _("reminder_jobs.daily_report_panel_error"))
            return

        panel_users_dict = {user['username']: user for user in all_users_from_panel if user.get('username')}
        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        non_renewal_list = await crud_non_renewal.get_all_non_renewal_users()
        users_map = await load_users_map()
        
        # [ORM CHANGE]: Use the new CRUD function
        auto_renew_candidates = await crud_marzban_link.get_all_auto_renew_links()
        
        expiring_users, low_data_users, auto_renew_success_report, auto_renew_fail_report = [], [], [], []
        processed_users = set()

        LOGGER.info(f"Found {len(auto_renew_candidates)} total users with auto-renew enabled. Checking them now...")
        for user_link in auto_renew_candidates:  # <-- Changed variable name for clarity
            # [ORM CHANGE]: Access attributes with dot notation
            marzban_username = user_link.marzban_username
            telegram_user_id = user_link.telegram_user_id
            
            panel_user = panel_users_dict.get(marzban_username)
            note_info = await crud_user_note.get_user_note(marzban_username)
            
            if not panel_user or panel_user.get('status') != 'active' or (note_info and note_info.is_test_account):
                continue

            if expire_ts := panel_user.get('expire'):
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                now = datetime.datetime.now()
                if now < expire_date < (now + datetime.timedelta(days=days_threshold)):
                    
                    user_note = await crud_user_note.get_user_note(marzban_username)
                    wallet_balance_obj = await crud_user.get_user_wallet_balance(telegram_user_id)
                    wallet_balance = float(wallet_balance_obj) if wallet_balance_obj is not None else 0.0
                    price = float(user_note.subscription_price) if user_note and user_note.subscription_price is not None else 0.0

                    if wallet_balance >= price and price > 0:
                        LOGGER.info(f"Attempting auto-renewal for '{marzban_username}' (Sufficient funds).")
                        full_user_data = {
                            "telegram_user_id": telegram_user_id,
                            "marzban_username": marzban_username,
                            "subscription_price": int(price),
                            "subscription_duration": user_note.subscription_duration if user_note else 30
                        }

                        if await _perform_auto_renewal(context, **full_user_data):
                            auto_renew_success_report.append(panel_user)
                        else:
                            auto_renew_fail_report.append(panel_user)
                    
                    else:
                        LOGGER.info(f"User '{marzban_username}' has insufficient funds for auto-renewal. Sending warning.")
                        try:
                            await context.bot.send_message(telegram_user_id, _("reminder_jobs.auto_renew_failed_customer_funds"))
                            auto_renew_fail_report.append(panel_user)
                        except Exception as e:
                            LOGGER.warning(f"Failed to send warning to customer for {marzban_username}: {e}")
                    
                    processed_users.add(marzban_username)
        
        LOGGER.info("Processing standard reminders for users without auto-renew or not in expiry window.")
        for panel_user in all_users_from_panel:
            username = panel_user.get('username')
            note_info = await crud_user_note.get_user_note(username)
            if not username or username in processed_users or username in non_renewal_list:
                continue

            if panel_user.get('status') != 'active' or (note_info and note_info.is_test_account):
                continue

            is_expiring, is_low_data, expire_date = False, False, None
            if expire_ts := panel_user.get('expire'):
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                if datetime.datetime.now() < expire_date < (datetime.datetime.now() + datetime.timedelta(days=days_threshold)):
                    is_expiring = True
            
            data_limit = panel_user.get('data_limit') or 0
            if data_limit > 0 and (data_limit - (panel_user.get('used_traffic') or 0)) < (data_gb_threshold * GB_IN_BYTES):
                is_low_data = True
            
            customer_telegram_id = users_map.get(username)
            if customer_telegram_id and (is_expiring or is_low_data):
                try:
                    customer_message = _("reminder_jobs.customer_reminder_title", username=f"`{username}`")
                    if is_expiring and expire_date:
                        time_left = expire_date - datetime.datetime.now()
                        customer_message += _("reminder_jobs.customer_reminder_days_left", days=time_left.days + 1)
                    if is_low_data:
                        remaining_gb = (data_limit - (panel_user.get('used_traffic') or 0)) / GB_IN_BYTES
                        customer_message += _("reminder_jobs.customer_reminder_data_left", gb=f"{remaining_gb:.2f}")
                    customer_message += _("reminder_jobs.customer_reminder_footer")
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(_("reminder_jobs.button_request_renewal"), callback_data=f"customer_renew_request_{username}")],
                        [InlineKeyboardButton(_("reminder_jobs.button_do_not_renew"), callback_data=f"customer_do_not_renew_{username}")]
                    ])
                    await context.bot.send_message(chat_id=customer_telegram_id, text=customer_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    LOGGER.warning(f"Failed to send reminder to customer {customer_telegram_id} for user {username}: {e}")

            if is_expiring: expiring_users.append(panel_user)
            if is_low_data and not is_expiring: low_data_users.append(panel_user)
        
        auto_renew_attempts = auto_renew_success_report + auto_renew_fail_report
        if any([expiring_users, low_data_users, auto_renew_attempts]):
            jalali_today = jdatetime.datetime.now().strftime('%Y/%m/%d')
            report_parts = [_("reminder_jobs.admin_daily_report_title", date=jalali_today)]
            
            def format_user_line(u, reason):
                uname = u.get('username', 'N/A')
                return f"▪️ <a href='https://t.me/{bot_username}?start=details_{uname}'>{uname}</a> - <i>{reason}</i>"

            if auto_renew_success_report:
                report_parts.append("✅ **تمدیدهای خودکار موفق**")
                for u in auto_renew_success_report: report_parts.append(format_user_line(u, "موفقیت‌آمیز"))
            
            if auto_renew_fail_report:
                report_parts.append("⚠️ **تمدیدهای خودکار ناموفق**")
                for u in auto_renew_fail_report: report_parts.append(format_user_line(u, "ناموفق (موجودی ناکافی)"))

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
    
    LOGGER.info("Starting auto-delete job for expired users...")
    
    settings = await crud_bot_setting.load_bot_settings()
    grace_days = settings.get('auto_delete_grace_days', 0)
    if grace_days <= 0:
        LOGGER.info("Auto-delete is disabled. Skipping."); return

    all_users = await get_all_users()
    if all_users is None:
        LOGGER.error("Auto-delete job failed: Could not fetch users."); return

    managed_users_set = set(await crud_managed_user.get_all_managed_users())
    if not managed_users_set:
        LOGGER.info("No bot-managed users found. Auto-delete job finished."); return
        
    deleted_users = []
    grace_period = datetime.timedelta(days=grace_days)

    for user in all_users:
        username = user.get('username')
        if not username or user.get('status') == 'active' or username not in managed_users_set:
            continue
            
        if expire_ts := user.get('expire'):
            expire_date = datetime.datetime.fromtimestamp(expire_ts)
            if datetime.datetime.now() > (expire_date + grace_period):
                LOGGER.info(f"User '{username}' is expired for more than {grace_days} days. Deleting...")
                if (await delete_user_api(username))[0]:
                    await cleanup_marzban_user_data(username)
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
    try:
        settings = await crud_bot_setting.load_bot_settings()
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


# FILE: modules/reminder/actions/jobs.py
# START: Replace the entire cleanup_expired_test_accounts function with this one

async def cleanup_expired_test_accounts(context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    
    LOGGER.info("Starting hourly job: Cleaning up expired test accounts...")
    
    test_accounts = await crud_user_note.get_all_test_accounts()
    
    if not test_accounts:
        LOGGER.info("Test account cleanup job finished. No test accounts found in the database.")
        return
        
    LOGGER.info(f"Found {len(test_accounts)} test accounts to check.")
    
    deleted_users_count = 0
    
    users_map = await load_users_map()

    for test_account in test_accounts:
        username = test_account.username
        telegram_user_id = users_map.get(username)
        
        user_data = await get_user_data(username)
        
        # Scenario 1: User is in our DB but not in Marzban panel (ghost user)
        if not user_data:
            LOGGER.warning(f"Test account '{username}' found in DB but not in Marzban. Cleaning up DB records.")
            await cleanup_marzban_user_data(username)
            # (✨ FIX) No message is sent to the user in this silent cleanup job.
            continue
            
        expire_ts = user_data.get('expire', 0)
        
        # Scenario 2: User exists and their expiration time has passed
        if expire_ts and expire_ts < datetime.datetime.now().timestamp():
            LOGGER.info(f"Test account '{username}' has expired. Deleting now...")
            
            success, message = await delete_user_api(username)
            if success:
                await cleanup_marzban_user_data(username)
                deleted_users_count += 1
                LOGGER.info(f"Successfully deleted expired test account '{username}'.")
                
                # (✨ FIX) The block that sent a message to the user has been completely removed.
                # The primary job (_cleanup_test_account_job) is responsible for notifying the user.
                # This hourly job only cleans up silently.
                
            else:
                LOGGER.error(f"Failed to delete expired test account '{username}' from Marzban. API Error: {message}")
                
    # This part remains to notify the ADMIN via the log channel.
    if deleted_users_count > 0:
        log_message = _("reminder_jobs.test_account_cleanup_report", count=deleted_users_count)
        await send_log(context.bot, log_message)
        LOGGER.info(f"Test account cleanup job finished. Deleted {deleted_users_count} expired accounts.")
    else:
        LOGGER.info("Test account cleanup job finished. No accounts were expired.")

# END: Replace the entire cleanup_expired_test_accounts function with this one