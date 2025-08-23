# FILE: database/db_manager.py
# (نسخه کامل و نهایی با تابع جدید)

import aiomysql
import logging
import json
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
            autocommit=True, loop=None
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
                
                try:
                    await cur.execute("ALTER TABLE marzban_telegram_links DROP INDEX telegram_user_id_idx;")
                    await cur.execute("CREATE INDEX telegram_user_id_idx ON marzban_telegram_links (telegram_user_id);")
                except aiomysql.OperationalError: pass
                
                try:
                    await cur.execute("ALTER TABLE user_notes ADD COLUMN subscription_duration INT DEFAULT NULL;")
                except aiomysql.OperationalError as e:
                    if e.args[0] == 1060: pass
                    else: raise
                try:
                    await cur.execute("ALTER TABLE user_notes ADD COLUMN subscription_price INT DEFAULT NULL;")
                except aiomysql.OperationalError as e:
                    if e.args[0] == 1060: pass
                    else: raise
        LOGGER.info("Database initialized successfully (all tables checked/created/updated).")
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
                return True
    except Exception as e:
        LOGGER.error(f"Query failed: {query} | Error: {e}", exc_info=True)
        return False

async def add_or_update_user(user):
    query = "INSERT INTO users (user_id, first_name, username) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE first_name = VALUES(first_name), username = VALUES(username);"
    return await execute_query(query, (user.id, user.first_name, user.username))

async def get_linked_marzban_usernames(telegram_user_id: int):
    query = "SELECT marzban_username FROM marzban_telegram_links WHERE telegram_user_id = %s;"
    results = await execute_query(query, (telegram_user_id,), fetch='all')
    return [row[0] for row in results] if results is not None else []

async def get_all_daily_notes():
    query = "SELECT id, title, text, created_at FROM admin_daily_notes ORDER BY title;"
    results = await execute_query(query, fetch='all')
    return [{"id": r[0], "title": r[1], "text": r[2], "created_at": r[3]} for r in results] if results else []

async def get_daily_note_by_id(note_id: str):
    query = "SELECT id, title, text FROM admin_daily_notes WHERE id = %s;"
    result = await execute_query(query, (note_id,), fetch='one')
    return {"id": result[0], "title": result[1], "text": result[2]} if result else None

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
    if result:
        return {
            "template_username": result[0],
            "proxies": json.loads(result[1]) if result[1] else {},
            "inbounds": json.loads(result[2]) if result[2] else {}
        }
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
        json.dumps(config_data.get("inbounds", {}))
    )
    return await execute_query(query, args)

async def get_user_note(username: str):
    """Fetches structured note data (duration and price) for a user."""
    query = "SELECT subscription_duration, subscription_price FROM user_notes WHERE username = %s;"
    result = await execute_query(query, (username,), fetch='one')
    if result:
        return {
            "subscription_duration": result[0],
            "subscription_price": result[1]
        }
    return {}

async def save_user_note(username: str, note_data: dict):
    """Saves or updates a structured note for a user."""
    query = """
        INSERT INTO user_notes (username, subscription_duration, subscription_price)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        subscription_duration = VALUES(subscription_duration),
        subscription_price = VALUES(subscription_price);
    """
    duration = note_data.get('subscription_duration')
    price = note_data.get('subscription_price')
    return await execute_query(query, (username, duration, price))

async def delete_user_note(username: str):
    """Deletes a user's note data."""
    query = "UPDATE user_notes SET subscription_duration = NULL, subscription_price = NULL WHERE username = %s;"
    return await execute_query(query, (username,))

# --- NEW FUNCTION with correct indentation ---
async def get_all_users_with_notes():
    """
    Fetches all users who have subscription details (duration or price) set.
    """
    query = """
        SELECT username, subscription_duration, subscription_price
        FROM user_notes
        WHERE subscription_duration IS NOT NULL AND subscription_price IS NOT NULL
        ORDER BY username;
    """
    results = await execute_query(query, fetch='all')
    if not results:
        return []
    
    return [
        {
            "username": row[0],
            "subscription_duration": row[1],
            "subscription_price": row[2]
        }
        for row in results
    ]