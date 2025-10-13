# --- START OF FILE database/crud/marzban_credential.py ---
import logging
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from ..engine import get_session
from ..models.marzban_credential import MarzbanCredential

LOGGER = logging.getLogger(__name__)


async def load_marzban_credentials() -> Optional[MarzbanCredential]:
    """Loads the single row of marzban credentials from the database."""
    async with get_session() as session:
        result = await session.execute(select(MarzbanCredential).where(MarzbanCredential.id == 1))
        return result.scalar_one_or_none()


async def save_marzban_credentials(credentials_data: Dict[str, Any]) -> bool:
    """
    Saves or updates the marzban credentials in the marzban_credentials table.
    This table is expected to have only one row with id=1.
    """
    if 'id' not in credentials_data:
        credentials_data['id'] = 1
        
    stmt = mysql_insert(MarzbanCredential).values(credentials_data)
    
    update_dict = {
        col.name: col
        for col in stmt.inserted
        if col.name != 'id'
    }
    
    update_stmt = stmt.on_duplicate_key_update(**update_dict)
    
    async with get_session() as session:
        try:
            await session.execute(update_stmt)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to save Marzban credentials: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/marzban_credential.py ---