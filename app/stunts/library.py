STUNT_LIBRARY = {
    "sit": [{"pose": "sit", "duration_ms": 800}],
    "paw-wave": [{"pose": "raise_front_right", "duration_ms": 400}, {"pose": "wave", "duration_ms": 900}],
    "play-bow": [{"pose": "front_low_rear_high", "duration_ms": 900}],
    "spin": [{"pose": "turn_left_step", "repeat": 4, "duration_ms": 350}],
    "freeze": [{"pose": "hold_current", "duration_ms": 1000}],
}


# TODO(stunts-branch): Convert these named fixed sequences into validated servo
# command frames. The agent may request only these stunt names, never arbitrary
# servo angles.
