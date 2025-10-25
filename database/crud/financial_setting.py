# --- START OF FILE database/crud/financial_setting.py ---
import logging
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.financial_setting import FinancialSetting

LOGGER = logging.getLogger(__name__)


async def load_financial_settings() -> Optional[FinancialSetting]:
    """Loads the single row of financial settings from the database."""
    async with get_session() as session:
        result = await session.execute(select(FinancialSetting).where(FinancialSetting.id == 1))
        return result.scalar_one_or_none()


async def save_financial_settings(settings_to_update: Dict[str, Any]) -> bool:
    """
    Safely updates settings in the financial_settings table.
    It reads the existing data, updates it with new values, and then commits.
    This prevents accidentally nullifying other fields.
    """
    async with get_session() as session:
        try:
            # Step 1: Get the existing settings object or create a new one
            db_settings = await session.get(FinancialSetting, 1)
            if not db_settings:
                db_settings = FinancialSetting(id=1)
                session.add(db_settings)

            # Step 2: Update the object with the new data
            for key, value in settings_to_update.items():
                if hasattr(db_settings, key):
                    setattr(db_settings, key, value)
            
            # Step 3: Commit the changes
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to save financial settings: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/financial_setting.py ---