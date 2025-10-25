# --- START OF FILE database/models/bot_setting.py ---
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class BotSetting(Base):
    __tablename__ = "bot_settings"

    setting_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    setting_value: Mapped[str] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BotSetting(key='{self.setting_key}', value='{self.setting_value[:20]}...')>"

# --- END OF FILE database/models/bot_setting.py ---