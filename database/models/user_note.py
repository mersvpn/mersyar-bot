# --- START OF FILE database/models/user_note.py ---
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Integer, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .marzban_link import MarzbanTelegramLink


class UserNote(Base):
    __tablename__ = "user_notes"

    username: Mapped[str] = mapped_column(String(255), primary_key=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subscription_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subscription_data_limit_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subscription_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_test_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Define the foreign key relationship to marzban_telegram_links
    # This assumes a one-to-one relationship from UserNote to MarzbanTelegramLink
    link: Mapped[Optional[MarzbanTelegramLink]] = relationship(
        "MarzbanTelegramLink",
        primaryjoin="foreign(UserNote.username) == MarzbanTelegramLink.marzban_username",
        backref="note",
        uselist=False
    )

    def __repr__(self) -> str:
        return f"<UserNote(username='{self.username}')>"

# --- END OF FILE database/models/user_note.py ---