# FILE: database/db_manager.py (FIXED TABLE NAMES)
import asyncio
import aiomysql
import logging
import json
from typing import List, Dict, Any, Optional
from config import config
from .db_config import db_config

LOGGER = logging.getLogger(__name__)

_pool = None

# --- CHANGE START: Introduce a simple in-memory cache for bot settings ---
_bot_settings_cache: Optional[Dict[str, Any]] = None
# --- CHANGE END ---


async def create_pool():
    global _pool
    # --- CHANGE START: Clear cache on pool creation ---
    global _bot_settings_cache
    _bot_settings_cache = None
    # --- CHANGE END ---
    if not db_config.is_configured():
        LOGGER.warning("Database is not configured. Skipping pool creation.")
        return
    try:
        _pool = await aiomysql.create_pool(
            host=db_config.DB_HOST, user=db_config.DB_USER,
            password=db_config.DB_PASSWORD, db=db_config.DB_NAME,
            autocommit=True,
            loop=None,
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
        _pool.close()
        await _pool.wait_closed()
        _pool = None
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

        # Migration 3: Add base_daily_price to financial_settings
        try:
            await cur.execute("SHOW COLUMNS FROM financial_settings LIKE 'base_daily_price';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'base_daily_price' to 'financial_settings' table.")
                await cur.execute("ALTER TABLE financial_settings ADD COLUMN base_daily_price INT NULL DEFAULT 1000;")
                LOGGER.info("Migration successful for 'base_daily_price'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'base_daily_price': {e}", exc_info=True)
        
        try:
            await cur.execute("SHOW COLUMNS FROM users LIKE 'wallet_balance';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'wallet_balance' to 'users' table.")
                await cur.execute("ALTER TABLE users ADD COLUMN wallet_balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00;")
                LOGGER.info("Migration successful for 'wallet_balance'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'wallet_balance': {e}", exc_info=True)
        
        try:
            await cur.execute("SHOW COLUMNS FROM marzban_telegram_links LIKE 'auto_renew';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'auto_renew' to 'marzban_telegram_links' table.")
                await cur.execute("ALTER TABLE marzban_telegram_links ADD COLUMN auto_renew BOOLEAN NOT NULL DEFAULT FALSE;")
                LOGGER.info("Migration successful for 'auto_renew'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'auto_renew': {e}", exc_info=True)


        try:
            await cur.execute("SHOW COLUMNS FROM users LIKE 'has_received_test_account';")
            if await cur.fetchone():
                LOGGER.info("Applying migration: Dropping obsolete 'has_received_test_account' column.")
                await cur.execute("ALTER TABLE users DROP COLUMN has_received_test_account;")
                LOGGER.info("Migration successful for dropping old column.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for dropping 'has_received_test_account': {e}", exc_info=True)

        try:
            await cur.execute("SHOW COLUMNS FROM users LIKE 'test_accounts_received';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'test_accounts_received' counter to 'users' table.")
                await cur.execute("ALTER TABLE users ADD COLUMN test_accounts_received INT NOT NULL DEFAULT 0;")
                LOGGER.info("Migration successful for 'test_accounts_received'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'test_accounts_received': {e}", exc_info=True)

        try:
            await cur.execute("SHOW COLUMNS FROM user_notes LIKE 'is_test_account';")
            if not await cur.fetchone():
                LOGGER.info("Applying migration: Adding 'is_test_account' to 'user_notes' table.")
                await cur.execute("ALTER TABLE user_notes ADD COLUMN is_test_account BOOLEAN NOT NULL DEFAULT FALSE;")
                LOGGER.info("Migration successful for 'is_test_account'.")
        except Exception as e:
            LOGGER.error(f"Failed to apply migration for 'is_test_account': {e}", exc_info=True)    
  
        
        await conn.commit()
        LOGGER.info("Database migrations finished.")

async def _initialize_db():
    if not _pool: return
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:

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
                
                await cur.execute(""" CREATE TABLE IF NOT EXISTS broadcasts ( job_id VARCHAR(36) PRIMARY KEY, 
                    text TEXT, photo_id VARCHAR(255), buttons JSON, target_user_ids JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
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
            
            # Commit table creation
            await conn.commit()
            await _run_migrations(conn)

        LOGGER.info("Database initialized and migrations checked successfully.")
    except Exception as e:
        LOGGER.error(f"An error occurred during database initialization or migration: {e}", exc_info=True)

# FIX 2: This function is now responsible for committing write operations.
async def execute_query(query, args=None, fetch=None):
    if not _pool: return None
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args or ())
                
                if fetch == 'one':
                    return await cur.fetchone()
                elif fetch == 'all':
                    return await cur.fetchall()
                else:
                    # This is a write operation (INSERT, UPDATE, DELETE)
                    # We commit the transaction to make changes permanent.
                    await conn.commit()
                    return cur.rowcount
    except Exception as e:
        LOGGER.error(f"Query failed: {query} | Error: {e}", exc_info=True)
        # For write operations, we should not hide the error
        return None

# =============================================================================
#  Wallet Management Functions (NEW SECTION)
# =============================================================================

async def get_user_wallet_balance(user_id: int) -> Optional[float]:
    """
    Retrieves the current wallet balance for a specific user.
    Returns the balance as a float, or None if the user is not found.
    """
    query = "SELECT wallet_balance FROM users WHERE user_id = %s;"
    result = await execute_query(query, (user_id,), fetch='one')
    
    if result and 'wallet_balance' in result:
        # The balance is stored as DECIMAL, which aiomysql returns as a Decimal object.
        # We convert it to a float for easier use in the bot logic.
        return float(result['wallet_balance'])
    
    LOGGER.warning(f"Could not retrieve wallet balance for user_id: {user_id}. User may not exist.")
    return None



async def increase_wallet_balance(user_id: int, amount: float) -> Optional[float]:
    """
    Increases a user's wallet balance by a given amount and returns the new balance.
    This operation is atomic to prevent race conditions.
    Returns the new balance, or None if the operation fails.
    """
    if amount <= 0:
        LOGGER.warning(f"Attempted to increase wallet balance with non-positive amount: {amount}")
        return None

    query = "UPDATE users SET wallet_balance = wallet_balance + %s WHERE user_id = %s;"
    result = await execute_query(query, (amount, user_id))

    if result is not None and result > 0:
        # If the update was successful, fetch the new balance to return it
        new_balance = await get_user_wallet_balance(user_id)
        return new_balance
    
    LOGGER.error(f"Failed to increase wallet balance for user_id: {user_id}. User may not exist or DB error.")
    return None

async def decrease_wallet_balance(user_id: int, amount: float) -> Optional[float]:
    """
    Decreases a user's wallet balance by a given amount.
    This operation is atomic and checks for sufficient funds.
    Returns the new balance if successful, or None if funds are insufficient or an error occurs.
    """
    if amount <= 0:
        LOGGER.warning(f"Attempted to decrease wallet balance with non-positive amount: {amount}")
        return None

    # This query atomically updates the balance ONLY IF the user has enough funds.
    query = """
        UPDATE users 
        SET wallet_balance = wallet_balance - %s 
        WHERE user_id = %s AND wallet_balance >= %s;
    """
    
    # The amount is passed twice: once for subtraction, once for the check.
    result = await execute_query(query, (amount, user_id, amount))

    if result is not None and result > 0:
        # The update was successful (1 row affected). Fetch the new balance.
        new_balance = await get_user_wallet_balance(user_id)
        return new_balance
    
    # If result is 0, it means the WHERE clause failed (insufficient funds).
    # If result is None, a DB error occurred.
    LOGGER.warning(f"Failed to decrease wallet balance for user {user_id}. Insufficient funds or DB error.")
    return None

async def add_or_update_user(user) -> bool:
    if not _pool: return False
    is_new_user = False # Initialize as False
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
                exists = await cur.fetchone()
                
                if exists:
                    update_query = "UPDATE users SET first_name = %s, username = %s WHERE user_id = %s;"
                    await cur.execute(update_query, (user.first_name, user.username, user.id))
                else:
                    insert_query = "INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s);"
                    await cur.execute(insert_query, (user.id, user.first_name, user.username))
                    is_new_user = True # Set to True only if it's a new user
                
                await conn.commit() # Save changes
    except Exception as e:
        LOGGER.error(f"Database operation failed for user {user.id}: {e}", exc_info=True)
        return False # Return False on error
        
    return is_new_user # Return the final status
        
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
    query = """
        INSERT INTO template_config (id, template_username, proxies, inbounds)
        VALUES (1, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            template_username = VALUES(template_username),
            proxies = VALUES(proxies),
            inbounds = VALUES(inbounds);
    """
    args = (
        config_data.get("template_username"),
        json.dumps(config_data.get("proxies", {})),
        json.dumps(config_data.get("inbounds", {})),
    )
    return await execute_query(query, args)


async def get_user_note(username: str):
    query = "SELECT subscription_duration, subscription_data_limit_gb, subscription_price FROM user_notes WHERE username = %s;"
    result = await execute_query(query, (username,), fetch='one')
    return result if result else {}

async def save_user_note(username: str, note_data: dict):
    # [FIXED] Corrected table name from `usernotes` to `user_notes` and column names
    query = """
        INSERT INTO user_notes (username, subscription_duration, subscription_data_limit_gb, subscription_price, is_test_account)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            subscription_duration = VALUES(subscription_duration),
            subscription_data_limit_gb = VALUES(subscription_data_limit_gb),
            subscription_price = VALUES(subscription_price),
            is_test_account = VALUES(is_test_account);
    """
    duration = note_data.get('subscription_duration')
    data_limit = note_data.get('subscription_data_limit_gb')
    price = note_data.get('subscription_price')
    is_test = note_data.get('is_test_account', False)
    return await execute_query(query, (username, duration, data_limit, price, is_test))


async def delete_user_note(username: str):
    query = "UPDATE user_notes SET subscription_duration = NULL, subscription_data_limit_gb = NULL, subscription_price = NULL WHERE username = %s;"
    return await execute_query(query, (username,))

async def get_all_users_with_notes():
    query = "SELECT username, subscription_duration, subscription_data_limit_gb, subscription_price FROM user_notes WHERE subscription_duration IS NOT NULL OR subscription_price IS NOT NULL OR subscription_data_limit_gb IS NOT NULL ORDER BY username;"
    return await execute_query(query, fetch='all') or []

async def link_user_to_telegram(marzban_username: str, telegram_user_id: int) -> bool:
    # [FIXED] Corrected table name from `marzbantelegramlinks` to `marzban_telegram_links` and column names
    query = """
        INSERT INTO marzban_telegram_links (marzban_username, telegram_user_id)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE telegram_user_id = VALUES(telegram_user_id);
    """
    result = await execute_query(query, (marzban_username, telegram_user_id))
    return result is not None

async def save_subscription_note(username: str, duration: int, price: int, data_limit_gb: int) -> bool:
    query = """
        INSERT INTO user_notes (username, subscription_duration, subscription_price, subscription_data_limit_gb)
        VALUES (%s, %s, %s, %s)
        AS new_sub
        ON DUPLICATE KEY UPDATE
            subscription_duration = new_sub.subscription_duration,
            subscription_price = new_sub.subscription_price,
            subscription_data_limit_gb = new_sub.subscription_data_limit_gb;
    """
    try:
        result = await execute_query(query, (username, duration, price, data_limit_gb))
        return result is not None
    except Exception as e:
        LOGGER.error(f"Failed to save subscription note for {username}: {e}", exc_info=True)
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
    """
    Loads bot settings from the database.
    Uses an in-memory cache to avoid frequent database reads.
    The cache is populated on the first call and invalidated by save_bot_settings.
    """
    global _bot_settings_cache
    if _bot_settings_cache is not None:
        return _bot_settings_cache.copy()

    query = "SELECT setting_key, setting_value FROM bot_settings;"
    results = await execute_query(query, fetch='all')
    
    settings = {}
    if results:
        for row in results:
            key, value = row['setting_key'], row['setting_value']
            try:
                settings[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                settings[key] = value
        
        for key in ['reminder_days', 'reminder_data_gb', 'auto_delete_grace_days', 
                    'test_account_limit', 'test_account_hours']:
            if key in settings:
                try: settings[key] = int(settings[key])
                except (ValueError, TypeError): pass
        
        if 'test_account_gb' in settings:
             try: settings['test_account_gb'] = float(settings['test_account_gb'])
             except (ValueError, TypeError): pass

    _bot_settings_cache = settings
    LOGGER.info("Bot settings loaded from DB and cached.")
    return _bot_settings_cache.copy()

async def save_bot_settings(settings_to_update: dict) -> bool:
    global _bot_settings_cache
    # [FIXED] Corrected table name from `botsettings` to `bot_settings` and column names
    query = """
        INSERT INTO bot_settings (setting_key, setting_value)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);
    """
    tasks = []
    for key, value in settings_to_update.items():
        value_to_save = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        tasks.append(execute_query(query, (key, value_to_save)))
    results = await asyncio.gather(*tasks)
    if all(r is not None for r in results):
        if _bot_settings_cache is None:
            await load_bot_settings()
        if _bot_settings_cache is not None: # Check if cache was successfully loaded
            _bot_settings_cache.update(settings_to_update)
        LOGGER.info(f"Bot settings saved to DB and cache updated for keys: {list(settings_to_update.keys())}")
        return True
    LOGGER.error("Failed to save one or more bot settings to the database.")
    return False

async def add_to_non_renewal_list(marzban_username: str) -> bool:
    query = "INSERT IGNORE INTO non_renewal_users (marzban_username) VALUES (%s);"
    result = await execute_query(query, (marzban_username,))
    return result is not None

async def is_in_non_renewal_list(marzban_username: str) -> bool:
    query = "SELECT marzban_username FROM non_renewal_users WHERE marzban_username = %s;"
    result = await execute_query(query, (marzban_username,), fetch='one')
    return result is not None

async def get_all_linked_users() -> dict:
    query = "SELECT marzban_username, telegram_user_id FROM marzban_telegram_links;"
    results = await execute_query(query, fetch='all')
    return {row['marzban_username']: row['telegram_user_id'] for row in results} if results else {}


async def load_non_renewal_users() -> list:
    query = "SELECT marzban_username FROM non_renewal_users;"
    results = await execute_query(query, fetch='all')
    return [row['marzban_username'] for row in results] if results else []

async def cleanup_marzban_user_data(marzban_username: str) -> bool:
    if not _pool: return False
    try:
        async with _pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor() as cur:
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
    # [FIXED] Corrected table name from `financialsettings` to `financial_settings` and column names
    card_number = data.get('card_number')
    card_holder = data.get('card_holder')
    query = """
        INSERT INTO financial_settings (id, card_number, card_holder)
        VALUES (1, %s, %s)
        ON DUPLICATE KEY UPDATE
            card_number = VALUES(card_number),
            card_holder = VALUES(card_holder);
    """
    result = await execute_query(query, (card_number, card_holder))
    return result is not None

async def save_pricing_settings(price_per_gb: int, price_per_day: int) -> bool:
    # [FIXED] Corrected table name from `financialsettings` to `financial_settings` and column names
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
    # [FIXED] Corrected table and column names
    buttons_json = json.dumps(buttons) if buttons else None
    query = """
        INSERT INTO guides (guide_key, title, content, photo_file_id, buttons)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            content = VALUES(content),
            photo_file_id = VALUES(photo_file_id),
            buttons = VALUES(buttons);
    """
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
    query = "SELECT invoice_id, plan_details, price, created_at FROM pending_invoices WHERE user_id = %s AND status = 'pending' ORDER BY created_at DESC;"
    results = await execute_query(query, (user_id,), fetch='all')
    
    if not results:
        return []

    for res in results:
        if res.get('plan_details'):
            try:
                res['plan_details'] = json.loads(res['plan_details'])
            except (json.JSONDecodeError, TypeError):
                res['plan_details'] = {}
    return results

async def create_pending_invoice(user_id: int, plan_details: dict, price: int) -> Optional[int]:
    plan_details_json = json.dumps(plan_details)
    query = """
        INSERT INTO pending_invoices (user_id, plan_details, price) 
        VALUES (%s, %s, %s);
    """
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
    query = "SELECT invoice_id, user_id, plan_details, price, status FROM pending_invoices WHERE invoice_id = %s;"
    result = await execute_query(query, (invoice_id,), fetch='one')
    
    if result:
        result['id'] = result.pop('invoice_id')
        if result.get('plan_details'):
            try:
                result['plan_details'] = json.loads(result['plan_details'])
            except (json.JSONDecodeError, TypeError):
                LOGGER.error(f"Failed to decode plan_details JSON for invoice_id {invoice_id}.")
                result['plan_details'] = {}
                
    return result
async def update_invoice_status(invoice_id: int, status: str) -> bool:
    query = "UPDATE pending_invoices SET status = %s WHERE invoice_id = %s;"
    result = await execute_query(query, (status, invoice_id))
    return result is not None and result > 0    

async def expire_old_pending_invoices() -> int:
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
    query = """
        UPDATE unlimited_plans
        SET plan_name = %s, price = %s, max_ips = %s, is_active = %s, sort_order = %s
        WHERE id = %s;
    """
    result = await execute_query(query, (plan_name, price, max_ips, is_active, sort_order, plan_id))
    return result is not None and result > 0

async def delete_unlimited_plan(plan_id: int) -> bool:
    query = "DELETE FROM unlimited_plans WHERE id = %s;"
    result = await execute_query(query, (plan_id,))
    return result is not None and result > 0

async def get_unlimited_plan_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
    query = "SELECT id, plan_name, price, max_ips, is_active, sort_order FROM unlimited_plans WHERE id = %s;"
    return await execute_query(query, (plan_id,), fetch='one')

async def get_all_unlimited_plans() -> List[Dict[str, Any]]:
    query = "SELECT id, plan_name, price, max_ips, is_active, sort_order FROM unlimited_plans ORDER BY sort_order ASC, id ASC;"
    return await execute_query(query, fetch='all') or []

async def get_active_unlimited_plans() -> List[Dict[str, Any]]:
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
    query = "SELECT id, tier_name, volume_limit_gb, price_per_gb FROM volumetric_pricing_tiers ORDER BY volume_limit_gb ASC;"
    return await execute_query(query, fetch='all') or []

async def get_pricing_tier_by_id(tier_id: int) -> Optional[Dict[str, Any]]:
    query = "SELECT id, tier_name, volume_limit_gb, price_per_gb FROM volumetric_pricing_tiers WHERE id = %s;"
    return await execute_query(query, (tier_id,), fetch='one')

async def add_pricing_tier(tier_name: str, volume_limit_gb: int, price_per_gb: int) -> Optional[int]:
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
    query = "UPDATE volumetric_pricing_tiers SET tier_name = %s, volume_limit_gb = %s, price_per_gb = %s WHERE id = %s;"
    result = await execute_query(query, (tier_name, volume_limit_gb, price_per_gb, tier_id))
    return result is not None and result > 0

async def delete_pricing_tier(tier_id: int) -> bool:
    query = "DELETE FROM volumetric_pricing_tiers WHERE id = %s;"
    result = await execute_query(query, (tier_id,))
    return result is not None and result > 0

async def save_base_daily_price(price: int) -> bool:
    query = """
        INSERT INTO financial_settings (id, base_daily_price) 
        VALUES (1, %s) 
        AS new_base_price
        ON DUPLICATE KEY UPDATE base_daily_price = new_base_price.base_daily_price;
    """
    result = await execute_query(query, (price,))
    return result is not None

async def load_pricing_parameters() -> Dict[str, Any]:
    query_base = "SELECT base_daily_price FROM financial_settings WHERE id = 1;"
    base_result = await execute_query(query_base, fetch='one')
    base_price = base_result.get('base_daily_price') if base_result else None

    tiers = await get_all_pricing_tiers()

    return {
        "base_daily_price": base_price,
        "tiers": tiers
    }

async def get_user_by_id(user_id: int) -> dict:
    query = "SELECT user_id, first_name, username FROM users WHERE user_id = %s;"
    return await execute_query(query, (user_id,), fetch='one')

async def is_auto_renew_enabled(telegram_user_id: int, marzban_username: str) -> bool:
    query = "SELECT auto_renew FROM marzban_telegram_links WHERE telegram_user_id = %s AND marzban_username = %s;"
    result = await execute_query(query, (telegram_user_id, marzban_username), fetch='one')
    return bool(result['auto_renew']) if result else False

async def set_auto_renew_status(telegram_user_id: int, marzban_username: str, status: bool) -> bool:
    query = "UPDATE marzban_telegram_links SET auto_renew = %s WHERE telegram_user_id = %s AND marzban_username = %s;"
    result = await execute_query(query, (status, telegram_user_id, marzban_username))
    return result is not None and result > 0

async def get_all_auto_renew_users() -> List[Dict[str, Any]]:
    query = "SELECT telegram_user_id, marzban_username FROM marzban_telegram_links WHERE auto_renew = TRUE;"
    return await execute_query(query, fetch='all') or []

# =============================================================================
#  Optimized Auto-Renewal Job Functions (NEW - FOR PERFORMANCE)
# =============================================================================

async def get_users_ready_for_auto_renewal() -> List[Dict[str, Any]]:
    query = """
        SELECT
            mtl.telegram_user_id,
            mtl.marzban_username,
            un.subscription_price,
            un.subscription_duration,
            u.wallet_balance
        FROM marzban_telegram_links AS mtl
        JOIN users AS u ON mtl.telegram_user_id = u.user_id
        JOIN user_notes AS un ON mtl.marzban_username = un.username
        WHERE
            mtl.auto_renew = TRUE
            AND u.wallet_balance >= un.subscription_price
            AND un.subscription_price IS NOT NULL AND un.subscription_price > 0
            AND un.subscription_duration IS NOT NULL AND un.subscription_duration > 0;
    """
    return await execute_query(query, fetch='all') or []


async def get_users_for_auto_renewal_warning() -> List[Dict[str, Any]]:
    query = """
        SELECT
            mtl.telegram_user_id,
            mtl.marzban_username,
            un.subscription_price,
            u.wallet_balance
        FROM marzban_telegram_links AS mtl
        JOIN users AS u ON mtl.telegram_user_id = u.user_id
        JOIN user_notes AS un ON mtl.marzban_username = un.username
        WHERE
            mtl.auto_renew = TRUE
            AND u.wallet_balance < un.subscription_price
            AND un.subscription_price IS NOT NULL AND un.subscription_price > 0
            AND un.subscription_duration IS NOT NULL AND un.subscription_duration > 0;
    """
    return await execute_query(query, fetch='all') or []

# =============================================================================
#  Test Account Functions (V2 - with Counter)
# =============================================================================

async def get_user_test_account_count(user_id: int) -> int:
    query = "SELECT test_accounts_received FROM users WHERE user_id = %s;"
    result = await execute_query(query, (user_id,), fetch='one')
    return result['test_accounts_received'] if result else 0

async def increment_user_test_account_count(user_id: int) -> bool:
    query = "UPDATE users SET test_accounts_received = test_accounts_received + 1 WHERE user_id = %s;"
    result = await execute_query(query, (user_id,))
    return result is not None and result > 0

async def is_user_admin(user_id: int) -> bool:
    return user_id in config.AUTHORIZED_USER_IDS

# =============================================================================
#  Test Account Cleanup Functions
# =============================================================================

async def get_all_test_accounts() -> List[str]:
    query = "SELECT username FROM user_notes WHERE is_test_account = TRUE;"
    results = await execute_query(query, fetch='all')
    return [row['username'] for row in results] if results else []

async def is_account_test(username: str) -> bool:
    query = "SELECT is_test_account FROM user_notes WHERE username = %s;"
    result = await execute_query(query, (username,), fetch='one')
    return bool(result['is_test_account']) if result else False

# =============================================================================
#  Forced Join Channel Functions (NEW SECTION)
# =============================================================================

async def save_forced_join_channel(channel_username: Optional[str]) -> bool:
    settings_to_save = {"forced_join_channel": channel_username}
    return await save_bot_settings(settings_to_save)

async def load_forced_join_channel() -> Optional[str]:
    settings = await load_bot_settings()
    return settings.get("forced_join_channel")

# =============================================================================
#  Gift and Bonus Functions (NEW SECTION)
# =============================================================================

async def save_welcome_gift_amount(amount: int) -> bool:
    return await save_bot_settings({'welcome_gift_amount': amount})

async def load_welcome_gift_amount() -> int:
    settings = await load_bot_settings()
    return int(settings.get('welcome_gift_amount', 0))

async def increase_balance_for_all_users(amount: float) -> Optional[int]:
    if amount <= 0:
        LOGGER.warning(f"Attempted to apply a universal gift with a non-positive amount: {amount}")
        return 0

    admin_ids_tuple = tuple(config.AUTHORIZED_USER_IDS)
    if not admin_ids_tuple:
        LOGGER.warning("No admin IDs configured, applying gift to all users.")
        query = "UPDATE users SET wallet_balance = wallet_balance + %s;"
        args = (amount,)
    else:
        placeholders = ', '.join(['%s'] * len(admin_ids_tuple))
        query = f"""
            UPDATE users
            SET wallet_balance = wallet_balance + %s
            WHERE user_id NOT IN ({placeholders});
        """
        args = (amount,) + admin_ids_tuple
    
    affected_rows = await execute_query(query, args)
    return affected_rows

async def get_all_user_ids() -> List[int]:
    admin_ids_tuple = tuple(config.AUTHORIZED_USER_IDS)
    if not admin_ids_tuple:
        return []
    placeholders = ', '.join(['%s'] * len(admin_ids_tuple))
    query = f"SELECT user_id FROM users WHERE user_id NOT IN ({placeholders});"
    
    results = await execute_query(query, admin_ids_tuple, fetch='all')
    return [row['user_id'] for row in results] if results else []


# =============================================================================
#  Broadcast Job Functions (NEW SECTION)
# =============================================================================
import json

async def save_broadcast_job(job_id: str, text: str | None, photo_id: str | None, buttons: list, target_user_ids: list | None) -> bool:
    query = """
        INSERT INTO broadcasts (job_id, text, photo_id, buttons, target_user_ids, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW());
    """
    buttons_json = json.dumps(buttons)
    targets_json = json.dumps(target_user_ids) if target_user_ids else None
    
    result = await execute_query(query, (job_id, text, photo_id, buttons_json, targets_json))
    return result is not None

async def get_broadcast_job(job_id: str) -> dict | None:
    query = "SELECT * FROM broadcasts WHERE job_id = %s;"
    result = await execute_query(query, (job_id,), fetch='one')
    if result:
        result['buttons'] = json.loads(result['buttons']) if result.get('buttons') else []
        result['target_user_ids'] = json.loads(result['target_user_ids']) if result.get('target_user_ids') else []
    return result

async def delete_broadcast_job(job_id: str) -> bool:
    query = "DELETE FROM broadcasts WHERE job_id = %s;"
    result = await execute_query(query, (job_id,))
    return result is not None

async def get_user_by_marzban_username(marzban_username: str) -> Optional[Dict[str, Any]]:
    telegram_id = await get_telegram_id_from_marzban_username(marzban_username)
    if not telegram_id:
        return None
    
    user_info = await get_user_by_id(telegram_id)
    if user_info:
        user_info['telegram_id'] = telegram_id
        return user_info

    return None