"""Configuration loading for watermark_remove (self-contained)."""
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


# DeepSeek Vision model. Override via env if the model name changes.
# NOTE: the official model id is "deepseek-v4-flash-vision-exp" (experimental,
# understanding-only — it accepts image input and returns text/JSON, not images).
DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_VISION_MODEL = get_env("DEEPSEEK_VISION_MODEL", "deepseek-v4-flash-vision-exp")
