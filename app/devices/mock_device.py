import argparse
import json
import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from app.config import get_settings
from app.realtime import topics


logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publish_json(client: mqtt.Client, topic: str, payload: dict[str, Any]) -> None:
    client.publish(topic, json.dumps(payload), qos=0)
    logger.info("published %s %s", topic, payload)


def _ack_after_delay(client: mqtt.Client, device_id: str, command_id: str) -> None:
    time.sleep(1)
    _publish_json(
        client,
        topics.format_topic(topics.ACK_STATUS_TOPIC, device_id),
        {"command_id": command_id, "status": "done"},
    )


def _on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    device_id = userdata["device_id"]
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("ignoring malformed command on %s: %s", message.topic, exc)
        return

    command_id = payload.get("command_id")
    if not command_id:
        logger.warning("ignoring command without command_id on %s: %s", message.topic, payload)
        return

    logger.info("received command %s %s", message.topic, payload)
    threading.Thread(target=_ack_after_delay, args=(client, device_id, command_id), daemon=True).start()


def _battery_loop(client: mqtt.Client, device_id: str, stop_event: threading.Event) -> None:
    battery_percent = 100.0
    while not stop_event.wait(30):
        battery_percent = max(0.0, battery_percent - random.uniform(0.1, 0.8))
        _publish_json(
            client,
            topics.format_topic(topics.BATTERY_STATUS_TOPIC, device_id),
            {"percent": round(battery_percent, 2)},
        )


def _publish_sensor_event(client: mqtt.Client, device_id: str, key: str, mask_attached: bool) -> bool:
    now = _timestamp()
    if key == "t":
        _publish_json(
            client,
            topics.format_topic(topics.TOUCH_SENSOR_TOPIC, device_id),
            {"pressed": True, "timestamp": now},
        )
    elif key == "m":
        _publish_json(
            client,
            topics.format_topic(topics.MOTION_SENSOR_TOPIC, device_id),
            {"detected": True, "timestamp": now},
        )
    elif key == "l":
        _publish_json(
            client,
            topics.format_topic(topics.LIGHT_SENSOR_TOPIC, device_id),
            {"lux_level": round(random.uniform(5.0, 700.0), 2), "timestamp": now},
        )
    elif key == "k":
        mask_attached = not mask_attached
        _publish_json(
            client,
            topics.format_topic(topics.MASK_STATE_SENSOR_TOPIC, device_id),
            {"attached": mask_attached, "timestamp": now},
        )
    else:
        print("Press one of: [t]ouch [m]otion [l]ight [k]mask-toggle, or [q]uit")
    return mask_attached


def run(device_id: str) -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"rufus-mock-{device_id}",
        userdata={"device_id": device_id},
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.on_message = _on_message
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
    client.subscribe(
        [
            (topics.format_topic(topics.STUNT_COMMAND_TOPIC, device_id), 0),
            (topics.format_topic(topics.DISPLAY_COMMAND_TOPIC, device_id), 0),
        ]
    )
    client.loop_start()

    stop_event = threading.Event()
    threading.Thread(target=_battery_loop, args=(client, device_id, stop_event), daemon=True).start()

    mask_attached = False
    print("Mock Rufus connected.")
    print("Press: [t]ouch [m]otion [l]ight [k]mask-toggle, then Enter. Press [q] to quit.")
    try:
        while True:
            key = input("> ").strip().lower()
            if key == "q":
                break
            mask_attached = _publish_sensor_event(client, device_id, key, mask_attached)
    finally:
        stop_event.set()
        client.loop_stop()
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a mock Rufus ESP32 device over MQTT.")
    parser.add_argument("--device-id", default="mock-rufus-001")
    args = parser.parse_args()
    run(args.device_id)


if __name__ == "__main__":
    main()
