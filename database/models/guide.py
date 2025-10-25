# --- START OF FILE database/models/guide.py ---
from typing import Optional, List, Dict

from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Guide(Base):
    __tablename__ = "guides"

    guide_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    buttons: Mapped[Optional[List[Dict[str, str]]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Guide(key='{self.guide_key}', title='{self.title}')>"

# --- END OF FILE database/models/guide.py ---