# --- START OF FILE database/models/bot_managed_user.py ---
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class BotManagedUser(Base):
    __tablename__ = "bot_managed_users"

    marzban_username: Mapped[str] = mapped_column(String(255), primary_key=True)

    def __repr__(self) -> str:
        return f"<BotManagedUser(username='{self.marzban_username}')>"

# --- END OF FILE database/models/bot_managed_user.py ---