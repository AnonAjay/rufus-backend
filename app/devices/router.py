from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.devices.models import Device


router = APIRouter(prefix="/devices", tags=["devices"])
ONLINE_WINDOW_SECONDS = 60
DEV_OWNER_USER_ID = "local-dev"


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class DeviceResponse(BaseModel):
    id: str
    name: str
    owner_user_id: str
    last_seen: Optional[datetime]
    battery_percent: Optional[float]


class DeviceStatusResponse(BaseModel):
    device_id: str
    name: str
    online: bool
    last_seen: Optional[datetime]
    battery_percent: Optional[float]


def _is_online(last_seen: Optional[datetime]) -> bool:
    if last_seen is None:
        return False
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - last_seen).total_seconds()
    return age_seconds <= ONLINE_WINDOW_SECONDS


@router.post("/register", response_model=DeviceResponse)
async def register_device(request: DeviceRegisterRequest, db: Session = Depends(get_db)) -> Device:
    device = db.get(Device, request.device_id)
    if device is None:
        device = Device(
            id=request.device_id,
            name=request.name,
            owner_user_id=DEV_OWNER_USER_ID,
            last_seen=None,
            battery_percent=None,
        )
        db.add(device)
    else:
        device.name = request.name

    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
async def device_status(device_id: str, db: Session = Depends(get_db)) -> DeviceStatusResponse:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not registered")

    return DeviceStatusResponse(
        device_id=device.id,
        name=device.name,
        online=_is_online(device.last_seen),
        last_seen=device.last_seen,
        battery_percent=device.battery_percent,
    )
