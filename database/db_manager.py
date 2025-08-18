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
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            # We can create tables here if they don't exist
            # For now, let's create a simple settings table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    setting_key VARCHAR(255) PRIMARY KEY,
                    setting_value TEXT
                )
            """)
            LOGGER.info("Database initialized (tables checked/created).")

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
                # For INSERT, UPDATE, DELETE, we don't need to fetch
                return True
    except Exception as e:
        LOGGER.error(f"Query failed: {query} | Error: {e}", exc_info=True)
        return False
        
# ===== USER MANAGEMENT FUNCTIONS =====

async def add_or_update_user(user):
    """
    Adds a new user to the database or updates their info if they already exist.
    This is an "UPSERT" operation.
    """
    query = """
        INSERT INTO users (user_id, first_name, username)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        first_name = VALUES(first_name),
        username = VALUES(username);
    """
    args = (user.id, user.first_name, user.username)
    return await execute_query(query, args)