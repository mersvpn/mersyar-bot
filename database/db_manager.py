# FILE: database/db_manager.py (نسخه نهایی با ایجاد خودکار جدول و توابع مدیریت پلن نامحدود)
import asyncio
import aiomysql
import logging
import json
from typing import List, Dict, Any, Optional

from .db_config import db_config

LOGGER = logging.getLogger(__name__)

_pool = None

async def create_pool():
    global _pool
    if not db_config.is_configured():
        LOGGER.warning("Database is not configured. Skipping pool creation.")
        return
    try:
        _pool = await aiomysql.create_pool(
            host=db_config.DB_HOST, user=db_config.DB_USER,
            password=db_config.DB_PASSWORD, db=db_config.DB_NAME,
            autocommit=True, loop=None, 
            cursorclass=aiomysql.DictCursor
        )
        LOGGER.info("Database connection pool created successfully.")
        await _initialize_db()
    except Exception as e:
        LOGGER.error(f"Failed to create database connection pool: {e}", exc_info=True)
        _pool = None

async def close_pool():
    global _pool
    if _pool:
        _pool.close(); await _pool.wait_closed(); _pool = None
        LOGGER.info("Database connection pool closed.")

async def _run_migrations(conn):
    """Checks for and applies necessary database schema changes."""
    async with conn.cursor() as cur:
        LOGGER.info("Running database migrations...")
        
        # Migration 1: Add price_per_gb
        try:
            await cur.execute("SHOW COLUMNS FROM financial_settings LIKE 'price_per_gb';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'price_per_gb' to 'financial_settings' table.")
                await cur.execute("ALTER TABLE financial_settings ADD COLUMN price_per_gb INT NULL;")
                LOGGER.info("Migration successful for 'price_per_gb'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'price_per_gb': {e}", exc_info=True)

        # Migration 2: Add price_per_day
        try:
            await cur.execute("SHOW COLUMNS FROM financial_settings LIKE 'price_per_day';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'price_per_day' to 'financial_settings' table.")
                await cur.execute("ALTER TABLE financial_settings ADD COLUMN price_per_day INT NULL;")
                LOGGER.info("Migration successful for 'price_per_day'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'price_per_day': {e}", exc_info=True)

        LOGGER.info("Database migrations finished.")

                # Migration 3: Add base_daily_price to financial_settings
        try:
            await cur.execute("SHOW COLUMNS FROM financial_settings LIKE 'base_daily_price';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'base_daily_price' to 'financial_settings' table.")
                # We set a sensible default value
                await cur.execute("ALTER TABLE financial_settings ADD COLUMN base_daily_price INT NULL DEFAULT 1000;")
                LOGGER.info("Migration successful for 'base_daily_price'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'base_daily_price': {e}", exc_info=True)

