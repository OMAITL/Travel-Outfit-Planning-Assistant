"""Shared LLM client for Trip and Stylist agents."""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import get_settings
from src.services.api_recorder import record_api_exchange

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
T = TypeVar("T", bound=BaseModel)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _messages_to_log(messages: list[BaseMessage]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for message in messages:
        role = getattr(message, "type", message.__class__.__name__.replace("Message", "").lower())
        content = message.content
        if isinstance(content, list):
            text = str(content)
        else:
            text = str(content)
        rows.append({"role": role, "content": text})
    return rows


def _normalize_openai_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


@lru_cache
def _build_chat_model(model: str, temperature: float) -> ChatOpenAI:
    settings = get_settings()
    settings.validate_llm()
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=_normalize_openai_base_url(settings.openai_api_base),
        model=model,
        temperature=temperature,
        timeout=120,
        max_retries=2,
    )


@lru_cache
def _build_chat_model_with_credentials(
    model: str,
    temperature: float,
    api_key: str,
    api_base: str,
) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=api_key,
        base_url=_normalize_openai_base_url(api_base),
        model=model,
        temperature=temperature,
        timeout=120,
        max_retries=2,
    )


def get_chat_model() -> ChatOpenAI:
    return _build_chat_model(get_settings().openai_model, 0.3)


def get_vision_model() -> ChatOpenAI:
    """Multimodal model for the Vision Agent (falls back to the default model)."""
    settings = get_settings()
    model = settings.vision_model or settings.openai_model
    api_key = settings.vision_api_key or settings.dashscope_api_key
    api_base = settings.vision_api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    if api_key:
        return _build_chat_model_with_credentials(model, 0.3, api_key, api_base)
    return _build_chat_model(model, 0.3)


def build_image_human_message(text: str, image_urls: list[str]) -> HumanMessage:
    """
    Build a multimodal HumanMessage mixing text and images.

    ``image_urls`` may be ``data:`` URIs (preferred, since XHS CDN blocks
    hotlinking server-side) or plain http(s) URLs.
    """
    content: list[dict[str, object]] = [{"type": "text", "text": text}]
    for url in image_urls:
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
    return HumanMessage(content=content)


def invoke_structured(
    model: BaseChatModel,
    schema: type[T],
    messages: list[BaseMessage],
    *,
    retries: int = 0,
    retry_hint: str | None = None,
    operation: str | None = None,
) -> T:
    """
    Parse LLM output into a Pydantic model.

    DeepSeek rejects the default json_schema response_format; use json_mode instead.
    """
    settings = get_settings()
    hint = retry_hint or (
        "Your previous reply was null or invalid JSON. "
        "Return ONLY valid JSON matching the required schema."
    )
    attempt_messages = messages
    last_error: OutputParserException | None = None
    op_name = operation or schema.__name__

    for attempt in range(retries + 1):
        raw_model = getattr(model, "model_name", None)
        model_label = raw_model if isinstance(raw_model, str) else settings.openai_model
        started = time.perf_counter()
        request_log = {
            "model": model_label,
            "schema": schema.__name__,
            "messages": _messages_to_log(attempt_messages),
            "method": "json_mode",
        }
        try:
            structured = model.with_structured_output(schema, method="json_mode")
            result = structured.invoke(attempt_messages)
            record_api_exchange(
                "deepseek",
                op_name,
                request_log,
                response=result.model_dump(mode="json"),
                status="success",
                duration_ms=(time.perf_counter() - started) * 1000,
                metadata={"attempt": attempt + 1},
            )
            return result
        except OutputParserException as exc:
            last_error = exc
            record_api_exchange(
                "deepseek",
                op_name,
                request_log,
                response=None,
                status="error",
                error=str(exc),
                duration_ms=(time.perf_counter() - started) * 1000,
                metadata={"attempt": attempt + 1, "error_type": "OutputParserException"},
            )
            if attempt >= retries:
                raise
            attempt_messages = [*messages, HumanMessage(content=hint)]

    if last_error is not None:
        raise last_error
    msg = "invoke_structured failed without a parser exception"
    raise RuntimeError(msg)
