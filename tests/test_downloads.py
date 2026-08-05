"""
Downloads a curated set of English Piper TTS voices from rhasspy/piper-voices
and generates a sample audio clip with each, so you can compare them directly.

Usage:
    python download_and_test_voices.py

Requires:
    pip install huggingface_hub
    piper-tts already installed and on PATH (pip install piper-tts)
"""

import subprocess
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "rhasspy/piper-voices"
OUTPUT_DIR = Path("piper_voices")
SAMPLE_TEXT = "Hey, I'm Rufus, your companion robot. How can I help you today?"

# Curated spread: mix of male/female, a couple of quality tiers.
# (name, quality, gender_label)
VOICES = [
    ("amy", "medium", "female"),
    ("kathleen", "low", "female"),
    ("hfc_female", "medium", "female"),
    ("kristin", "medium", "female"),
    ("hfc_male", "medium", "male"),
    ("joe", "medium", "male"),
    ("john", "medium", "male"),
]


def download_voice(name: str, quality: str) -> tuple[Path, Path]:
    """Download the .onnx and .onnx.json for one voice, return local paths."""
    onnx_subpath = f"en/en_US/{name}/{quality}/en_US-{name}-{quality}.onnx"
    json_subpath = f"{onnx_subpath}.json"

    print(f"  Downloading {name} ({quality})...")
    onnx_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=onnx_subpath,
        local_dir=str(OUTPUT_DIR),
    )
    json_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=json_subpath,
        local_dir=str(OUTPUT_DIR),
    )
    return Path(onnx_path), Path(json_path)


def generate_sample(name: str, quality: str, onnx_path: Path) -> Path:
    """Run piper to synthesize the sample sentence with this voice."""
    out_path = OUTPUT_DIR / f"sample_{name}_{quality}.wav"
    print(f"  Generating sample -> {out_path.name}")
    subprocess.run(
        [
            "piper",
            "--model", str(onnx_path),
            "--output_file", str(out_path),
        ],
        input=SAMPLE_TEXT,
        text=True,
        check=True,
    )
    return out_path


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    results = []

    for name, quality, gender in VOICES:
        print(f"\n[{name} / {quality} / {gender}]")
        try:
            onnx_path, _json_path = download_voice(name, quality)
            sample_path = generate_sample(name, quality, onnx_path)
            results.append((name, quality, gender, sample_path))
        except Exception as e:
            print(f"  FAILED: {e}")

    print("\n" + "=" * 60)
    print("Done. Generated samples:")
    for name, quality, gender, sample_path in results:
        print(f"  {gender:6} | {name:12} ({quality:6}) -> {sample_path}")
    print("=" * 60)
    print(f"\nAll files are in: {OUTPUT_DIR.resolve()}")
    print("Play each sample_*.wav file to compare voices side by side.")


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("This script uses tuple[Path, Path] typing, needs Python 3.9+.")
    main()