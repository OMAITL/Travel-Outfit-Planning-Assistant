"""Shared LLM client for Trip and Stylist agents."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import get_settings

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
T = TypeVar("T", bound=BaseModel)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


@lru_cache
def get_chat_model() -> ChatOpenAI:
    settings = get_settings()
    settings.validate_llm()
    base_url = settings.openai_api_base.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=base_url,
        model=settings.openai_model,
        temperature=0.3,
    )


def invoke_structured(
    model: BaseChatModel,
    schema: type[T],
    messages: list[BaseMessage],
) -> T:
    """
    Parse LLM output into a Pydantic model.

    DeepSeek rejects the default json_schema response_format; use json_mode instead.
    """
    structured = model.with_structured_output(schema, method="json_mode")
    return structured.invoke(messages)
