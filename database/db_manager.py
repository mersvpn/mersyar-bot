# FILE: database/db_manager.py (نسخه نهایی با جدول آموزش، عکس و دکمه)
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

async def _initialize_db():
    if not _pool: return
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                # ... (تمام CREATE TABLE های دیگر بدون تغییر باقی می‌مانند)
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
                        card_holder VARCHAR(255) NULL,
                        CONSTRAINT single_financial_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_notes (
                        username VARCHAR(255) PRIMARY KEY,
                        note TEXT,
                        subscription_duration INT DEFAULT NULL,
                        subscription_data_limit_gb INT DEFAULT NULL,
                        subscription_price INT DEFAULT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS marzban_telegram_links (
                        marzban_username VARCHAR(255) PRIMARY KEY, telegram_user_id BIGINT NOT NULL,
                        INDEX telegram_user_id_idx (telegram_user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS admin_daily_notes (
                        id VARCHAR(36) PRIMARY KEY, title VARCHAR(255) NOT NULL,
                        text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS template_config (
                        id INT PRIMARY KEY DEFAULT 1,
                        template_username VARCHAR(255) NOT NULL,
                        proxies JSON,
                        inbounds JSON,
                        CONSTRAINT single_template_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS non_renewal_users (
                        marzban_username VARCHAR(255) PRIMARY KEY
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS broadcasts (
                        job_id VARCHAR(36) PRIMARY KEY,
                        data JSON NOT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_managed_users (
                        marzban_username VARCHAR(255) PRIMARY KEY
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                
                # ==================== جدول آموزش آپدیت شده ====================
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS guides (
                        guide_key VARCHAR(50) PRIMARY KEY,
                        title VARCHAR(100) NOT NULL,
                        content TEXT,
                        photo_file_id TEXT DEFAULT NULL,
                        buttons JSON DEFAULT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                # =============================================================
        LOGGER.info("Database initialized successfully.")
    except Exception as e:
        LOGGER.error(f"An error occurred during database initialization: {e}", exc_info=True)

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

# ... (تمام توابع دیگر تا بخش توابع آموزش، بدون تغییر باقی می‌مانند)
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
    if 'reminder_days' in settings: settings['reminder_days'] = int(settings['reminder_days'])
    if 'reminder_data_gb' in settings: settings['reminder_data_gb'] = int(settings['reminder_data_gb'])
    if 'auto_delete_grace_days' in settings: settings['auto_delete_grace_days'] = int(settings['auto_delete_grace_days'])
    return settings
async def save_bot_settings(settings_to_update: dict):
    query = "INSERT INTO bot_settings (setting_key, setting_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);"
    tasks = []
    for key, value in settings_to_update.items():
        value_to_save = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        tasks.append(execute_query(query, (key, value_to_save)))
    results = await asyncio.gather(*tasks)
    return all(results)
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
    normalized_username = marzban_username.lower()
    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await conn.begin()
                try:
                    await cur.execute("DELETE FROM user_notes WHERE username = %s;", (normalized_username,))
                    await cur.execute("DELETE FROM marzban_telegram_links WHERE marzban_username = %s;", (normalized_username,))
                    await cur.execute("DELETE FROM non_renewal_users WHERE marzban_username = %s;", (normalized_username,))
                    await cur.execute("DELETE FROM bot_managed_users WHERE marzban_username = %s;", (normalized_username,))
                    await conn.commit()
                    return True
                except Exception as inner_e:
                    await conn.rollback()
                    LOGGER.error(f"Transaction rolled back during cleanup for {normalized_username}: {inner_e}")
                    return False
    except Exception as e:
        LOGGER.error(f"Failed to acquire connection for cleanup of {normalized_username}: {e}", exc_info=True)
        return False
async def get_total_users_count() -> int:
    query = "SELECT COUNT(*) AS total FROM users;"
    result = await execute_query(query, fetch='one')
    return result['total'] if result and 'total' in result else 0
async def add_user_to_managed_list(marzban_username: str) -> bool:
    query = "INSERT IGNORE INTO bot_managed_users (marzban_username) VALUES (%s);"
    result = await execute_query(query, (marzban_username,))
    return result is not None
async def get_all_managed_users() -> list[str]:
    query = "SELECT marzban_username FROM bot_managed_users;"
    results = await execute_query(query, fetch='all')
    return [row['marzban_username'] for row in results] if results else []
async def remove_user_from_managed_list(marzban_username: str) -> bool:
    query = "DELETE FROM bot_managed_users WHERE marzban_username = %s;"
    result = await execute_query(query, (marzban_username,))
    return result is not None

# ==================== توابع مدیریت آموزش (آپدیت شده) ====================
async def add_or_update_guide(guide_key: str, title: str, content: str = None, photo_file_id: str = None, buttons: Optional[List[Dict[str, str]]] = None) -> bool:
    """Adds or updates a guide with photo and button support."""
    # Convert buttons list to a JSON string, or None if it's empty
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
    """Retrieves a specific guide, including photo and buttons."""
    query = "SELECT guide_key, title, content, photo_file_id, buttons FROM guides WHERE guide_key = %s;"
    guide = await execute_query(query, (guide_key,), fetch='one')
    if guide and guide.get('buttons'):
        try:
            guide['buttons'] = json.loads(guide['buttons'])
        except (json.JSONDecodeError, TypeError):
            guide['buttons'] = None # Handle corrupted JSON data
    return guide

async def get_all_guides() -> List[Dict[str, Any]]:
    """Retrieves all guides from the database."""
    query = "SELECT guide_key, title, content, photo_file_id, buttons FROM guides ORDER BY title;"
    guides = await execute_query(query, fetch='all') or []
    for guide in guides:
        if guide.get('buttons'):
            try:
                guide['buttons'] = json.loads(guide['buttons'])
            except (json.JSONDecodeError, TypeError):
                guide['buttons'] = None
    return guides

async def delete_guide(guide_key: str) -> bool:
    """Deletes a guide from the database and logs the outcome."""
    query = "DELETE FROM guides WHERE guide_key = %s;"
    result = await execute_query(query, (guide_key,))
    if result is not None:
        if result > 0:
            LOGGER.info(f"Successfully deleted guide with key '{guide_key}'.")
            return True
        else:
            LOGGER.warning(f"Attempted to delete guide with key '{guide_key}', but it was not found.")
            return False
    else:
        return False