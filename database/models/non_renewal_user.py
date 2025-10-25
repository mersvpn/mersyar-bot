# --- START OF FILE database/models/non_renewal_user.py ---
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class NonRenewalUser(Base):
    __tablename__ = "non_renewal_users"

    marzban_username: Mapped[str] = mapped_column(String(255), primary_key=True)

    def __repr__(self) -> str:
        return f"<NonRenewalUser(username='{self.marzban_username}')>"

# --- END OF FILE database/models/non_renewal_user.py ---