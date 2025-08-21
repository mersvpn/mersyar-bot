# FILE: database/db_manager.py

import aiomysql
import logging
from .db_config import db_config

LOGGER = logging.getLogger(__name__)

# A global pool for database connections
_pool = None

async def create_pool():
    global _pool
    if not db_config.is_configured():
        LOGGER.warning("Database is not configured. Skipping pool creation.")
        return

    try:
        _pool = await aiomysql.create_pool(
            host=db_config.DB_HOST,
            user=db_config.DB_USER,
            password=db_config.DB_PASSWORD,
            db=db_config.DB_NAME,
            autocommit=True,
            loop=None 
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

async def _initialize_db():
    """
    Ensures all necessary tables are created and updated in the database upon startup.
    This function is idempotent and safe to run on every bot start.
    """
    if not _pool:
        LOGGER.error("Database initialization failed: Pool is not available.")
        return

    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_settings (
                        setting_key VARCHAR(255) PRIMARY KEY,
                        setting_value TEXT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255) NOT NULL,
                        username VARCHAR(255) NULL,
                        is_admin BOOLEAN DEFAULT FALSE,
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS marzban_credentials (
                        id INT PRIMARY KEY DEFAULT 1,
                        base_url VARCHAR(255) NOT NULL,
                        username VARCHAR(255) NOT NULL,
                        password VARCHAR(255) NOT NULL,
                        CONSTRAINT single_row_check CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS financial_settings (
                        id INT PRIMARY KEY DEFAULT 1,
                        card_number VARCHAR(255) NULL,
                        card_holder VARCHAR(255) NULL,
                        CONSTRAINT single_financial_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_notes (
                        username VARCHAR(255) PRIMARY KEY,
                        note TEXT,
                        subscription_duration INT DEFAULT 30
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # This table was almost correct, but a user can have multiple accounts,
                # so the UNIQUE index on telegram_user_id was wrong. PRIMARY KEY on username is enough.
                # I've removed the UNIQUE index to allow multiple marzban_usernames per telegram_user_id.
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS marzban_telegram_links (
                        marzban_username VARCHAR(255) PRIMARY KEY,
                        telegram_user_id BIGINT NOT NULL,
                        INDEX telegram_user_id_idx (telegram_user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)
                try: # --- This part is new to fix the unique constraint if it exists ---
                    await cur.execute("ALTER TABLE marzban_telegram_links DROP INDEX telegram_user_id_idx;")
                    await cur.execute("CREATE INDEX telegram_user_id_idx ON marzban_telegram_links (telegram_user_id);")
                except aiomysql.OperationalError as e:
                    if "check that column/key exists" in str(e) or "doesn't exist" in str(e): pass # Index doesn't exist, which is fine
                    else: raise
                # --- End of fix ---
                
                try:
                    await cur.execute("ALTER TABLE user_notes ADD COLUMN subscription_duration INT DEFAULT 30;")
                    LOGGER.info("Column 'subscription_duration' added to 'user_notes' table.")
                except aiomysql.OperationalError as e:
                    if e.args[0] == 1060: pass
                    else: raise

        LOGGER.info("Database initialized successfully (all tables checked/created/updated).")
    except Exception as e:
        LOGGER.error(f"An error occurred during database initialization: {e}", exc_info=True)

async def execute_query(query, args=None, fetch=None):
    if not _pool:
        LOGGER.error("Query execution failed: Database pool is not available.")
        return None

    try:
        async with _pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args or ())
                if fetch == 'one':
                    return await cur.fetchone()
                elif fetch == 'all':
                    return await cur.fetchall()
                return True
    except Exception as e:
        LOGGER.error(f"Query failed: {query} | Error: {e}", exc_info=True)
        return False

# ===== USER MANAGEMENT FUNCTIONS =====

async def add_or_update_user(user):
    query = """
        INSERT INTO users (user_id, first_name, username)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        first_name = VALUES(first_name),
        username = VALUES(username);
    """
    args = (user.id, user.first_name, user.username)
    return await execute_query(query, args)

async def get_user_note_and_duration(username: str):
    """
    Fetches the note and subscription duration for a specific user.
    """
    query = "SELECT note, subscription_duration FROM user_notes WHERE username = %s;"
    result = await execute_query(query, (username,), fetch='one')
    if result:
        return {"note": result[0], "subscription_duration": result[1]}
    return None

# <--- کد جدید از اینجا شروع می‌شود --->
async def get_linked_marzban_usernames(telegram_user_id: int):
    """
    Fetches all Marzban usernames linked to a given Telegram user ID.
    Returns a list of usernames.
    """
    query = "SELECT marzban_username FROM marzban_telegram_links WHERE telegram_user_id = %s;"
    results = await execute_query(query, (telegram_user_id,), fetch='all')
    if results is None: # In case of DB error
        return []
    # The result is a list of tuples like [('user1',), ('user2',)]. We need a simple list ['user1', 'user2'].
    return [row[0] for row in results]
# <--- کد جدید در اینجا پایان می‌یابد --->