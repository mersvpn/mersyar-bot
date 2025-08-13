# ===== IMPORTS & DEPENDENCIES =====
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Union

# ===== SETUP & CONSTANTS =====
LOGGER = logging.getLogger(__name__)

# --- CORRECTED: Use pathlib for robust, OS-agnostic path handling ---
# This finds the project root directory (where bot.py is) and builds paths from there.
try:
    # This works when the script is run directly.
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
except NameError:
    # Fallback for environments where __file__ is not defined (e.g., some interactive shells)
    PROJECT_ROOT = Path.cwd().resolve()

# --- Define absolute paths for all JSON files ---
DATA_DIR = PROJECT_ROOT
USERS_MAP_FILE = DATA_DIR / "users.json"
TEMPLATE_CONFIG_FILE = DATA_DIR / "template_config.json"
REMINDERS_FILE = DATA_DIR / "reminders.json"
NON_RENEWAL_FILE = DATA_DIR / "non_renewal_users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
BROADCASTS_FILE = DATA_DIR / "broadcasts.json"
FINANCIALS_FILE = DATA_DIR / "financials.json"

# --- Async Locks for Thread-Safe File Operations ---
# A dictionary to hold a lock for each file path.
_locks: Dict[Path, asyncio.Lock] = {
    file_path: asyncio.Lock() for file_path in [
        USERS_MAP_FILE,
        TEMPLATE_CONFIG_FILE,
        REMINDERS_FILE,
        NON_RENEWAL_FILE,
        SETTINGS_FILE,
        BROADCASTS_FILE,
        FINANCIALS_FILE,
    ]
}

# ===== CORE FILE OPERATIONS (ASYNCHRONOUS & SAFE) =====

async def _load_json_file(file_path: Path, is_list: bool = False) -> Union[Dict, List]:
    """
    Asynchronously and safely loads a JSON file.
    If the file doesn't exist or is corrupted, it creates a new empty one.
    """
    default_empty: Union[Dict, List] = [] if is_list else {}
    lock = _locks[file_path]

    async with lock:
        try:
            # Ensure the file exists before trying to read it.
            if not file_path.exists():
                file_path.write_text(json.dumps(default_empty), encoding='utf-8')
                return default_empty

            # Read the content
            content = file_path.read_text(encoding='utf-8')
            # Handle empty file case
            if not content:
                return default_empty

            return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            LOGGER.error(f"Error reading {file_path}, creating a new empty file. Error: {e}")
            # If any error occurs, create a clean file.
            file_path.write_text(json.dumps(default_empty), encoding='utf-8')
            return default_empty

async def _save_json_file(file_path: Path, data: Union[Dict, List]) -> None:
    """Asynchronously and safely saves data to a JSON file with pretty printing."""
    lock = _locks[file_path]
    async with lock:
        try:
            file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4),
                encoding='utf-8'
            )
        except IOError as e:
            LOGGER.error(f"Could not write to file {file_path}. Error: {e}", exc_info=True)


# ===== PUBLIC DATA ACCESSOR FUNCTIONS (NORMALIZED & ASYNC) =====
# These functions are the ONLY way other parts of the bot should interact with data files.

# --- User Normalization ---
def normalize_username(username: str) -> str:
    """Consistently converts usernames to lowercase to prevent case-sensitivity issues."""
    return username.lower()

# --- Users Data (users.json) ---
async def load_users_map() -> Dict[str, int]:
    return await _load_json_file(USERS_MAP_FILE)

async def save_users_map(users_map: Dict[str, int]) -> None:
    # Normalize all keys before saving to ensure data integrity.
    normalized_map = {normalize_username(k): v for k, v in users_map.items()}
    await _save_json_file(USERS_MAP_FILE, normalized_map)

# --- Template Config (template_config.json) ---
async def load_template_config() -> Dict[str, Any]:
    return await _load_json_file(TEMPLATE_CONFIG_FILE)

async def save_template_config(config_data: Dict[str, Any]) -> None:
    if 'template_username' in config_data:
        config_data['template_username'] = normalize_username(config_data['template_username'])
    await _save_json_file(TEMPLATE_CONFIG_FILE, config_data)

# --- Manual Reminders/Notes (reminders.json) ---
async def load_reminders() -> Dict[str, str]:
    return await _load_json_file(REMINDERS_FILE)

async def save_reminders(reminders: Dict[str, str]) -> None:
    normalized_reminders = {normalize_username(k): v for k, v in reminders.items()}
    await _save_json_file(REMINDERS_FILE, normalized_reminders)

