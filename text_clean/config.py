"""Configuration loading for text_clean (self-contained)."""
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


DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY")
