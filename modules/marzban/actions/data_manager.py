# modules/marzban/actions/data_manager.py
# (کد کامل و جایگزین)

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Union

LOGGER = logging.getLogger(__name__)

try:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
except NameError:
    PROJECT_ROOT = Path.cwd().resolve()

DATA_DIR = PROJECT_ROOT
USERS_MAP_FILE = DATA_DIR / "users.json"
TEMPLATE_CONFIG_FILE = DATA_DIR / "template_config.json"
REMINDERS_FILE = DATA_DIR / "reminders.json"
NON_RENEWAL_FILE = DATA_DIR / "non_renewal_users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
BROADCASTS_FILE = DATA_DIR / "broadcasts.json"
FINANCIALS_FILE = DATA_DIR / "financials.json"
MARZBAN_CREDENTIALS_FILE = DATA_DIR / "marzban_credentials.json" # <-- فایل جدید

_locks: Dict[Path, asyncio.Lock] = {
    file_path: asyncio.Lock() for file_path in [
        USERS_MAP_FILE, TEMPLATE_CONFIG_FILE, REMINDERS_FILE,
        NON_RENEWAL_FILE, SETTINGS_FILE, BROADCASTS_FILE,
        FINANCIALS_FILE, MARZBAN_CREDENTIALS_FILE # <-- قفل برای فایل جدید
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

# --- توابع مربوط به اطلاعات پنل مرزبان ---
async def load_marzban_credentials() -> Dict[str, str]:
    return await _load_json_file(MARZBAN_CREDENTIALS_FILE)

async def save_marzban_credentials(credentials: Dict[str, str]) -> None:
    await _save_json_file(MARZBAN_CREDENTIALS_FILE, credentials)

# (بقیه توابع data_manager بدون تغییر باقی می‌مانند)
async def load_users_map() -> Dict[str, int]: return await _load_json_file(USERS_MAP_FILE)
async def save_users_map(users_map: Dict[str, int]) -> None: await _save_json_file(USERS_MAP_FILE, {normalize_username(k): v for k, v in users_map.items()})
async def load_template_config() -> Dict[str, Any]: return await _load_json_file(TEMPLATE_CONFIG_FILE)
async def save_template_config(config_data: Dict[str, Any]) -> None:
    if 'template_username' in config_data: config_data['template_username'] = normalize_username(config_data['template_username'])
    await _save_json_file(TEMPLATE_CONFIG_FILE, config_data)
async def load_reminders() -> Dict[str, str]: return await _load_json_file(REMINDERS_FILE)
async def save_reminders(reminders: Dict[str, str]) -> None: await _save_json_file(REMINDERS_FILE, {normalize_username(k): v for k, v in reminders.items()})
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
async def load_financials() -> Dict[str, str]: return await _load_json_file(FINANCIALS_FILE)
async def save_financials(financial_data: Dict[str, str]) -> None: await _save_json_file(FINANCIALS_FILE, financial_data)