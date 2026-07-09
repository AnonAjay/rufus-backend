from fastapi import APIRouter


router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/status")
async def device_status() -> dict[str, str]:
    # TODO(device-service-branch): Return MQTT-backed device presence, firmware,
    # battery, and last sensor event once the device service is implemented.
    return {"status": "unknown"}
