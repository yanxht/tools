import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_env(key, default=None, required=False):
    val = os.getenv(key, default)
    if required and not val:
        raise EnvironmentError(f"Required environment variable '{key}' is not set. Check your .env file.")
    return val


AZURE_SPEECH_KEY = get_env("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = get_env("AZURE_SPEECH_REGION", "eastus")
DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY")
