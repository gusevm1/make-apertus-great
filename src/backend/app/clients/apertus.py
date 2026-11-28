import base64
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict, cast

import httpx2
import openai
from fastapi import Depends, Request
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.completion_create_params import ResponseFormat
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import UpstreamError

STRUCTURED_TEMPERATURE = 0.0
TRANSCRIBE_TEMPERATURE = 0.0
STRUCTURED_MAX_ATTEMPTS = 2
RETRY_INSTRUCTION = "That JSON was invalid. Return corrected JSON only. Errors:"
# The -thinking models write their reasoning into the content, between these two markers.
THINKING_START = "<|inner_prefix|>"
THINKING_END = "<|inner_suffix|>"


class Model(StrEnum):
    FAST = "fast"
    SMART = "smart"
    THINKING = "thinking"


class TextPart(TypedDict):
    type: Literal["text"]
    text: str


class ImageURL(TypedDict):
    url: str


class ImagePart(TypedDict):
    """An image as a `data:<media type>;base64,...` URL."""

    type: Literal["image_url"]
    image_url: ImageURL


class InputAudio(TypedDict):
    data: str
    format: Literal["wav", "mp3"]


class AudioPart(TypedDict):
    """Base64 audio."""

    type: Literal["input_audio"]
    input_audio: InputAudio


type ContentPart = TextPart | ImagePart | AudioPart


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str | list[ContentPart]


@dataclass(frozen=True)
class LLMResult[T]:
    content: T
    model: str
    latency_ms: int
    tokens_in: int | None
    tokens_out: int | None


class LLMStream:
    """Async iterator of text chunks; `result` holds the full LLMResult once iteration ends."""

    def __init__(self, chunks: AsyncIterator[str]) -> None:
        self._chunks = chunks
        self.result: LLMResult[str] | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        return self._chunks


def _call_logger(path: str | None) -> logging.Logger:
    logger = logging.getLogger("llm_calls")
    if not logger.handlers:
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = logging.FileHandler(path)
        else:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def _to_openai(messages: list[Message]) -> list[ChatCompletionMessageParam]:
    return cast(list[ChatCompletionMessageParam], list(messages))


def _loggable(messages: list[Message]) -> list[Message]:
    """The messages with image and audio data replaced by their size."""
    return [
        {**message, "content": [_loggable_part(part=part) for part in message["content"]]}
        if isinstance(message["content"], list)
        else message
        for message in messages
    ]


def _loggable_part(part: ContentPart) -> ContentPart:
    if part["type"] == "image_url":
        return {
            "type": "image_url",
            "image_url": {"url": f"<{len(part['image_url']['url'])} chars>"},
        }
    if part["type"] == "input_audio":
        audio = part["input_audio"]
        return {
            "type": "input_audio",
            "input_audio": {**audio, "data": f"<{len(audio['data'])} chars>"},
        }
    return part


def _strip_code_fences(text: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, re.DOTALL)
    return match.group(1) if match is not None else text


