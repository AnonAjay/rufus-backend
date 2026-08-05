from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    battery_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


@dataclass(frozen=True)
class DeviceEvent:
    device_id: str
    event_type: str
    payload: dict[str, Any]
