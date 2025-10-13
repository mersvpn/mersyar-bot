# --- START OF FILE database/models/broadcast.py ---
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    JSON,
    TIMESTAMP,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from . import Base

if TYPE_CHECKING:
    from .user import User


class Broadcast(Base):
    __tablename__ = "broadcasts"

    broadcast_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    # Storing message content as JSON allows for complex messages (text, photo, keyboard, etc.)
    message_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationship to the User model (the admin who sent the broadcast)
    admin: Mapped["User"] = relationship(back_populates="broadcasts")

    def __repr__(self) -> str:
        return f"<Broadcast(id={self.broadcast_id}, admin_id={self.admin_id})>"

# --- END OF FILE database/models/broadcast.py ---