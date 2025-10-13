# --- START OF FILE database/models/template_config.py ---
from sqlalchemy import Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class TemplateConfig(Base):
    __tablename__ = "template_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    template_username: Mapped[str] = mapped_column(String(255), nullable=False)
    proxies: Mapped[dict] = mapped_column(JSON, nullable=True)
    inbounds: Mapped[dict] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<TemplateConfig(username='{self.template_username}')>"

# --- END OF FILE database/models/template_config.py ---