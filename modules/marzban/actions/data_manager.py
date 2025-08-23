# modules/marzban/actions/data_manager.py

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Union

from database import db_manager

LOGGER = logging.getLogger(__name__)

# --- FILE-BASED STORAGE (for settings that are okay to be in files) ---

try:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
except NameError:
    PROJECT_ROOT = Path.cwd().resolve()

DATA_DIR = PROJECT_ROOT
NON_RENEWAL_FILE = DATA_DIR / "non_renewal_users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
BROADCASTS_FILE = DATA_DIR / "broadcasts.json"
# All other JSON files are now removed

_locks: Dict[Path, asyncio.Lock] = {
    file_path: asyncio.Lock() for file_path in [
        NON_RENEWAL_FILE, SETTINGS_FILE, BROADCASTS_FILE
    ]
}

async def _load_json_file(file_path: Path, is_list: bool = False) -> Union[Dict, List]:
    default_empty = [] if is_list else {}
    lock = _locks.get(file_path, asyncio.Lock())
    async with lock:
        if not file_path.exists():
            file_path.write_text(json.dumps(default_empty), encoding='utf-8')
            return default_empty
        try:
            content = file_path.read_text(encoding='utf-8')
            return json.loads(content) if content else default_empty
        except (json.JSONDecodeError, IOError):
            file_path.write_text(json.dumps(default_empty), encoding='utf-8')
            return default_empty

async def _save_json_file(file_path: Path, data: Union[Dict, List]) -> None:
    lock = _locks.get(file_path, asyncio.Lock())
    async with lock:
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')

def normalize_username(username: str) -> str:
    return username.lower()

# --- DATABASE-BASED STORAGE FUNCTIONS ---

async def load_marzban_credentials() -> Dict[str, str]:
    query = "SELECT base_url, username, password FROM marzban_credentials WHERE id = 1;"
    result = await db_manager.execute_query(query, fetch='one')
    return {"base_url": result[0], "username": result[1], "password": result[2]} if result else {}

async def save_marzban_credentials(credentials: Dict[str, str]) -> bool:
    query = "INSERT INTO marzban_credentials (id, base_url, username, password) VALUES (1, %s, %s, %s) ON DUPLICATE KEY UPDATE base_url = VALUES(base_url), username = VALUES(username), password = VALUES(password);"
    args = (credentials.get("base_url"), credentials.get("username"), credentials.get("password"))
    return await db_manager.execute_query(query, args)

async def load_financials() -> Dict[str, str]:
    query = "SELECT card_number, card_holder FROM financial_settings WHERE id = 1;"
    result = await db_manager.execute_query(query, fetch='one')
    return {"card_number": result[0] or "", "card_holder": result[1] or ""} if result else {"card_number": "", "card_holder": ""}

async def save_financials(financial_data: Dict[str, str]) -> bool:
    query = "INSERT INTO financial_settings (id, card_number, card_holder) VALUES (1, %s, %s) ON DUPLICATE KEY UPDATE card_number = VALUES(card_number), card_holder = VALUES(card_holder);"
    args = (financial_data.get("card_number"), financial_data.get("card_holder"))
    return await db_manager.execute_query(query, args)

async def load_reminders() -> Dict[str, str]:
    query = "SELECT username, note FROM user_notes;"
    results = await db_manager.execute_query(query, fetch='all')
    return {row[0]: row[1] for row in results} if results else {}

async def save_reminders(reminders: Dict[str, str]) -> bool:
    delete_query = "DELETE FROM user_notes;"
    if not await db_manager.execute_query(delete_query): return False
    if not reminders: return True
    insert_query = "INSERT INTO user_notes (username, note) VALUES (%s, %s);"
    success = True
    for username, note in reminders.items():
        if not await db_manager.execute_query(insert_query, (username, note)):
            success = False
    return success

async def load_users_map() -> Dict[str, int]:
    query = "SELECT marzban_username, telegram_user_id FROM marzban_telegram_links;"
    results = await db_manager.execute_query(query, fetch='all')
    return {row[0]: row[1] for row in results} if results else {}

async def save_users_map(users_map: Dict[str, int]) -> bool:
    # This function is deprecated, use link_user_to_telegram instead for single user operations.
    # We keep it for now for compatibility, but it's inefficient.
    delete_query = "DELETE FROM marzban_telegram_links;"
    if not await db_manager.execute_query(delete_query): return False
    if not users_map: return True
    insert_query = "INSERT INTO marzban_telegram_links (marzban_username, telegram_user_id) VALUES (%s, %s);"
    success = True
    for marzban_username, telegram_user_id in users_map.items():
        if not await db_manager.execute_query(insert_query, (normalize_username(marzban_username), telegram_user_id)):
            success = False
    return success

async def link_user_to_telegram(marzban_username: str, telegram_user_id: int) -> bool:
    query = "INSERT INTO marzban_telegram_links (marzban_username, telegram_user_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE telegram_user_id = VALUES(telegram_user_id);"
    return await db_manager.execute_query(query, (normalize_username(marzban_username), telegram_user_id))

# --- TEMPLATE CONFIG: Now from database ---
async def load_template_config() -> Dict[str, Any]:
    return await db_manager.load_template_config_db()

async def save_template_config(config_data: Dict[str, Any]) -> bool:
    if 'template_username' in config_data:
        config_data['template_username'] = normalize_username(config_data['template_username'])
    return await db_manager.save_template_config_db(config_data)
# --- END OF TEMPLATE CONFIG ---


# --- FILE-BASED functions that are still needed ---
async def load_non_renewal_users() -> List[str]: return await _load_json_file(NON_RENEWAL_FILE, is_list=True)
async def save_non_renewal_users(users_list: List[str]) -> None: await _save_json_file(NON_RENEWAL_FILE, sorted(list(set(normalize_username(u) for u in users_list))))
async def load_settings() -> Dict[str, Any]:
    from modules.reminder.actions.constants import DEFAULT_REMINDER_TIME_TEHRAN, DEFAULT_REMINDER_DAYS_THRESHOLD, DEFAULT_REMINDER_DATA_THRESHOLD_GB
    settings = await _load_json_file(SETTINGS_FILE)
    settings.setdefault('reminder_time', DEFAULT_REMINDER_TIME_TEHRAN); settings.setdefault('reminder_days', DEFAULT_REMINDER_DAYS_THRESHOLD); settings.setdefault('reminder_data_gb', DEFAULT_REMINDER_DATA_THRESHOLD_GB)
    return settings
async def save_settings(settings: Dict[str, Any]) -> None: await _save_json_file(SETTINGS_FILE, settings)
async def load_broadcasts() -> Dict[str, Any]: return await _load_json_file(BROADCASTS_FILE)
async def save_broadcasts(broadcast_data: Dict[str, Any]) -> None: await _save_json_file(BROADCASTS_FILE, broadcast_data)