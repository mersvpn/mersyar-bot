# --- START OF FILE database/models/volumetric_tier.py ---
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class VolumetricTier(Base):
    __tablename__ = "volumetric_pricing_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    volume_limit_gb: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    price_per_gb: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<VolumetricTier(id={self.id}, limit_gb={self.volume_limit_gb}, price={self.price_per_gb})>"

# --- END OF FILE database/models/volumetric_tier.py ---