async def _initialize_db():
    if not _pool: return
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                # ... (تمام دستورات CREATE TABLE IF NOT EXISTS قبلی) ...
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_settings (
                        setting_key VARCHAR(255) PRIMARY KEY, setting_value TEXT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY, first_name VARCHAR(255) NOT NULL,
                        username VARCHAR(255) NULL, is_admin BOOLEAN DEFAULT FALSE,
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS marzban_credentials (
                        id INT PRIMARY KEY DEFAULT 1, base_url VARCHAR(255) NOT NULL,
                        username VARCHAR(255) NOT NULL, password VARCHAR(255) NOT NULL,
                        CONSTRAINT single_row_check CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS financial_settings (
                        id INT PRIMARY KEY DEFAULT 1, card_number VARCHAR(255) NULL,
                        card_holder VARCHAR(255) NULL, CONSTRAINT single_financial_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_notes (
                        username VARCHAR(255) PRIMARY KEY, note TEXT, subscription_duration INT DEFAULT NULL,
                        subscription_data_limit_gb INT DEFAULT NULL, subscription_price INT DEFAULT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS marzban_telegram_links (
                        marzban_username VARCHAR(255) PRIMARY KEY, telegram_user_id BIGINT NOT NULL,
                        INDEX telegram_user_id_idx (telegram_user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_daily_notes (
                        id VARCHAR(36) PRIMARY KEY, title VARCHAR(255) NOT NULL, text TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS template_config (
                        id INT PRIMARY KEY DEFAULT 1, template_username VARCHAR(255) NOT NULL,
                        proxies JSON, inbounds JSON, CONSTRAINT single_template_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS non_renewal_users (marzban_username VARCHAR(255) PRIMARY KEY)
                    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS broadcasts (job_id VARCHAR(36) PRIMARY KEY, data JSON NOT NULL)
                    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_managed_users (marzban_username VARCHAR(255) PRIMARY KEY)
                    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS pending_invoices (
                        invoice_id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        plan_details JSON NOT NULL,
                        price INT NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX user_id_idx (user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")                    
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS guides (
                        guide_key VARCHAR(50) PRIMARY KEY, title VARCHAR(100) NOT NULL, content TEXT,
                        photo_file_id TEXT DEFAULT NULL, buttons JSON DEFAULT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                
                # --- NEW TABLE FOR UNLIMITED PLANS (AUTO-CREATED) ---
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS unlimited_plans (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        plan_name VARCHAR(100) NOT NULL,
                        price INT NOT NULL,
                        max_ips INT NOT NULL DEFAULT 1,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        sort_order INT NOT NULL DEFAULT 0
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                # --- END OF NEW TABLE ---
                # --- NEW TABLE FOR VOLUMETRIC PRICING TIERS (AUTO-CREATED) ---
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS volumetric_pricing_tiers (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        tier_name VARCHAR(100) NOT NULL,
                        volume_limit_gb INT NOT NULL UNIQUE,
                        price_per_gb INT NOT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                # --- END OF NEW TABLE ---

            await _run_migrations(conn)
        LOGGER.info("Database initialized and migrations checked successfully.")
    except Exception as e:
        LOGGER.error(f"An error occurred during database initialization or migration: {e}", exc_info=True)

async def execute_query(query, args=None, fetch=None):
    if not _pool: return None
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args or ())
                if fetch == 'one': return await cur.fetchone()
                elif fetch == 'all': return await cur.fetchall()
                return cur.rowcount
    except Exception as e:
        LOGGER.error(f"Query failed: {query} | Error: {e}", exc_info=True)
        return None

async def add_or_update_user(user) -> bool:
    if not _pool: return False
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
                exists = await cur.fetchone()
                if exists:
                    update_query = "UPDATE users SET first_name = %s, username = %s WHERE user_id = %s;"
                    await cur.execute(update_query, (user.first_name, user.username, user.id))
                    return False
                else:
                    insert_query = "INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s);"
                    await cur.execute(insert_query, (user.id, user.first_name, user.username))
                    return True
    except Exception as e:
        LOGGER.error(f"Database operation failed for user {user.id}: {e}", exc_info=True)
        return False
        
async def get_linked_marzban_usernames(telegram_user_id: int):
    query = "SELECT marzban_username FROM marzban_telegram_links WHERE telegram_user_id = %s;"
    results = await execute_query(query, (telegram_user_id,), fetch='all')
    return [row['marzban_username'] for row in results] if results else []
    
async def get_all_daily_notes():
    query = "SELECT id, title, text, created_at FROM admin_daily_notes ORDER BY title;"
    return await execute_query(query, fetch='all') or []

async def get_daily_note_by_id(note_id: str):
    query = "SELECT id, title, text FROM admin_daily_notes WHERE id = %s;"
    return await execute_query(query, (note_id,), fetch='one')

async def add_daily_note(note_id: str, title: str, text: str):
    query = "INSERT INTO admin_daily_notes (id, title, text) VALUES (%s, %s, %s);"
    return await execute_query(query, (note_id, title, text))

async def update_daily_note(note_id: str, title: str, text: str):
    query = "UPDATE admin_daily_notes SET title = %s, text = %s WHERE id = %s;"
    return await execute_query(query, (title, text, note_id))

async def delete_daily_note_by_id(note_id: str):
    query = "DELETE FROM admin_daily_notes WHERE id = %s;"
    return await execute_query(query, (note_id,))

async def load_template_config_db():
    query = "SELECT template_username, proxies, inbounds FROM template_config WHERE id = 1;"
    result = await execute_query(query, fetch='one')
    if result: return {"template_username": result.get('template_username'), "proxies": json.loads(result.get('proxies', '{}') or '{}'), "inbounds": json.loads(result.get('inbounds', '{}') or '{}')}
    return {}

async def save_template_config_db(config_data: dict):
    query = "INSERT INTO template_config (id, template_username, proxies, inbounds) VALUES (1, %s, %s, %s) ON DUPLICATE KEY UPDATE template_username = VALUES(template_username), proxies = VALUES(proxies), inbounds = VALUES(inbounds);"
    args = (config_data.get("template_username"), json.dumps(config_data.get("proxies", {})), json.dumps(config_data.get("inbounds", {})))
    return await execute_query(query, args)

async def get_user_note(username: str):
    query = "SELECT subscription_duration, subscription_data_limit_gb, subscription_price FROM user_notes WHERE username = %s;"
    result = await execute_query(query, (username,), fetch='one')
    return result if result else {}

async def save_user_note(username: str, note_data: dict):
    query = "INSERT INTO user_notes (username, subscription_duration, subscription_data_limit_gb, subscription_price) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE subscription_duration = VALUES(subscription_duration), subscription_data_limit_gb = VALUES(subscription_data_limit_gb), subscription_price = VALUES(subscription_price);"
    duration = note_data.get('subscription_duration')
    data_limit = note_data.get('subscription_data_limit_gb')
    price = note_data.get('subscription_price')
    return await execute_query(query, (username, duration, data_limit, price))

async def delete_user_note(username: str):
    query = "UPDATE user_notes SET subscription_duration = NULL, subscription_data_limit_gb = NULL, subscription_price = NULL WHERE username = %s;"
    return await execute_query(query, (username,))

async def get_all_users_with_notes():
    query = "SELECT username, subscription_duration, subscription_data_limit_gb, subscription_price FROM user_notes WHERE subscription_duration IS NOT NULL OR subscription_price IS NOT NULL OR subscription_data_limit_gb IS NOT NULL ORDER BY username;"
    return await execute_query(query, fetch='all') or []

async def link_user_to_telegram(marzban_username: str, telegram_user_id: int) -> bool:
    query = "INSERT INTO marzban_telegram_links (marzban_username, telegram_user_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE telegram_user_id = VALUES(telegram_user_id);"
    result = await execute_query(query, (marzban_username, telegram_user_id))
    return result is not None

async def save_subscription_note(username: str, duration: int, price: int, data_limit_gb: int) -> bool:
    """
    Saves or updates subscription details (price, duration, etc.) for a user in the notes table.
    This is used after a new user is created via the automated purchase flow.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                # SQL query to insert or update the user's note
                sql = """
                    INSERT INTO notes (username, subscription_duration, subscription_price, subscription_data_limit_gb, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        subscription_duration = VALUES(subscription_duration),
                        subscription_price = VALUES(subscription_price),
                        subscription_data_limit_gb = VALUES(subscription_data_limit_gb),
                        updated_at = NOW();
                """
                await cursor.execute(sql, (username, duration, price, data_limit_gb))
                await conn.commit()
                return True
            except Exception as e:
                # It's better to log the error for debugging
                # Assuming you have a logger setup similar to other files
                # LOGGER.error(f"Failed to save subscription note for {username}: {e}")
                print(f"Error in save_subscription_note for {username}: {e}") # Or use your logger
                return False
                
async def unlink_user_from_telegram(marzban_username: str) -> bool:
    query = "DELETE FROM marzban_telegram_links WHERE marzban_username = %s;"
    result = await execute_query(query, (marzban_username,))
    return result is not None

async def get_telegram_id_from_marzban_username(marzban_username: str):
    query = "SELECT telegram_user_id FROM marzban_telegram_links WHERE marzban_username = %s;"
    result = await execute_query(query, (marzban_username,), fetch='one')
    return result['telegram_user_id'] if result else None

async def load_bot_settings() -> dict:
    query = "SELECT setting_key, setting_value FROM bot_settings;"
    results = await execute_query(query, fetch='all')
    if not results: return {}
    settings = {}
    for row in results:
        key, value = row['setting_key'], row['setting_value']
        try: settings[key] = json.loads(value)
        except (json.JSONDecodeError, TypeError): settings[key] = value
    for key in ['reminder_days', 'reminder_data_gb', 'auto_delete_grace_days']:
        if key in settings:
            try: settings[key] = int(settings[key])
            except (ValueError, TypeError): pass
    return settings

async def save_bot_settings(settings_to_update: dict):
    query = "INSERT INTO bot_settings (setting_key, setting_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);"
    tasks = []
    for key, value in settings_to_update.items():
        value_to_save = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        tasks.append(execute_query(query, (key, value_to_save)))
    results = await asyncio.gather(*tasks)
    return all(r is not None for r in results)

async def add_to_non_renewal_list(marzban_username: str) -> bool:
    query = "INSERT IGNORE INTO non_renewal_users (marzban_username) VALUES (%s);"
    return await execute_query(query, (marzban_username,))

async def is_in_non_renewal_list(marzban_username: str) -> bool:
    query = "SELECT marzban_username FROM non_renewal_users WHERE marzban_username = %s;"
    result = await execute_query(query, (marzban_username,), fetch='one')
    return result is not None

async def get_all_linked_users() -> dict:
    query = "SELECT marzban_username, telegram_user_id FROM marzban_telegram_links;"
    results = await execute_query(query, fetch='all')
    return {row['marzban_username']: row['telegram_user_id'] for row in results} if results else {}

async def add_broadcast_job(job_data: dict):
    query = "INSERT INTO broadcasts (job_id, data) VALUES (%s, %s);"
    data_str = json.dumps(job_data)
    return await execute_query(query, (job_data['job_id'], data_str))

async def get_broadcast_job(job_id: str):
    query = "SELECT data FROM broadcasts WHERE job_id = %s;"
    result = await execute_query(query, (job_id,), fetch='one')
    return json.loads(result['data']) if result and result.get('data') else None

async def delete_broadcast_job(job_id: str):
    query = "DELETE FROM broadcasts WHERE job_id = %s;"
    return await execute_query(query, (job_id,))

async def load_non_renewal_users() -> list:
    query = "SELECT marzban_username FROM non_renewal_users;"
    results = await execute_query(query, fetch='all')
    return [row['marzban_username'] for row in results] if results else []

async def cleanup_marzban_user_data(marzban_username: str) -> bool:
    if not _pool: return False
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await conn.begin()
                try:
                    await cur.execute("DELETE FROM user_notes WHERE username = %s;", (marzban_username,))
                    await cur.execute("DELETE FROM marzban_telegram_links WHERE marzban_username = %s;", (marzban_username,))
                    await cur.execute("DELETE FROM non_renewal_users WHERE marzban_username = %s;", (marzban_username,))
                    await cur.execute("DELETE FROM bot_managed_users WHERE marzban_username = %s;", (marzban_username,))
                    await conn.commit()
                    return True
                except Exception as inner_e:
                    await conn.rollback()
                    LOGGER.error(f"Transaction rolled back during cleanup for {marzban_username}: {inner_e}")
                    return False
    except Exception as e:
        LOGGER.error(f"Failed to acquire connection for cleanup of {marzban_username}: {e}", exc_info=True)
        return False
        
async def get_total_users_count() -> int:
    query = "SELECT COUNT(*) AS total FROM users;"
    result = await execute_query(query, fetch='one')
    return result['total'] if result and 'total' in result else 0

async def add_user_to_managed_list(marzban_username: str) -> bool:
    query = "INSERT IGNORE INTO bot_managed_users (marzban_username) VALUES (%s);"
    return await execute_query(query, (marzban_username,)) is not None

async def get_all_managed_users() -> list[str]:
    query = "SELECT marzban_username FROM bot_managed_users;"
    results = await execute_query(query, fetch='all')
    return [row['marzban_username'] for row in results] if results else []

async def remove_user_from_managed_list(marzban_username: str) -> bool:
    query = "DELETE FROM bot_managed_users WHERE marzban_username = %s;"
    return await execute_query(query, (marzban_username,)) is not None

async def load_financials() -> dict:
    query = "SELECT card_number, card_holder FROM financial_settings WHERE id = 1;"
    result = await execute_query(query, fetch='one')
    return result if result else {}

async def save_financials(data: dict) -> bool:
    card_number = data.get('card_number')
    card_holder = data.get('card_holder')
    query = """
        INSERT INTO financial_settings (id, card_number, card_holder) VALUES (1, %s, %s) 
        ON DUPLICATE KEY UPDATE card_number = VALUES(card_number), card_holder = VALUES(card_holder);"""
    result = await execute_query(query, (card_number, card_holder))
    return result is not None

async def save_pricing_settings(price_per_gb: int, price_per_day: int) -> bool:
    """Saves or updates the price per GB and price per day for custom plans."""
    query = """
        INSERT INTO financial_settings (id, price_per_gb, price_per_day) 
        VALUES (1, %s, %s) 
        ON DUPLICATE KEY UPDATE 
            price_per_gb = VALUES(price_per_gb), 
            price_per_day = VALUES(price_per_day);
    """
    result = await execute_query(query, (price_per_gb, price_per_day))
    LOGGER.info(f"Custom pricing settings saved: price_per_gb={price_per_gb}, price_per_day={price_per_day}")
    return result is not None

async def load_pricing_settings() -> Dict[str, Optional[int]]:
    """
    Loads pricing settings (price per GB and price per day).
    Returns a dictionary {'price_per_gb': X, 'price_per_day': Y} or empty dict.
    """
    query = "SELECT price_per_gb, price_per_day FROM financial_settings WHERE id = 1;"
    result = await execute_query(query, fetch='one')
    
    if result:
        price_gb = result.get('price_per_gb')
        price_day = result.get('price_per_day')
        return {
            'price_per_gb': int(price_gb) if price_gb is not None else None,
            'price_per_day': int(price_day) if price_day is not None else None
        }
    
    LOGGER.warning("Pricing settings not found in the database.")
    return {'price_per_gb': None, 'price_per_day': None}

async def add_or_update_guide(guide_key: str, title: str, content: str = None, photo_file_id: str = None, buttons: Optional[List[Dict[str, str]]] = None) -> bool:
    buttons_json = json.dumps(buttons) if buttons else None
    query = """
        INSERT INTO guides (guide_key, title, content, photo_file_id, buttons) VALUES (%s, %s, %s, %s, %s) 
        ON DUPLICATE KEY UPDATE title = VALUES(title), content = VALUES(content), 
        photo_file_id = VALUES(photo_file_id), buttons = VALUES(buttons);"""
    result = await execute_query(query, (guide_key, title, content, photo_file_id, buttons_json))
    return result is not None

async def get_guide(guide_key: str) -> Optional[Dict[str, Any]]:
    query = "SELECT guide_key, title, content, photo_file_id, buttons FROM guides WHERE guide_key = %s;"
    guide = await execute_query(query, (guide_key,), fetch='one')
    if guide and guide.get('buttons'):
        try: guide['buttons'] = json.loads(guide['buttons'])
        except (json.JSONDecodeError, TypeError): guide['buttons'] = None
    return guide

async def get_all_guides() -> List[Dict[str, Any]]:
    query = "SELECT guide_key, title, content, photo_file_id, buttons FROM guides ORDER BY title;"
    guides = await execute_query(query, fetch='all') or []
    for guide in guides:
        if guide.get('buttons'):
            try: guide['buttons'] = json.loads(guide['buttons'])
            except (json.JSONDecodeError, TypeError): guide['buttons'] = None
    return guides

async def delete_guide(guide_key: str) -> bool:
    query = "DELETE FROM guides WHERE guide_key = %s;"
    result = await execute_query(query, (guide_key,))
    if result is not None: return result > 0
    return False
# ==================== توابع مدیریت صورتحساب‌های در انتظار ====================

async def get_pending_invoices_for_user(user_id: int) -> List[dict]:
    """
    Retrieves all invoices with 'pending' status for a specific user.
    """
    query = "SELECT invoice_id, plan_details, price, created_at FROM pending_invoices WHERE user_id = %s AND status = 'pending' ORDER BY created_at DESC;"
    results = await execute_query(query, (user_id,), fetch='all')
    
    if not results:
        return []

    # Decode JSON plan_details for each invoice
    for res in results:
        if res.get('plan_details'):
            try:
                res['plan_details'] = json.loads(res['plan_details'])
            except (json.JSONDecodeError, TypeError):
                res['plan_details'] = {}
    return results

async def create_pending_invoice(user_id: int, plan_details: dict, price: int) -> Optional[int]:
    """
    Creates a new pending invoice and returns its ID.
    """
    plan_details_json = json.dumps(plan_details)
    query = """
        INSERT INTO pending_invoices (user_id, plan_details, price) 
        VALUES (%s, %s, %s);
    """
    # We need to get the last inserted ID, so we use a transaction
    if not _pool: return None
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (user_id, plan_details_json, price))
                await conn.commit()
                return cur.lastrowid
    except Exception as e:
        LOGGER.error(f"Failed to create pending invoice for user {user_id}: {e}", exc_info=True)
        return None

async def get_pending_invoice(invoice_id: int) -> Optional[dict]:
    """
    Retrieves a pending invoice by its ID.
    """
    query = "SELECT user_id, plan_details, price, status FROM pending_invoices WHERE invoice_id = %s;"
    result = await execute_query(query, (invoice_id,), fetch='one')
    if result and result.get('plan_details'):
        try:
            result['plan_details'] = json.loads(result['plan_details'])
        except (json.JSONDecodeError, TypeError):
            LOGGER.error(f"Failed to decode plan_details JSON for invoice_id {invoice_id}.")
            result['plan_details'] = {}
    return result

async def update_invoice_status(invoice_id: int, status: str) -> bool:
    """
    Updates the status of an invoice (e.g., to 'approved' or 'rejected').
    """
    query = "UPDATE pending_invoices SET status = %s WHERE invoice_id = %s;"
    result = await execute_query(query, (status, invoice_id))
    return result is not None and result > 0    

    # این تابع را به انتهای فایل database/db_manager.py اضافه کنید

async def expire_old_pending_invoices() -> int:
    """
    Finds all 'pending' invoices older than 24 hours and updates their status to 'expired'.
    Returns the number of invoices that were expired.
    """
    query = """
        UPDATE pending_invoices
        SET status = 'expired'
        WHERE status = 'pending' AND created_at < NOW() - INTERVAL 24 HOUR;
    """
    expired_count = await execute_query(query)
    return expired_count if expired_count is not None else 0

# =============================================================================
#  Unlimited Plan Management (NEW SECTION)
# =============================================================================

async def add_unlimited_plan(plan_name: str, price: int, max_ips: int, sort_order: int) -> Optional[int]:
    """Adds a new unlimited plan to the database and returns its ID."""
    query = """
        INSERT INTO unlimited_plans (plan_name, price, max_ips, sort_order, is_active)
        VALUES (%s, %s, %s, %s, TRUE);
    """
    if not _pool: return None
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (plan_name, price, max_ips, sort_order))
                await conn.commit()
                return cur.lastrowid
    except Exception as e:
        LOGGER.error(f"Failed to add new unlimited plan: {e}", exc_info=True)
        return None

async def update_unlimited_plan(plan_id: int, plan_name: str, price: int, max_ips: int, is_active: bool, sort_order: int) -> bool:
    """Updates an existing unlimited plan."""
    query = """
        UPDATE unlimited_plans
        SET plan_name = %s, price = %s, max_ips = %s, is_active = %s, sort_order = %s
        WHERE id = %s;
    """
    result = await execute_query(query, (plan_name, price, max_ips, is_active, sort_order, plan_id))
    return result is not None and result > 0

async def delete_unlimited_plan(plan_id: int) -> bool:
    """Deletes an unlimited plan from the database."""
    query = "DELETE FROM unlimited_plans WHERE id = %s;"
    result = await execute_query(query, (plan_id,))
    return result is not None and result > 0

async def get_unlimited_plan_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single unlimited plan by its ID."""
    query = "SELECT id, plan_name, price, max_ips, is_active, sort_order FROM unlimited_plans WHERE id = %s;"
    return await execute_query(query, (plan_id,), fetch='one')

async def get_all_unlimited_plans() -> List[Dict[str, Any]]:
    """Fetches all unlimited plans for the admin panel, ordered by sort_order."""
    query = "SELECT id, plan_name, price, max_ips, is_active, sort_order FROM unlimited_plans ORDER BY sort_order ASC, id ASC;"
    return await execute_query(query, fetch='all') or []

async def get_active_unlimited_plans() -> List[Dict[str, Any]]:
    """Fetches all ACTIVE unlimited plans for the customer purchase menu."""
    query = """
        SELECT id, plan_name, price, max_ips FROM unlimited_plans
        WHERE is_active = TRUE
        ORDER BY sort_order ASC, id ASC;
    """
    return await execute_query(query, fetch='all') or []

# =============================================================================
#  Volumetric Pricing Management (NEW SECTION)
# =============================================================================

async def get_all_pricing_tiers() -> List[Dict[str, Any]]:
    """Fetches all volumetric pricing tiers, ordered by their volume limit."""
    query = "SELECT id, tier_name, volume_limit_gb, price_per_gb FROM volumetric_pricing_tiers ORDER BY volume_limit_gb ASC;"
    return await execute_query(query, fetch='all') or []

async def get_pricing_tier_by_id(tier_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single pricing tier by its ID."""
    query = "SELECT id, tier_name, volume_limit_gb, price_per_gb FROM volumetric_pricing_tiers WHERE id = %s;"
    return await execute_query(query, (tier_id,), fetch='one')

async def add_pricing_tier(tier_name: str, volume_limit_gb: int, price_per_gb: int) -> Optional[int]:
    """Adds a new pricing tier and returns its ID."""
    query = "INSERT INTO volumetric_pricing_tiers (tier_name, volume_limit_gb, price_per_gb) VALUES (%s, %s, %s);"
    if not _pool: return None
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (tier_name, volume_limit_gb, price_per_gb))
                await conn.commit()
                return cur.lastrowid
    except Exception as e:
        LOGGER.error(f"Failed to add new pricing tier: {e}", exc_info=True)
        return None

async def update_pricing_tier(tier_id: int, tier_name: str, volume_limit_gb: int, price_per_gb: int) -> bool:
    """Updates an existing pricing tier."""
    query = "UPDATE volumetric_pricing_tiers SET tier_name = %s, volume_limit_gb = %s, price_per_gb = %s WHERE id = %s;"
    result = await execute_query(query, (tier_name, volume_limit_gb, price_per_gb, tier_id))
    return result is not None and result > 0

async def delete_pricing_tier(tier_id: int) -> bool:
    """Deletes a pricing tier."""
    query = "DELETE FROM volumetric_pricing_tiers WHERE id = %s;"
    result = await execute_query(query, (tier_id,))
    return result is not None and result > 0

async def save_base_daily_price(price: int) -> bool:
    """Saves or updates the base daily price in financial_settings."""
    # This also removes the old, now unused, price_per_gb and price_per_day columns for cleanup.
    query = """
        INSERT INTO financial_settings (id, base_daily_price) 
        VALUES (1, %s) 
        ON DUPLICATE KEY UPDATE base_daily_price = VALUES(base_daily_price);
    """
    result = await execute_query(query, (price,))
    return result is not None

async def load_pricing_parameters() -> Dict[str, Any]:
    """
    Loads all necessary parameters for the volumetric pricing formula.
    Fetches the base daily price and all pricing tiers.
    """
    # 1. Get base price
    query_base = "SELECT base_daily_price FROM financial_settings WHERE id = 1;"
    base_result = await execute_query(query_base, fetch='one')
    base_price = base_result.get('base_daily_price') if base_result else None

    # 2. Get all tiers
    tiers = await get_all_pricing_tiers()

    return {
        "base_daily_price": base_price,
        "tiers": tiers
    }