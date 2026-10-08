"""Initialize the configured provider with bounded model requests."""

from typing import Any
from urllib.parse import urlsplit

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from .config import Settings


class LightningDeepSeekChatOpenAI(ChatOpenAI):
    """Keep DeepSeek's non-streaming tool exchanges compatible with Lightning."""

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        # ToolStrategy requests "any", which ChatOpenAI turns into "required".
        # DeepSeek thinking mode supports automatic rather than forced selection.
        if tool_choice is True or (isinstance(tool_choice, str) and tool_choice in ("any", "required")):
            tool_choice = "auto"
        return super().bind_tools(tools, tool_choice=tool_choice, **kwargs)

    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        data = response if isinstance(response, dict) else response.model_dump()
        for generation, choice in zip(result.generations, data["choices"]):
            reasoning = choice.get("message", {}).get("reasoning_content")
            if isinstance(reasoning, str):
                generation.message.additional_kwargs["reasoning_content"] = reasoning
        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        for message, serialized in zip(messages, payload["messages"]):
            if isinstance(message, AIMessage):
                reasoning = message.additional_kwargs.get("reasoning_content")
                if isinstance(reasoning, str):
                    serialized["reasoning_content"] = reasoning
        return payload


def create_model(settings: Settings) -> BaseChatModel:
    options: dict[str, Any] = {
        "temperature": 0,
        "timeout": settings.model_timeout_seconds,
        "max_tokens": settings.model_max_tokens,
        "max_retries": 0,
    }
    if settings.model_base_url:
        options.update(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key,
            use_responses_api=False,
        )
        if (settings.model == "openai:lightning-ai/deepseek-v4.1-flash"
                and urlsplit(settings.model_base_url).hostname == "lightning.ai"):
            return LightningDeepSeekChatOpenAI(model=settings.model.split(":", 1)[1], **options)
    if settings.model == "groq:qwen/qwen3.8-27b":
        options["reasoning_effort"] = "none"
    return init_chat_model(settings.model, **options)
