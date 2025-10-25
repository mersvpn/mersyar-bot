# --- START OF FILE database/crud/volumetric_tier.py ---
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.volumetric_tier import VolumetricTier

LOGGER = logging.getLogger(__name__)


async def get_all_pricing_tiers() -> List[VolumetricTier]:
    """Retrieves all pricing tiers, sorted by their volume limit."""
    async with get_session() as session:
        stmt = select(VolumetricTier).order_by(VolumetricTier.volume_limit_gb.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_pricing_tier_by_id(tier_id: int) -> Optional[VolumetricTier]:
    """Retrieves a single pricing tier by its primary key."""
    async with get_session() as session:
        return await session.get(VolumetricTier, tier_id)


async def add_pricing_tier(tier_data: Dict[str, Any]) -> Optional[VolumetricTier]:
    """Adds a new pricing tier to the database."""
    async with get_session() as session:
        try:
            new_tier = VolumetricTier(**tier_data)
            session.add(new_tier)
            await session.commit()
            await session.refresh(new_tier)
            return new_tier
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to add pricing tier: {e}", exc_info=True)
            return None


async def update_pricing_tier(tier_id: int, update_data: Dict[str, Any]) -> bool:
    """Updates an existing pricing tier."""
    async with get_session() as session:
        try:
            stmt = update(VolumetricTier).where(VolumetricTier.id == tier_id).values(**update_data)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to update pricing tier {tier_id}: {e}", exc_info=True)
            return False


async def delete_pricing_tier(tier_id: int) -> bool:
    """Deletes a pricing tier from the database."""
    async with get_session() as session:
        try:
            stmt = delete(VolumetricTier).where(VolumetricTier.id == tier_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to delete pricing tier {tier_id}: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/volumetric_tier.py ---