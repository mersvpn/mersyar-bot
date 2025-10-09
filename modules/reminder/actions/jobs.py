# FILE: modules/reminder/actions/jobs.py (REFACTORED & OPTIMIZED VERSION)

import datetime
import logging
import jdatetime
from telegram.ext import ContextTypes, Application
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from modules.marzban.actions.data_manager import load_users_map, normalize_username
from modules.marzban.actions.api import get_all_users, delete_user_api, get_user_data # (renew_user_subscription_api removed)
from modules.marzban.actions.constants import GB_IN_BYTES
from shared.log_channel import send_log
from database.db_manager import (
    load_bot_settings, load_non_renewal_users, expire_old_pending_invoices,
    
    get_users_ready_for_auto_renewal, get_users_for_auto_renewal_warning, 
    get_all_managed_users, cleanup_marzban_user_data,get_all_test_accounts,is_account_test,create_pending_invoice,
    decrease_wallet_balance, increase_wallet_balance, get_user_note, get_all_auto_renew_users, get_user_wallet_balance
)
from modules.payment.actions.approval import approve_payment 

LOGGER = logging.getLogger(__name__)

async def _perform_auto_renewal(context: ContextTypes.DEFAULT_TYPE, telegram_user_id: int, marzban_username: str, subscription_price: int, **kwargs) -> bool:
    """
    Performs auto-renewal by first deducting from the wallet, and if successful,
    directly triggering the approval logic.
    """
    price = float(subscription_price)

    # Step 1: Secure the funds first
    new_balance = await decrease_wallet_balance(telegram_user_id, price)
    if new_balance is None:
        LOGGER.error(f"Auto-renew for {marzban_username} aborted: Insufficient funds at the moment of transaction.")
        return False

    LOGGER.info(f"Auto-renewal funds secured for {marzban_username}. Balance deducted. Proceeding to renewal.")

    # Step 2: Create a temporary invoice for the approval system to process
    # Note: We need to get duration and volume for the invoice details
    note_data = await get_user_note(marzban_username)
    duration = note_data.get('subscription_duration', 30)
    user_panel_data = await get_user_data(marzban_username)
    volume_gb = (user_panel_data.get('data_limit', 0) / GB_IN_BYTES) if user_panel_data else 0

    plan_details = {
        'username': marzban_username,
        'volume': volume_gb,
        'duration': duration,
        'price': price,
        'invoice_type': 'RENEWAL'
    }
    invoice_id = await create_pending_invoice(telegram_user_id, plan_details, price)
    if not invoice_id:
        LOGGER.critical(f"CRITICAL: Wallet balance for {marzban_username} was deducted, but invoice creation failed. Rolling back payment.")
        await increase_wallet_balance(telegram_user_id, price)
        return False

    # Step 3: Trigger the approval logic directly using a mock update
    class MockUser:
        id = 0
        full_name = "سیستم تمدید خودکار"

    class MockQuery:
        data = f"approve_receipt_{invoice_id}"
        message = type('obj', (object,), {'caption' : f"Auto-approved invoice #{invoice_id} via auto-renew job"})()
        async def answer(self, *args, **kwargs): pass
        async def edit_message_caption(self, *args, **kwargs): pass
    
    class MockUpdate:
        effective_user = MockUser()
        callback_query = MockQuery()
        
    try:
        await approve_payment(MockUpdate(), context)
        LOGGER.info(f"Auto-renewal for {marzban_username} (Invoice #{invoice_id}) completed successfully.")
        return True
    except Exception as e:
        LOGGER.critical(f"CRITICAL: Auto-renewal for {marzban_username} failed at approval stage. Rolling back payment. Error: {e}", exc_info=True)
        await increase_wallet_balance(telegram_user_id, price)
        return False
# =============================================================================
#  Main Daily Job Function (Completely Refactored for Performance)
# =============================================================================

