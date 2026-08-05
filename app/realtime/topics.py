TOUCH_SENSOR_TOPIC = "rufus/{device_id}/sensors/touch"
MOTION_SENSOR_TOPIC = "rufus/{device_id}/sensors/motion"
LIGHT_SENSOR_TOPIC = "rufus/{device_id}/sensors/light"
MASK_STATE_SENSOR_TOPIC = "rufus/{device_id}/sensors/mask_state"

STUNT_COMMAND_TOPIC = "rufus/{device_id}/commands/stunt"
DISPLAY_COMMAND_TOPIC = "rufus/{device_id}/commands/display"

ACK_STATUS_TOPIC = "rufus/{device_id}/status/ack"
BATTERY_STATUS_TOPIC = "rufus/{device_id}/status/battery"

SENSOR_TOPIC_FILTER = "rufus/+/sensors/#"
ACK_STATUS_TOPIC_FILTER = "rufus/+/status/ack"
BATTERY_STATUS_TOPIC_FILTER = "rufus/+/status/battery"


def format_topic(template: str, device_id: str) -> str:
    return template.format(device_id=device_id)
