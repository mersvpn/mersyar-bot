# --- START OF FILE database/models/admin_daily_note.py ---
from datetime import datetime

from sqlalchemy import String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


from . import Base


class AdminDailyNote(Base):
    __tablename__ = "admin_daily_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AdminDailyNote(id='{self.id}', title='{self.title}')>"

# --- END OF FILE database/models/admin_daily_note.py ---