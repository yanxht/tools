"""Configuration loading for the VoxCPM2 backend (self-contained)."""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_env(key, default=None, required=False):
    val = os.getenv(key, default)
    if required and not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill it in."
        )
    return val


VOXCPM_VENV = get_env(
    "VOXCPM_VENV", os.path.expanduser("~/envs/voiceforge/bin/python")
)
VOXCPM_REFERENCE_DIR = get_env(
    "VOXCPM_REFERENCE_DIR", os.path.expanduser("~/voxcpm_data")
)
