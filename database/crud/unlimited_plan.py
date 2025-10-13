# --- START OF FILE database/crud/unlimited_plan.py ---
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.unlimited_plan import UnlimitedPlan

LOGGER = logging.getLogger(__name__)


async def get_all_unlimited_plans() -> List[UnlimitedPlan]:
    """Retrieves all unlimited plans, sorted by their sort_order."""
    async with get_session() as session:
        stmt = select(UnlimitedPlan).order_by(UnlimitedPlan.sort_order.asc(), UnlimitedPlan.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_active_unlimited_plans() -> List[UnlimitedPlan]:
    """Retrieves only the active unlimited plans for customer view."""
    async with get_session() as session:
        stmt = (
            select(UnlimitedPlan)
            .where(UnlimitedPlan.is_active == True)
            .order_by(UnlimitedPlan.sort_order.asc(), UnlimitedPlan.id.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_unlimited_plan_by_id(plan_id: int) -> Optional[UnlimitedPlan]:
    """Retrieves a single unlimited plan by its primary key."""
    async with get_session() as session:
        return await session.get(UnlimitedPlan, plan_id)


async def add_unlimited_plan(plan_data: Dict[str, Any]) -> Optional[UnlimitedPlan]:
    """Adds a new unlimited plan to the database."""
    async with get_session() as session:
        try:
            new_plan = UnlimitedPlan(**plan_data)
            session.add(new_plan)
            await session.commit()
            await session.refresh(new_plan)
            return new_plan
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to add unlimited plan: {e}", exc_info=True)
            return None


async def update_unlimited_plan(plan_id: int, update_data: Dict[str, Any]) -> bool:
    """Updates an existing unlimited plan."""
    async with get_session() as session:
        try:
            stmt = update(UnlimitedPlan).where(UnlimitedPlan.id == plan_id).values(**update_data)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to update unlimited plan {plan_id}: {e}", exc_info=True)
            return False


async def delete_unlimited_plan(plan_id: int) -> bool:
    """Deletes an unlimited plan from the database."""
    async with get_session() as session:
        try:
            stmt = delete(UnlimitedPlan).where(UnlimitedPlan.id == plan_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to delete unlimited plan {plan_id}: {e}", exc_info=True)
            return False

# --- END OF FILE database/crud/unlimited_plan.py ---