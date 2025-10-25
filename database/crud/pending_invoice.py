# --- START OF FILE database/crud/pending_invoice.py ---
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import get_session
from ..models.pending_invoice import PendingInvoice

LOGGER = logging.getLogger(__name__)


async def create_pending_invoice(invoice_data: Dict[str, Any]) -> Optional[PendingInvoice]:
    """Creates a new pending invoice in the database."""
    async with get_session() as session:
        try:
            new_invoice = PendingInvoice(**invoice_data)
            session.add(new_invoice)
            await session.commit()
            await session.refresh(new_invoice)
            return new_invoice
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to create pending invoice: {e}", exc_info=True)
            return None


async def get_pending_invoice_by_id(invoice_id: int) -> Optional[PendingInvoice]:
    """Retrieves a single pending invoice by its primary key."""
    async with get_session() as session:
        return await session.get(PendingInvoice, invoice_id)


async def get_pending_invoices_for_user(user_id: int) -> List[PendingInvoice]:
    """Retrieves all 'pending' invoices for a specific user."""
    async with get_session() as session:
        stmt = (
            select(PendingInvoice)
            .where(PendingInvoice.user_id == user_id, PendingInvoice.status == 'pending')
            .order_by(PendingInvoice.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def update_invoice_status(invoice_id: int, status: str) -> bool:
    """Updates the status of a specific invoice."""
    async with get_session() as session:
        try:
            stmt = update(PendingInvoice).where(PendingInvoice.invoice_id == invoice_id).values(status=status)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to update status for invoice {invoice_id}: {e}", exc_info=True)
            return False


async def expire_old_pending_invoices() -> int:
    """Updates the status of old pending invoices to 'expired'."""
    async with get_session() as session:
        try:
            expiration_time = datetime.utcnow() - timedelta(hours=24)
            stmt = (
                update(PendingInvoice)
                .where(PendingInvoice.status == 'pending', PendingInvoice.created_at < expiration_time)
                .values(status='expired')
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
        except Exception as e:
            await session.rollback()
            LOGGER.error(f"Failed to expire old pending invoices: {e}", exc_info=True)
            return 0

# --- END OF FILE database/crud/pending_invoice.py ---