# --- Non-renewal Users (non_renewal_users.json) ---
async def load_non_renewal_users() -> List[str]:
    return await _load_json_file(NON_RENEWAL_FILE, is_list=True)

async def save_non_renewal_users(users_list: List[str]) -> None:
    normalized_list = sorted(list(set(normalize_username(u) for u in users_list)))
    await _save_json_file(NON_RENEWAL_FILE, normalized_list)

# --- Bot Settings (settings.json) ---
async def load_settings() -> Dict[str, Any]:
    from modules.reminder.actions.constants import (
        DEFAULT_REMINDER_TIME_TEHRAN, DEFAULT_REMINDER_DAYS_THRESHOLD,
        DEFAULT_REMINDER_DATA_THRESHOLD_GB
    )
    settings = await _load_json_file(SETTINGS_FILE)
    # Ensure default values are present if the file is new or keys are missing.
    settings.setdefault('reminder_time', DEFAULT_REMINDER_TIME_TEHRAN)
    settings.setdefault('reminder_days', DEFAULT_REMINDER_DAYS_THRESHOLD)
    settings.setdefault('reminder_data_gb', DEFAULT_REMINDER_DATA_THRESHOLD_GB)
    return settings

async def save_settings(settings: Dict[str, Any]) -> None:
    await _save_json_file(SETTINGS_FILE, settings)

# --- Broadcasts (broadcasts.json) ---
async def load_broadcasts() -> Dict[str, Any]:
    return await _load_json_file(BROADCASTS_FILE)

async def save_broadcasts(broadcast_data: Dict[str, Any]) -> None:
    await _save_json_file(BROADCASTS_FILE, broadcast_data)

# --- Financials (financials.json) ---
async def load_financials() -> Dict[str, str]:
    return await _load_json_file(FINANCIALS_FILE)

async def save_financials(financial_data: Dict[str, str]) -> None:
    await _save_json_file(FINANCIALS_FILE, financial_data)


# ===== IMPORTS & DEPENDENCIES =====
import httpx
import logging
from typing import Tuple, Dict, Any, Optional, Union

# --- Local Imports ---
from config import config
from .data_manager import normalize_username

# --- Setup ---
LOGGER = logging.getLogger(__name__)

# --- Create a reusable httpx AsyncClient for performance and connection pooling ---
_client = httpx.AsyncClient(timeout=20.0, http2=True)

# ===== API ACTIONS (REWRITTEN WITH HTTPX & NORMALIZATION) =====

async def get_marzban_token() -> Optional[str]:
    """Fetches the Marzban access token using the shared httpx client."""
    url = f"{config.MARZBAN_BASE_URL}/api/admin/token"
    payload = {'username': config.MARZBAN_USERNAME, 'password': config.MARZBAN_PASSWORD}
    LOGGER.info(f"Requesting Marzban token from {url}")
    try:
        response = await _client.post(url, data=payload)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        token = response.json().get("access_token")
        LOGGER.info("Successfully obtained Marzban token.")
        return token
    except httpx.HTTPStatusError as e:
        LOGGER.error(f"HTTP Error while authenticating: {e.response.status_code} - {e.response.text}", exc_info=True)
    except httpx.RequestError as e:
        LOGGER.error(f"Network error while authenticating: {e}", exc_info=True)
    return None

async def get_all_users() -> Optional[List[Dict[str, Any]]]:
    """Fetches all users from the Marzban panel."""
    token = await get_marzban_token()
    if not token:
        return None
    url = f"{config.MARZBAN_BASE_URL}/api/users"
    headers = {"Authorization": f"Bearer {token}"}
    LOGGER.info("Requesting all users from Marzban panel.")
    try:
        response = await _client.get(url, headers=headers, timeout=40.0) # Longer timeout for potentially large lists
        response.raise_for_status()
        return response.json().get("users", [])
    except httpx.HTTPStatusError as e:
        LOGGER.error(f"HTTP error fetching all users: {e.response.status_code} - {e.response.text}", exc_info=True)
    except httpx.RequestError as e:
        LOGGER.error(f"Network error fetching all users: {e}", exc_info=True)
    return None