async def check_users_for_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    
    admin_id = context.job.chat_id
    bot_username = context.bot.username
    LOGGER.info(f"Executing daily job for admin {admin_id}...")

    try:
        # --- Stage 0: Initial Cleanup ---
        expired_count = await expire_old_pending_invoices()
        if expired_count > 0:
            log_message = _("reminder_jobs.invoice_expiry_report_title")
            log_message += _("reminder_jobs.invoice_expiry_report_body", count=f"`{expired_count}`")
            await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)

        # --- Stage 1: Load essential data ---
        settings = await load_bot_settings()
        all_users_from_panel = await get_all_users()
        if all_users_from_panel is None:
            await context.bot.send_message(admin_id, _("reminder_jobs.daily_report_panel_error"))
            return

        panel_users_dict = {user['username']: user for user in all_users_from_panel if user.get('username')}
        days_threshold = settings.get('reminder_days', 3)
        data_gb_threshold = settings.get('reminder_data_gb', 1)
        non_renewal_list = await load_non_renewal_users()
        users_map = await load_users_map()
        
        # Get all users with auto-renew enabled from the links table
        auto_renew_candidates = await get_all_auto_renew_users()
        
        # --- Initialize report lists ---
        expiring_users, low_data_users, auto_renew_success_report, auto_renew_fail_report = [], [], [], []
        processed_users = set()

        # --- Stage 2: Process ALL auto-renewal candidates ---
        LOGGER.info(f"Found {len(auto_renew_candidates)} total users with auto-renew enabled. Checking them now...")
        for user_data in auto_renew_candidates:
            marzban_username = user_data['marzban_username']
            panel_user = panel_users_dict.get(marzban_username)

            if not panel_user or panel_user.get('status') != 'active' or await is_account_test(marzban_username):
                continue

            if expire_ts := panel_user.get('expire'):
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                now = datetime.datetime.now()
                # Check if user is in the renewal window
                if now < expire_date < (now + datetime.timedelta(days=days_threshold)):
                    
                    # Fetch the LATEST wallet balance and note info right before processing
                    user_note = await get_user_note(marzban_username)
                    wallet_balance = await get_user_wallet_balance(user_data['telegram_user_id'])
                    price = float(user_note.get('subscription_price', 0))

                    # Scenario A: Sufficient funds
                    if wallet_balance is not None and wallet_balance >= price and price > 0:
                        LOGGER.info(f"Attempting auto-renewal for '{marzban_username}' (Sufficient funds).")
                        # Pass all necessary data to the renewal function
                        full_user_data = {
                            "telegram_user_id": user_data['telegram_user_id'],
                            "marzban_username": marzban_username,
                            "subscription_price": price,
                            "subscription_duration": user_note.get('subscription_duration', 30)
                        }

                        if await _perform_auto_renewal(context, **full_user_data):
                            auto_renew_success_report.append(panel_user)
                        else:
                            auto_renew_fail_report.append(panel_user)
                    
                    # Scenario B: Insufficient funds
                    else:
                        LOGGER.info(f"User '{marzban_username}' has insufficient funds for auto-renewal. Sending warning.")
                        try:
                            await context.bot.send_message(user_data['telegram_user_id'], _("reminder_jobs.auto_renew_failed_customer_funds"))
                            auto_renew_fail_report.append(panel_user)
                        except Exception as e:
                            LOGGER.warning(f"Failed to send warning to customer for {marzban_username}: {e}")
                    
                    processed_users.add(marzban_username)
        
        # --- Stage 3: Process Standard Reminders for Remaining Users ---
        LOGGER.info("Processing standard reminders for users without auto-renew or not in expiry window.")
        for panel_user in all_users_from_panel:
            username = panel_user.get('username')
            if not username or username in processed_users or normalize_username(username) in non_renewal_list:
                continue

            if panel_user.get('status') != 'active' or await is_account_test(username):
                continue

            is_expiring, is_low_data, expire_date = False, False, None
            if expire_ts := panel_user.get('expire'):
                expire_date = datetime.datetime.fromtimestamp(expire_ts)
                if datetime.datetime.now() < expire_date < (datetime.datetime.now() + datetime.timedelta(days=days_threshold)):
                    is_expiring = True
            
            data_limit = panel_user.get('data_limit') or 0
            if data_limit > 0 and (data_limit - (panel_user.get('used_traffic') or 0)) < (data_gb_threshold * GB_IN_BYTES):
                is_low_data = True
            
            customer_telegram_id = users_map.get(normalize_username(username))
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
        
        # --- Stage 4: Compile and Send Admin Report ---
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
        
        # --- Stage 5: Run Cleanup Job ---
        await auto_delete_expired_users(context)

    except Exception as e:
        LOGGER.error(f"Critical error in daily job: {e}", exc_info=True)
        try:
            error_message = _("reminder_jobs.critical_error_in_job", error=f"`{escape_markdown(str(e), 2)}`")
            await context.bot.send_message(admin_id, error_message, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as notify_error:
            LOGGER.error(f"Failed to notify admin about the job failure: {notify_error}")

# The auto_delete_expired_users function does not need changes as it's already efficient.
async def auto_delete_expired_users(context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    
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


# The scheduling functions do not need changes.
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

# =============================================================================
#  Hourly Job for Test Account Cleanup
# =============================================================================

async def cleanup_expired_test_accounts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This job runs periodically (e.g., hourly) to find and delete expired test accounts.
    (MODIFIED: Sends notification to customer after deleting expired test account)
    """
    from shared.translator import _
    
    LOGGER.info("Starting hourly job: Cleaning up expired test accounts...")
    
    # 1. Get the list of all usernames marked as 'test_account' from our DB
    test_account_usernames = await get_all_test_accounts()
    
    if not test_account_usernames:
        LOGGER.info("Test account cleanup job finished. No test accounts found in the database.")
        return
        
    LOGGER.info(f"Found {len(test_account_usernames)} test accounts to check.")
    
    deleted_users_count = 0
    
    # (NEW) Load users_map to find Telegram ID for notifications
    users_map = await load_users_map()

    # 2. Iterate through each test account username
    for username in test_account_usernames:
        telegram_user_id = users_map.get(normalize_username(username)) # (NEW) Get Telegram user ID
        
        # 3. Get the user's current data from the Marzban panel
        user_data = await get_user_data(username)
        
        # If user doesn't exist in Marzban, clean them up from our DB anyway
        if not user_data:
            LOGGER.warning(f"Test account '{username}' found in DB but not in Marzban. Cleaning up DB records.")
            await cleanup_marzban_user_data(normalize_username(username))
            # (NEW) If we have a Telegram ID, notify the user they are cleaned up
            if telegram_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=telegram_user_id,
                        text=_("customer.test_account.account_expired_notification_no_panel"),
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(_("general.buy_subscription_button"), callback_data="customer_show_shop")
                        ]])
                    )
                except Exception as e:
                    LOGGER.warning(f"Failed to send cleanup notification to user {telegram_user_id} for ghost test account {username}: {e}")
            continue
            
        # 4. Check if the user is expired
        expire_ts = user_data.get('expire', 0)
        
        # Only proceed if the user has an expiration date and it's in the past
        if expire_ts and expire_ts < datetime.datetime.now().timestamp():
            LOGGER.info(f"Test account '{username}' has expired. Deleting now...")
            
            # 5. Delete the user from both Marzban panel and our local database
            success, message = await delete_user_api(username)
            if success:
                await cleanup_marzban_user_data(normalize_username(username))
                deleted_users_count += 1
                LOGGER.info(f"Successfully deleted expired test account '{username}'.")
                
                # (NEW) Send notification to the user
                if telegram_user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=telegram_user_id,
                            text=_("customer.test_account.account_expired_notification"),
                            parse_mode=ParseMode.HTML,
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton(_("general.buy_subscription_button"), callback_data="customer_show_shop")
                            ]])
                        )
                    except Exception as e:
                        LOGGER.warning(f"Failed to send expiration notification to user {telegram_user_id} for test account {username}: {e}")
            else:
                LOGGER.error(f"Failed to delete expired test account '{username}' from Marzban. API Error: {message}")
                
    if deleted_users_count > 0:
        log_message = _("reminder_jobs.test_account_cleanup_report", count=deleted_users_count)
        await send_log(context.bot, log_message)
        LOGGER.info(f"Test account cleanup job finished. Deleted {deleted_users_count} expired accounts.")
    else:
        LOGGER.info("Test account cleanup job finished. No accounts were expired.")