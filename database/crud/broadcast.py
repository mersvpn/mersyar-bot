# --- START OF FILE database/crud/broadcast.py ---
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.broadcast import Broadcast

LOGGER = logging.getLogger(__name__)


async def log_broadcast(
    admin_id: int,
    message_content: dict,
    success_count: int,
    failure_count: int
) -> Optional[Broadcast]:
    """Logs a completed broadcast message to the database."""
    async with get_session() as session:
        try:
            new_broadcast = Broadcast(
                admin_id=admin_id,
                message_content=message_content,
                success_count=success_count,
                failure_count=failure_count
            )
            session.add(new_broadcast)
            await session.commit()
            await session.refresh(new_broadcast)
            return new_broadcast
        except Exception as e:
            LOGGER.error(f"Could not log broadcast for admin {admin_id}: {e}", exc_info=True)
            return None

# --- END OF FILE database/crud/broadcast.py ---