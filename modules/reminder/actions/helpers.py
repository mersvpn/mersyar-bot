# ===== IMPORTS & DEPENDENCIES =====
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from .constants import (
    SETTINGS_FILE, DEFAULT_REMINDER_TIME_TEHRAN,
    DEFAULT_REMINDER_DAYS_THRESHOLD, DEFAULT_REMINDER_DATA_THRESHOLD_GB
)

# ===== HELPER FUNCTIONS =====
def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}
    
    settings.setdefault('reminder_time', DEFAULT_REMINDER_TIME_TEHRAN)
    settings.setdefault('reminder_days', DEFAULT_REMINDER_DAYS_THRESHOLD)
    settings.setdefault('reminder_data_gb', DEFAULT_REMINDER_DATA_THRESHOLD_GB)
    save_settings(settings) # Save back to create file or add missing keys
    return settings

def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def build_settings_keyboard() -> InlineKeyboardMarkup:
    settings = load_settings()
    time_button = InlineKeyboardButton(f"⏰ ساعت اعلان: {settings['reminder_time']}", callback_data="set_time")
    days_button = InlineKeyboardButton(f"⏳ آستانه روز: {settings['reminder_days']} روز", callback_data="set_days")
    data_button = InlineKeyboardButton(f"📉 آستانه حجم: {settings['reminder_data_gb']} گیگابایت", callback_data="set_data")
    back_button = InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main_from_settings")
    
    return InlineKeyboardMarkup([
        [time_button],
        [days_button],
        [data_button],
        [back_button]
    ])