async def get_user_data(username: str) -> Optional[Dict[str, Any]]:
    """
    Fetches a single user's data. Normalizes username before the request.
    """
    if not username: return None
    normalized_user = normalize_username(username)

    token = await get_marzban_token()
    if not token: return None

    url = f"{config.MARZBAN_BASE_URL}/api/user/{normalized_user}"
    headers = {"Authorization": f"Bearer {token}"}
    LOGGER.info(f"Requesting user data for '{normalized_user}' from: {url}")
    try:
        response = await _client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        # It's common for this to fail with 404 if user not found, so log as info not error.
        if e.response.status_code == 404:
            LOGGER.info(f"User '{normalized_user}' not found in Marzban (404).")
        else:
            LOGGER.error(f"HTTP Error getting user '{normalized_user}': {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        LOGGER.error(f"Network error getting user '{normalized_user}': {e}", exc_info=True)
    return None

async def modify_user_api(username: str, settings_to_change: dict) -> Tuple[bool, str]:
    """Modifies a user. Normalizes username before the request."""
    normalized_user = normalize_username(username)
    token = await get_marzban_token()
    if not token: return False, "خطا در احراز هویت."

    current_data = await get_user_data(normalized_user)
    if not current_data: return False, f"کاربر «{normalized_user}» برای ویرایش یافت نشد."

    # Marzban API requires the full user object for modification.
    # We merge the changes into the current data.
    updated_payload = {**current_data, **settings_to_change}
    # Remove read-only fields that cause errors if sent back.
    for key in ['online_at', 'created_at', 'subscription_url', 'usages']:
        updated_payload.pop(key, None)

    url = f"{config.MARZBAN_BASE_URL}/api/user/{normalized_user}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = await _client.put(url, headers=headers, json=updated_payload)
        response.raise_for_status()
        return True, "کاربر با موفقیت به‌روزرسانی شد."
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", e.response.text)
        return False, f"خطا: {error_detail}"
    except httpx.RequestError:
        return False, "خطای شبکه در هنگام ویرایش کاربر."

async def delete_user_api(username: str) -> Tuple[bool, str]:
    """Deletes a user. Normalizes username before the request."""
    normalized_user = normalize_username(username)
    token = await get_marzban_token()
    if not token: return False, "خطا در احراز هویت."
    url = f"{config.MARZBAN_BASE_URL}/api/user/{normalized_user}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = await _client.delete(url, headers=headers)
        response.raise_for_status()
        return True, "کاربر با موفقیت حذف شد."
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", e.response.text)
        return False, f"خطا: {error_detail}"
    except httpx.RequestError:
        return False, "خطای شبکه در هنگام حذف کاربر."

async def create_user_api(payload: dict) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    """Creates a new user. Normalizes username within the payload."""
    if 'username' in payload:
        payload['username'] = normalize_username(payload['username'])

    token = await get_marzban_token()
    if not token: return False, "خطا در احراز هویت."
    url = f"{config.MARZBAN_BASE_URL}/api/user"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        response = await _client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True, response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", e.response.text)
        return False, f"خطا: {error_detail}"
    except httpx.RequestError:
        return False, "خطای شبکه در هنگام ساخت کاربر."

async def reset_user_traffic_api(username: str) -> Tuple[bool, str]:
    """Resets user traffic. Normalizes username before the request."""
    normalized_user = normalize_username(username)
    token = await get_marzban_token()
    if not token: return False, "خطا در احراز هویت."
    url = f"{config.MARZBAN_BASE_URL}/api/user/{normalized_user}/reset"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = await _client.post(url, headers=headers)
        response.raise_for_status()
        return True, "ترافیک کاربر با موفقیت صفر شد."
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", e.response.text)
        return False, f"خطا: {error_detail}"
    except httpx.RequestError:
        return False, "خطای شبکه در هنگام ریست ترافیک."

async def reset_subscription_url_api(username: str) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    """Resets the subscription URL. Normalizes username before the request."""
    normalized_user = normalize_username(username)
    token = await get_marzban_token()
    if not token: return False, "خطا در احراز هویت."
    url = f"{config.MARZBAN_BASE_URL}/api/user/{normalized_user}/revoke_sub"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = await _client.post(url, headers=headers)
        response.raise_for_status()
        return True, response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", e.response.text)
        return False, f"خطا: {error_detail}"
    except httpx.RequestError:
        return False, "خطای شبکه در هنگام بازسازی لینک."

async def close_client():
    """Closes the shared httpx client. Should be called on application shutdown."""
    if not _client.is_closed:
        await _client.aclose()
        LOGGER.info("Shared HTTPX client has been closed.")