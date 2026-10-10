import os
import pytest
from faster_whisper import WhisperModel


def test_stt_sample():
    audio_path = "../../example_voices/test_voice.m4a"
    if not os.path.exists(audio_path):
        pytest.skip(f"Audio sample not found at {audio_path}")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path)
    assert info is not None