"""Shared LLM client for Trip and Stylist agents."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
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
        timeout=120,
        max_retries=2,
    )


def invoke_structured(
    model: BaseChatModel,
    schema: type[T],
    messages: list[BaseMessage],
    *,
    retries: int = 0,
    retry_hint: str | None = None,
) -> T:
    """
    Parse LLM output into a Pydantic model.

    DeepSeek rejects the default json_schema response_format; use json_mode instead.
    """
    hint = retry_hint or (
        "Your previous reply was null or invalid JSON. "
        "Return ONLY valid JSON matching the required schema."
    )
    attempt_messages = messages
    last_error: OutputParserException | None = None

    for attempt in range(retries + 1):
        try:
            structured = model.with_structured_output(schema, method="json_mode")
            return structured.invoke(attempt_messages)
        except OutputParserException as exc:
            last_error = exc
            if attempt >= retries:
                raise
            attempt_messages = [*messages, HumanMessage(content=hint)]

    if last_error is not None:
        raise last_error
    msg = "invoke_structured failed without a parser exception"
    raise RuntimeError(msg)
