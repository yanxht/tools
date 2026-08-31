"""Spawn the VoxCPM2 worker in the heavy venv and collect the result."""
import json
import os
import subprocess
import tempfile

from . import config


def _reference_path(gender):
    gender = (gender or "Unknown").lower()
    if gender.startswith("male"):
        name = "male_reference.wav"
    elif gender.startswith("female"):
        name = "female_reference.wav"
    else:
        name = "male_reference.wav"
    return os.path.join(config.VOXCPM_REFERENCE_DIR, name)


def synthesize(text, output_path, gender="Female"):
    """Synthesize `text` to `output_path` (MP3) via VoxCPM2. Returns duration (s) or False."""
    ref_path = _reference_path(gender)
    if not os.path.exists(ref_path):
        print(f"❌ VoxCPM reference missing: {ref_path}")
        return False
    if not os.path.exists(config.VOXCPM_VENV):
        print(f"❌ VoxCPM venv not found: {config.VOXCPM_VENV}")
        return False

    abs_out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    worker = os.path.join(os.path.dirname(__file__), "worker.py")

    with tempfile.TemporaryDirectory() as tmp:
        text_path = os.path.join(tmp, "text.txt")
        result_path = os.path.join(tmp, "result.json")
        with open(text_path, "w", encoding="utf-8") as fh:
            fh.write(text)

        try:
            proc = subprocess.run(
                [config.VOXCPM_VENV, worker, text_path, ref_path, abs_out, result_path],
                capture_output=True, text=True, timeout=3600,
            )
        except subprocess.TimeoutExpired:
            print("❌ VoxCPM timed out")
            return False

        result = None
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as fh:
                try:
                    result = json.load(fh)
                except Exception:
                    result = None
        if result and result.get("ok"):
            return result.get("duration")
        print(f"❌ VoxCPM failed: {result or proc.stderr[-400:]}")
        return False
