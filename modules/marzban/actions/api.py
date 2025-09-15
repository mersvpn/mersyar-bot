# FILE: modules/marzban/actions/api.py (نسخه نهایی با مکانیزم تلاش مجدد)

import httpx
import logging
import asyncio # <-- کتابخانه جدید برای ایجاد تاخیر
from typing import Tuple, Dict, Any, Optional, Union, List

from .data_manager import normalize_username

LOGGER = logging.getLogger(__name__)
_client = httpx.AsyncClient(timeout=20.0, http2=True)

_marzban_credentials: Dict[str, Any] = {}

async def init_marzban_credentials():
    """
    اطلاعات اتصال به مرزبان را از دیتابیس خوانده و در حافظه کش می‌کند.
    """
    from .data_manager import load_marzban_credentials as load_from_db
    global _marzban_credentials
    _marzban_credentials = await load_from_db()
    if _marzban_credentials:
        LOGGER.info("Marzban credentials loaded into memory.")
    else:
        LOGGER.warning("Marzban credentials could not be loaded from database.")

async def get_marzban_token() -> Optional[str]:
    """
    Gets an authentication token from the Marzban API.
    Retries up to 3 times on network errors.
    """
    if not _marzban_credentials:
        LOGGER.warning("Marzban API call failed: Credentials are not loaded.")
        return None

    base_url = _marzban_credentials.get("base_url")
    username = _marzban_credentials.get("username")
    password = _marzban_credentials.get("password")

    if not all([base_url, username, password]):
        LOGGER.warning("Marzban API call failed: Credential values are incomplete.")
        return None

    url = f"{base_url}/api/admin/token"
    payload = {'username': username, 'password': password}
    
    last_exception = None
    for attempt in range(3):
        try:
            response = await _client.post(url, data=payload)
            response.raise_for_status()
            return response.json().get("access_token")
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            last_exception = e
            LOGGER.warning(f"Attempt {attempt + 1}/3 to get Marzban token failed: {e}. Retrying in 1 second...")
            await asyncio.sleep(1)
            
    LOGGER.error(f"Failed to get Marzban token after 3 attempts. Last error: {last_exception}")
    return None

async def _api_request(method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Performs an API request to Marzban with authentication and retry logic.
    Retries up to 3 times for network-related errors or 5xx server errors.
    """
    token = await get_marzban_token()
    if not token:
        return {"error": "Authentication failed or credentials not set."}
    
    base_url = _marzban_credentials.get("base_url")
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {token}", **kwargs.pop('headers', {})}

    last_exception = None
    for attempt in range(3):
        try:
            response = await _client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {"success": True}

        except httpx.HTTPStatusError as e:
            if 500 <= e.response.status_code < 600:
                last_exception = e
                LOGGER.warning(f"API request to {url} failed with server error {e.response.status_code} (Attempt {attempt + 1}/3). Retrying...")
                await asyncio.sleep(attempt + 1)
                continue
            else:
                error_detail = "Unknown client error"
                try:
                    error_detail = e.response.json().get("detail", e.response.text)
                except Exception:
                    pass
                LOGGER.error(f"API request to {url} failed with client status {e.response.status_code}: {error_detail}")
                return {"error": error_detail, "status_code": e.response.status_code}

        except httpx.RequestError as e:
            last_exception = e
            LOGGER.warning(f"Network error on API request to {url} (Attempt {attempt + 1}/3): {e}. Retrying...")
            await asyncio.sleep(attempt + 1)
    
    LOGGER.error(f"API request to {url} failed after 3 attempts. Last error: {last_exception}")
    return {"error": "Network error or persistent server issue"}

async def get_all_users() -> Optional[List[Dict[str, Any]]]:
    response = await _api_request("GET", "/api/users", timeout=40.0)
    return response.get("users") if response and "error" not in response else None

async def get_user_data(username: str) -> Optional[Dict[str, Any]]:
    if not username: return None
    response = await _api_request("GET", f"/api/user/{username}")
    # --- FIX: Simplify error handling. Let _api_request handle logging. ---
    if response and "error" in response:
        return None
    return response

# FILE: modules/marzban/actions/api.py
# REPLACE ONLY THIS FUNCTION

async def modify_user_api(username: str, settings_to_change: dict) -> Tuple[bool, str]:
    current_data = await get_user_data(username)
    if not current_data or "error" in current_data:
        return False, f"User '{username}' not found or API error during fetch."
    
    # Clean up read-only or irrelevant fields from the payload
    for key in ['online_at', 'created_at', 'subscription_url', 'usages', 'error', 'status_code']:
        current_data.pop(key, None)
    
    # Ensure proxies dictionary is clean
    if 'proxies' in current_data and isinstance(current_data['proxies'], dict):
        current_data['proxies'] = {p: s for p, s in current_data['proxies'].items() if s}
        
    # V V V V V THE FINAL FIX IS HERE V V V V V
    # If the user's current status is not one of the valid writable statuses
    # (e.g., it's 'expired' or 'limited'), force it back to 'active'.
    # This ensures that adding days/data to an expired user reactivates them.
    valid_statuses = ['active', 'disabled', 'on_hold']
    if current_data.get('status') not in valid_statuses:
        current_data['status'] = 'active'
    # ^ ^ ^ ^ ^ THE FINAL FIX IS HERE ^ ^ ^ ^ ^

    # Merge the current data with the new settings
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

# ADD THIS FUNCTION BEFORE `close_client`

async def add_data_to_user_api(username: str, data_gb: int) -> Tuple[bool, str]:
    """
    Adds a specified amount of data (in GB) to a user's existing data_limit.
    """
    from .constants import GB_IN_BYTES
    
    # 1. Fetch the user's current data
    current_data = await get_user_data(username)
    if not current_data or "error" in current_data:
        return False, f"User '{username}' not found or API error during fetch."
        
    # 2. Calculate the new data limit
    current_limit_bytes = current_data.get('data_limit', 0)
    additional_bytes = data_gb * GB_IN_BYTES
    new_limit_bytes = current_limit_bytes + additional_bytes
    
    # 3. Prepare the payload for modification
    settings_to_change = {
        "data_limit": new_limit_bytes
    }
    
    # 4. Call the existing modify_user_api function
    success, message = await modify_user_api(username, settings_to_change)
    
    if success:
        return True, f"Successfully added {data_gb} GB to user '{username}'."
    else:
        return False, f"Failed to add data to user '{username}': {message}"

# ... (the rest of the file, starting with async def close_client():)

async def close_client():
    if not _client.is_closed:
        await _client.aclose()
        LOGGER.info("Shared HTTPX client has been closed.")