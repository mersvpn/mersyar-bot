# --- START OF FILE database/models/financial_setting.py ---
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class FinancialSetting(Base):
    __tablename__ = "financial_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    card_number: Mapped[str] = mapped_column(String(255), nullable=True)
    card_holder: Mapped[str] = mapped_column(String(255), nullable=True)
    price_per_gb: Mapped[int] = mapped_column(Integer, nullable=True)
    price_per_day: Mapped[int] = mapped_column(Integer, nullable=True)
    base_daily_price: Mapped[int] = mapped_column(Integer, nullable=True, default=1000)

    def __repr__(self) -> str:
        return f"<FinancialSetting(id={self.id})>"

# --- END OF FILE database/models/financial_setting.py ---