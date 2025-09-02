# FILE: modules/marzban/actions/data_manager.py
# (نسخه نهایی و هماهنگ با DictCursor)

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Union

from database import db_manager

LOGGER = logging.getLogger(__name__)

# --- FILE-BASED STORAGE (for settings that are okay to be in files) ---
# This section remains for non-database related temporary storage or logs
# ... (your existing _load_json_file and _save_json_file functions can remain here) ...

def normalize_username(username: str) -> str:
    return username.lower()

# --- DATABASE-BASED STORAGE FUNCTIONS (ALL ARE NOW DictCursor-COMPATIBLE) ---

async def load_marzban_credentials() -> Dict[str, str]:
    query = "SELECT base_url, username, password FROM marzban_credentials WHERE id = 1;"
    result = await db_manager.execute_query(query, fetch='one')
    # Use .get() for safe access in case a column is unexpectedly missing
    return {
        "base_url": result.get("base_url"),
        "username": result.get("username"),
        "password": result.get("password")
    } if result else {}

async def save_marzban_credentials(credentials: Dict[str, str]) -> bool:
    query = "INSERT INTO marzban_credentials (id, base_url, username, password) VALUES (1, %s, %s, %s) ON DUPLICATE KEY UPDATE base_url = VALUES(base_url), username = VALUES(username), password = VALUES(password);"
    args = (credentials.get("base_url"), credentials.get("username"), credentials.get("password"))
    return await db_manager.execute_query(query, args)

async def load_financials() -> Dict[str, str]:
    query = "SELECT card_number, card_holder FROM financial_settings WHERE id = 1;"
    result = await db_manager.execute_query(query, fetch='one')
    return {
        "card_number": result.get("card_number") or "",
        "card_holder": result.get("card_holder") or ""
    } if result else {"card_number": "", "card_holder": ""}

async def save_financials(financial_data: Dict[str, str]) -> bool:
    query = "INSERT INTO financial_settings (id, card_number, card_holder) VALUES (1, %s, %s) ON DUPLICATE KEY UPDATE card_number = VALUES(card_number), card_holder = VALUES(card_holder);"
    args = (financial_data.get("card_number"), financial_data.get("card_holder"))
    return await db_manager.execute_query(query, args)

async def load_reminders() -> Dict[str, str]:
    query = "SELECT username, note FROM user_notes;"
    results = await db_manager.execute_query(query, fetch='all')
    return {row['username']: row['note'] for row in results} if results else {}

async def save_reminders(reminders: Dict[str, str]) -> bool:
    # This function is complex and might need a better implementation, but let's fix it for now.
    # A better approach would be to update rows individually.
    delete_query = "UPDATE user_notes SET note = NULL;" # Clear old text notes without deleting rows
    if not await db_manager.execute_query(delete_query): return False
    if not reminders: return True
    
    update_query = "UPDATE user_notes SET note = %s WHERE username = %s;"
    success = True
    for username, note in reminders.items():
        if not await db_manager.execute_query(update_query, (note, username)):
            success = False
    return success

async def load_users_map() -> Dict[str, int]:
    query = "SELECT marzban_username, telegram_user_id FROM marzban_telegram_links;"
    results = await db_manager.execute_query(query, fetch='all')
    return {row['marzban_username']: row['telegram_user_id'] for row in results} if results else {}

async def link_user_to_telegram(marzban_username: str, telegram_user_id: int) -> bool:
    # This is already a database-native function, just ensuring it's here.
    return await db_manager.link_user_to_telegram(normalize_username(marzban_username), telegram_user_id)

# --- TEMPLATE CONFIG: Now from database ---
async def load_template_config() -> Dict[str, Any]:
    return await db_manager.load_template_config_db()

async def save_template_config(config_data: Dict[str, Any]) -> bool:
    if 'template_username' in config_data:
        config_data['template_username'] = normalize_username(config_data['template_username'])
    return await db_manager.save_template_config_db(config_data)

# --- FILE-BASED functions that are still needed (if any) ---
# We keep these for non-critical data or for features not yet migrated to DB
# ... (your load/save_non_renewal_users, load/save_settings, etc. can remain if you still use them) ...