class ApertusClient:
    def __init__(self, settings: Settings, http_client: httpx2.AsyncClient | None = None) -> None:
        self._openai = openai.AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=settings.apertus_timeout_seconds,
            max_retries=settings.apertus_max_retries,
            http_client=http_client,
        )
        self._models = {
            Model.FAST: settings.llm_name_fast or settings.llm_name,
            Model.SMART: settings.llm_name,
            Model.THINKING: settings.llm_name_thinking or settings.llm_name,
        }
        self.has_thinking_model = settings.llm_name_thinking is not None
        self._json_schema_supported = settings.apertus_json_schema_supported
        self._log_content = settings.log_llm_content
        self._log = _call_logger(path=settings.llm_log_path)

    def model_name(self, model: Model) -> str:
        """The gateway's name for `model`."""
        return self._models[model]

    async def close(self) -> None:
        await self._openai.close()

    async def chat(
        self,
        messages: list[Message],
        *,
        model: Model,
        purpose: str,
        temperature: float | None = None,
    ) -> LLMResult[str]:
        """Complete a chat; returns the full text, without a thinking model's reasoning."""
        return await self._complete(
            messages=messages, model=model, purpose=purpose, temperature=temperature
        )

    async def transcribe(
        self, wav: bytes, instruction: str, *, model: Model, purpose: str
    ) -> LLMResult[str]:
        """Transcribe WAV audio by sending it as an audio part after the instruction."""
        audio: AudioPart = {
            "type": "input_audio",
            "input_audio": {"data": base64.b64encode(wav).decode(), "format": "wav"},
        }
        message = Message(role="user", content=[{"type": "text", "text": instruction}, audio])
        return await self._complete(
            messages=[message], model=model, purpose=purpose, temperature=TRANSCRIBE_TEMPERATURE
        )

    def stream_chat(self, messages: list[Message], *, model: Model, purpose: str) -> LLMStream:
        """Stream a chat as text chunks; read `.result` after iterating."""
        stream: LLMStream

        async def chunks() -> AsyncIterator[str]:
            started = time.perf_counter()
            parts: list[str] = []
            usage = None
            try:
                response = await self._openai.chat.completions.create(
                    model=self._models[model],
                    messages=_to_openai(messages=messages),
                    stream=True,
                    stream_options={"include_usage": True},
                )
                async for chunk in response:
                    usage = chunk.usage or usage
                    if chunk.choices and chunk.choices[0].delta.content:
                        parts.append(chunk.choices[0].delta.content)
                        yield chunk.choices[0].delta.content
            except openai.APIError as exc:
                self._write_log(
                    purpose=purpose,
                    model=model,
                    started=started,
                    usage=None,
                    messages=messages,
                    response=None,
                    error=exc,
                )
                raise _upstream_error(exc=exc) from exc
            text = "".join(parts)
            stream.result = self._result(text=text, model=model, started=started, usage=usage)
            self._write_log(
                purpose=purpose,
                model=model,
                started=started,
                usage=usage,
                messages=messages,
                response=text,
                error=None,
            )

        stream = LLMStream(chunks=chunks())
        return stream

    async def structured[T: BaseModel](
        self,
        messages: list[Message],
        *,
        schema: type[T],
        model: Model,
        purpose: str,
        timeout_seconds: float | None = None,
        json_schema_mode: bool | None = None,
    ) -> LLMResult[T]:
        """Complete a chat validated against `schema`; `json_schema_mode` overrides the setting."""
        json_schema = schema.model_json_schema()
        constrained = self._json_schema_supported if json_schema_mode is None else json_schema_mode
        if constrained:
            response_format: ResponseFormat | None = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": json_schema},
            }
            attempt_messages = list(messages)
        else:
            response_format = None
            instruction = (
                "Respond with only a JSON object (no prose, no code fences) matching this "
                f"JSON schema:\n{json.dumps(json_schema)}"
            )
            attempt_messages = [*messages, Message(role="user", content=instruction)]

        last_error = ""
        reason = ""
        for _ in range(STRUCTURED_MAX_ATTEMPTS):
            raw = await self._complete(
                messages=attempt_messages,
                model=model,
                purpose=purpose,
                temperature=STRUCTURED_TEMPERATURE,
                response_format=response_format,
                timeout_seconds=timeout_seconds,
            )
            try:
                parsed = schema.model_validate_json(_strip_code_fences(text=raw.content))
            except ValidationError as exc:
                last_error = str(exc)
                reason = _first_error(exc=exc)
                attempt_messages = [
                    *attempt_messages,
                    Message(role="assistant", content=raw.content),
                    Message(role="user", content=f"{RETRY_INSTRUCTION}\n{last_error}"),
                ]
                continue
            return LLMResult(
                content=parsed,
                model=raw.model,
                latency_ms=raw.latency_ms,
                tokens_in=raw.tokens_in,
                tokens_out=raw.tokens_out,
            )
        raise UpstreamError(f"Model returned invalid {schema.__name__} twice, last: {reason}")

    async def _complete(
        self,
        messages: list[Message],
        model: Model,
        purpose: str,
        *,
        temperature: float | None = None,
        response_format: ResponseFormat | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResult[str]:
        started = time.perf_counter()
        try:
            response = await self._openai.chat.completions.create(
                model=self._models[model],
                messages=_to_openai(messages=messages),
                temperature=openai.omit if temperature is None else temperature,
                response_format=openai.omit if response_format is None else response_format,
                timeout=openai.not_given if timeout_seconds is None else timeout_seconds,
            )
        except openai.APIError as exc:
            self._write_log(
                purpose=purpose,
                model=model,
                started=started,
                usage=None,
                messages=messages,
                response=None,
                error=exc,
            )
            raise _upstream_error(exc=exc) from exc
        text = response.choices[0].message.content or ""
        self._write_log(
            purpose=purpose,
            model=model,
            started=started,
            usage=response.usage,
            messages=messages,
            response=text,
            error=None,
        )
        if THINKING_START in text and THINKING_END not in text:
            raise UpstreamError("Apertus stopped while still thinking")
        text = text.split(THINKING_END)[-1].strip() if THINKING_END in text else text
        return self._result(text=text, model=model, started=started, usage=response.usage)

    def _result(self, text: str, model: Model, started: float, usage: Any) -> LLMResult[str]:
        return LLMResult(
            content=text,
            model=self._models[model],
            latency_ms=round((time.perf_counter() - started) * 1000),
            tokens_in=usage.prompt_tokens if usage is not None else None,
            tokens_out=usage.completion_tokens if usage is not None else None,
        )

    def _write_log(
        self,
        purpose: str,
        model: Model,
        started: float,
        usage: Any,
        messages: list[Message],
        response: str | None,
        error: Exception | None,
    ) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "purpose": purpose,
            "model": self._models[model],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "tokens_in": usage.prompt_tokens if usage is not None else None,
            "tokens_out": usage.completion_tokens if usage is not None else None,
            "error": type(error).__name__ if error is not None else None,
        }
        if self._log_content:
            entry["prompt"] = _loggable(messages=messages)
            entry["response"] = response
        self._log.info(json.dumps(entry, ensure_ascii=False))


def _first_error(exc: ValidationError) -> str:
    # Without the input, which holds the model's answer.
    error = exc.errors(include_input=False, include_url=False)[0]
    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}" if location else error["msg"]


def _upstream_error(exc: openai.APIError) -> UpstreamError:
    if isinstance(exc, openai.APITimeoutError):
        return UpstreamError("Apertus timed out")
    if isinstance(exc, openai.RateLimitError):
        return UpstreamError("Apertus rate limit reached")
    if isinstance(exc, openai.APIStatusError):
        return UpstreamError(f"Apertus returned {exc.status_code}")
    return UpstreamError("Apertus is unreachable")


def get_apertus_client(request: Request) -> ApertusClient:
    return request.app.state.apertus


ApertusClientDep = Annotated[ApertusClient, Depends(get_apertus_client)]
