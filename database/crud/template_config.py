# --- START OF FILE database/crud/template_config.py ---
import logging
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from ..engine import get_session
from ..models.template_config import TemplateConfig

LOGGER = logging.getLogger(__name__)


async def load_template_config() -> Optional[TemplateConfig]:
    """Loads the single row of template config from the database."""
    async with get_session() as session:
        result = await session.execute(select(TemplateConfig).where(TemplateConfig.id == 1))
        return result.scalar_one_or_none()


async def save_template_config(config_data: Dict[str, Any]) -> bool:
    """
    Saves or updates the template config in the template_config table.
    This table is expected to have only one row with id=1.
    """
    if 'id' not in config_data:
        config_data['id'] = 1
        
    stmt = mysql_insert(TemplateConfig).values(config_data)
    
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
            LOGGER.error(f"Failed to save template config: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/template_config.py ---