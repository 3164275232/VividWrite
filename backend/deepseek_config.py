import os

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_THINKING = "disabled"


def get_deepseek_api_key() -> str | None:
    return os.getenv("DEEPSEEK_API_KEY")


def get_deepseek_base_url() -> str:
    return (os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL).strip()


def get_deepseek_model(requested_model: str | None = None) -> str:
    model = (requested_model or os.getenv("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL).strip()
    return model or DEFAULT_DEEPSEEK_MODEL


def get_deepseek_extra_body() -> dict:
    thinking = (os.getenv("DEEPSEEK_THINKING") or DEFAULT_DEEPSEEK_THINKING).strip().lower()
    if thinking in {"enabled", "disabled"}:
        return {"thinking": {"type": thinking}}
    return {"thinking": {"type": DEFAULT_DEEPSEEK_THINKING}}


def get_deepseek_client(api_key: str | None = None) -> OpenAI:
    key = api_key or get_deepseek_api_key()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not configured.")
    return OpenAI(api_key=key, base_url=get_deepseek_base_url())
