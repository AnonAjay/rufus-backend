import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import paho.mqtt.client as mqtt

from app.config import get_settings
from app.db.session import SessionLocal
from app.devices.models import Device
from app.realtime import topics


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MqttDeviceEvent:
    device_id: str
    topic: str
    event_type: str
    payload: dict[str, Any]
    received_at: datetime


event_queue: asyncio.Queue[MqttDeviceEvent] = asyncio.Queue()
_client: Optional[mqtt.Client] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def _extract_device_id(topic: str) -> Optional[str]:
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "rufus":
        return None
    return parts[1]


def _event_type_from_topic(topic: str) -> str:
    parts = topic.split("/")
    if len(parts) < 4:
        return "unknown"
    return "/".join(parts[2:])


def _queue_event(event: MqttDeviceEvent) -> None:
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(event_queue.put_nowait, event)
    else:
        event_queue.put_nowait(event)


def _mark_device_seen(device_id: str, topic: str, payload: dict[str, Any]) -> None:
    with SessionLocal() as db:
        device = db.get(Device, device_id)
        if device is None:
            return

        device.last_seen = datetime.now(timezone.utc)
        if topic.endswith("/status/battery"):
            percent = payload.get("percent")
            if percent is not None:
                device.battery_percent = float(percent)
        db.commit()


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
    logger.info("MQTT backend connected: reason_code=%s", reason_code)
    client.subscribe(
        [
            (topics.SENSOR_TOPIC_FILTER, 0),
            (topics.ACK_STATUS_TOPIC_FILTER, 0),
            (topics.BATTERY_STATUS_TOPIC_FILTER, 0),
        ]
    )


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring malformed MQTT payload on %s: %s", message.topic, exc)
        return

    device_id = _extract_device_id(message.topic)
    if device_id is None:
        logger.warning("Ignoring MQTT message on unexpected topic: %s", message.topic)
        return

    event = MqttDeviceEvent(
        device_id=device_id,
        topic=message.topic,
        event_type=_event_type_from_topic(message.topic),
        payload=payload,
        received_at=datetime.now(timezone.utc),
    )
    logger.info("MQTT event received: device_id=%s topic=%s payload=%s", device_id, message.topic, payload)
    _mark_device_seen(device_id, message.topic, payload)
    _queue_event(event)


def connect_mqtt() -> mqtt.Client:
    global _client, _loop

    settings = get_settings()
    try:
        _loop = asyncio.get_running_loop()
    except RuntimeError:
        _loop = None

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rufus-backend")
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    client.loop_start()
    _client = client
    return client


def disconnect_mqtt() -> None:
    global _client
    if _client is None:
        return
    _client.loop_stop()
    _client.disconnect()
    _client = None


def publish(topic: str, payload: dict[str, Any]) -> None:
    if _client is None:
        raise RuntimeError("MQTT client is not connected")
    _client.publish(topic, json.dumps(payload), qos=0)


def publish_stunt_command(device_id: str, command_id: str, stunt_name: str) -> None:
    publish(
        topics.format_topic(topics.STUNT_COMMAND_TOPIC, device_id),
        {"command_id": command_id, "stunt_name": stunt_name},
    )


def publish_display_command(device_id: str, command_id: str, mode: str, content: str) -> None:
    publish(
        topics.format_topic(topics.DISPLAY_COMMAND_TOPIC, device_id),
        {"command_id": command_id, "mode": mode, "content": content},
    )


def get_event_queue() -> asyncio.Queue[MqttDeviceEvent]:
    return event_queue
