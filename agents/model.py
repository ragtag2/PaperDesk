"""Initialize the configured provider with bounded model requests."""

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from .config import Settings


def create_model(settings: Settings) -> BaseChatModel:
    options: dict[str, Any] = {
        "temperature": 0,
        "timeout": settings.model_timeout_seconds,
        "max_tokens": settings.model_max_tokens,
        "max_retries": 0,
    }
    if settings.model == "groq:qwen/qwen3.8-27b":
        options["reasoning_effort"] = "none"
    return init_chat_model(settings.model, **options)
