# --- START OF FILE database/models/unlimited_plan.py ---
from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class UnlimitedPlan(Base):
    __tablename__ = "unlimited_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    max_ips: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<UnlimitedPlan(id={self.id}, name='{self.plan_name}', price={self.price})>"

# --- END OF FILE database/models/unlimited_plan.py ---