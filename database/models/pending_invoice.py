from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    String,
    TIMESTAMP,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from . import Base

if TYPE_CHECKING:
    from .user import User


class PendingInvoice(Base):
    __tablename__ = "pending_invoices"

    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    plan_details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # --- ✨ NEW COLUMN ADDED ✨ ---
    from_wallet_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # --- --------------------- ---

    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )

    # Relationship to the User model
    user: Mapped["User"] = relationship(back_populates="pending_invoices")

    def __repr__(self) -> str:
        return f"<PendingInvoice(id={self.invoice_id}, user_id={self.user_id}, price={self.price})>"