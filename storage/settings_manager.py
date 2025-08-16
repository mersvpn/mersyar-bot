import json
import asyncio
from pathlib import Path

# --- Path Configuration ---
try:
    PROJECT_ROOT = Path(__file__).parent.parent.resolve()
except NameError:
    PROJECT_ROOT = Path.cwd().resolve()

STATUS_FILE = PROJECT_ROOT / "bot_status.json"
_lock = asyncio.Lock()

# --- Helper Functions ---

async def _get_default_data():
    return {"is_bot_active": True, "maintenance_message": "ربات در حال حاضر در دست تعمیر است. لطفاً بعداً تلاش کنید."}

async def _load_status_data() -> dict:
    async with _lock:
        if not STATUS_FILE.exists():
            return await _get_default_data()
        try:
            content = STATUS_FILE.read_text(encoding='utf-8')
            if not content:
                return await _get_default_data()
            return json.loads(content)
        except (json.JSONDecodeError, IOError):
            return await _get_default_data()

async def _save_status_data(data: dict) -> None:
    async with _lock:
        STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')

# --- Public API for Bot Settings ---

async def is_bot_active() -> bool:
    data = await _load_status_data()
    return data.get("is_bot_active", True)

async def set_bot_status(is_active: bool) -> None:
    data = await _load_status_data()
    data["is_bot_active"] = is_active
    await _save_status_data(data)

async def get_maintenance_message() -> str:
    data = await _load_status_data()
    return data.get("maintenance_message", "ربات در حال حاضر در دست تعمیر است. لطفاً بعداً تلاش کنید.")