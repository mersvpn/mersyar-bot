# ===== IMPORTS & DEPENDENCIES =====
import httpx
import logging
from typing import Tuple, Dict, Any, Optional, Union, List

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
        # Use a longer timeout for this request as it can be slow with many users
        response = await _client.get(url, headers=headers, timeout=40.0)
        response.raise_for_status()
        return response.json().get("users", [])
    except httpx.HTTPStatusError as e:
        LOGGER.error(f"HTTP error fetching all users: {e.response.status_code} - {e.response.text}", exc_info=True)
    except httpx.RequestError as e:
        LOGGER.error(f"Network error fetching all users: {e}", exc_info=True)
    return None

async def get_user_data(username: str) -> Optional[Dict[str, Any]]:
    """Fetches a single user's data. Normalizes username before the request."""
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

    updated_payload = {**current_data, **settings_to_change}
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