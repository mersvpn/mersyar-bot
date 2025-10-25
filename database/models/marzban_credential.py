# --- START OF FILE database/models/marzban_credential.py ---
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class MarzbanCredential(Base):
    __tablename__ = "marzban_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<MarzbanCredential(base_url='{self.base_url}')>"

# --- END OF FILE database/models/marzban_credential.py ---