# FILE: modules/marzban/actions/api.py (نسخه نهایی با کش کردن اطلاعات)

import httpx
import logging
from typing import Tuple, Dict, Any, Optional, Union, List

from .data_manager import normalize_username
# تابع load_marzban_credentials دیگر به صورت مستقیم استفاده نمی‌شود

LOGGER = logging.getLogger(__name__)
_client = httpx.AsyncClient(timeout=20.0, http2=True)

# --- متغیر سراسری برای کش کردن اطلاعات اتصال ---
_marzban_credentials: Dict[str, Any] = {}

async def init_marzban_credentials():
    """
    اطلاعات اتصال به مرزبان را از دیتابیس خوانده و در حافظه کش می‌کند.
    این تابع باید در هنگام استارت ربات فراخوانی شود.
    """
    from .data_manager import load_marzban_credentials as load_from_db
    global _marzban_credentials
    _marzban_credentials = await load_from_db()
    if _marzban_credentials:
        LOGGER.info("Marzban credentials loaded into memory.")
    else:
        LOGGER.warning("Marzban credentials could not be loaded from database.")

async def get_marzban_token() -> Optional[str]:
    # حالا از متغیر کش شده استفاده می‌کنیم
    if not _marzban_credentials:
        LOGGER.warning("Marzban API call failed: Credentials are not loaded into the bot.")
        return None

    base_url = _marzban_credentials.get("base_url")
    username = _marzban_credentials.get("username")
    password = _marzban_credentials.get("password")

    if not all([base_url, username, password]):
        LOGGER.warning("Marzban API call failed: Credentials values are incomplete.")
        return None

    url = f"{base_url}/api/admin/token"
    payload = {'username': username, 'password': password}
    try:
        response = await _client.post(url, data=payload)
        response.raise_for_status()
        return response.json().get("access_token")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        LOGGER.error(f"Failed to get Marzban token: {e}")
        return None

async def _api_request(method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
    token = await get_marzban_token()
    if not token:
        return {"error": "Authentication failed or credentials not set."}
    
    base_url = _marzban_credentials.get("base_url")
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {token}", **kwargs.pop('headers', {})}

    try:
        response = await _client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {"success": True}
    except httpx.HTTPStatusError as e:
        error_detail = "Unknown error"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except Exception:
            pass
        LOGGER.error(f"API request to {url} failed with status {e.response.status_code}: {error_detail}")
        return {"error": error_detail, "status_code": e.response.status_code}
    except httpx.RequestError as e:
        LOGGER.error(f"Network error on API request to {url}: {e}")
        return {"error": "Network error"}

# بقیه توابع بدون تغییر باقی می‌مانند و از _api_request اصلاح شده استفاده می‌کنند
async def get_all_users() -> Optional[List[Dict[str, Any]]]:
    response = await _api_request("GET", "/api/users", timeout=40.0)
    return response.get("users") if response and "error" not in response else None

async def get_user_data(username: str) -> Optional[Dict[str, Any]]:
    if not username: return None
    response = await _api_request("GET", f"/api/user/{username}")
    if response and "error" in response and response.get("status_code") == 404:
        return None 
    if response and "error" in response:
        return None
    return response

async def modify_user_api(username: str, settings_to_change: dict) -> Tuple[bool, str]:
    current_data = await get_user_data(username)
    if not current_data or "error" in current_data:
        return False, f"User '{username}' not found or API error during fetch."
    for key in ['online_at', 'created_at', 'subscription_url', 'usages', 'error', 'status_code']:
        current_data.pop(key, None)
    if 'proxies' in current_data and isinstance(current_data['proxies'], dict):
        current_data['proxies'] = {p: s for p, s in current_data['proxies'].items() if s}
    current_data['status'] = 'active'
    updated_payload = {**current_data, **settings_to_change}
    response = await _api_request("PUT", f"/api/user/{username}", json=updated_payload)
    if response and "error" not in response:
        return True, "User updated successfully."
    return False, response.get("error", "Unknown error") if response else "Network error"

async def delete_user_api(username: str) -> Tuple[bool, str]:
    response = await _api_request("DELETE", f"/api/user/{username}")
    if response and "error" not in response:
        return True, "User deleted successfully."
    return False, response.get("error", "Unknown error") if response else "Network error"

async def create_user_api(payload: dict) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    if 'username' in payload: payload['username'] = normalize_username(payload['username'])
    response = await _api_request("POST", "/api/user", json=payload)
    if response and "error" not in response:
        return True, response
    return False, response.get("error", "Unknown error") if response else "Network error"

async def reset_user_traffic_api(username: str) -> Tuple[bool, str]:
    response = await _api_request("POST", f"/api/user/{username}/reset")
    if response and "error" not in response:
        return True, "Traffic reset successfully."
    return False, response.get("error", "Unknown error") if response else "Network error"

async def reset_subscription_url_api(username: str) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    normalized_user = normalize_username(username)
    response = await _api_request("POST", f"/api/user/{normalized_user}/revoke_sub")
    if response and "error" not in response:
        return True, response
    return False, response.get("error", "Unknown error") if response else "Network error"

async def close_client():
    if not _client.is_closed:
        await _client.aclose()
        LOGGER.info("Shared HTTPX client has been closed.")