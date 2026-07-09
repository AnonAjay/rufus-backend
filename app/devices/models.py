from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeviceEvent:
    device_id: str
    event_type: str
    payload: dict[str, Any]


# TODO(device-service-branch): Replace these dataclasses with persisted device
# state and command acknowledgement models once the MQTT contract is finalized.
