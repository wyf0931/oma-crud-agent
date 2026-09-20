"""OpenAI-compatible LLM provider."""

from typing import Optional
import os
import logging
import time
import json
from urllib.parse import urlparse

from openai import APIConnectionError, APITimeoutError, RateLimitError
from shared.trace import trace_event


logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """Chat Completions client for OpenAI and compatible providers."""

    MAX_RETRIES = 3
    RETRY_BASE_SECONDS = 2.0
    RETRY_MAX_SECONDS = 30.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        """Initialize an OpenAI-compatible provider."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.default_model = default_model or os.getenv("OPENAI_MODEL")
        self.response_format = self._load_response_format()

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set. Set it in your .env file.")
        if not self.base_url:
            raise ValueError("OPENAI_BASE_URL not set. Set it in your .env file.")
        if not self.default_model:
            raise ValueError("OPENAI_MODEL not set. Set it in your .env file.")

    @staticmethod
    def _load_response_format() -> Optional[dict]:
        """Load an optional response format from OPENAI_RESPONSE_FORMAT."""
        value = os.getenv("OPENAI_RESPONSE_FORMAT", "").strip()
        if not value:
            return None
        if value == "json_object":
            return {"type": "json_object"}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "OPENAI_RESPONSE_FORMAT must be empty, json_object, or valid JSON."
            ) from exc
        if not isinstance(parsed, dict) or not parsed.get("type"):
            raise ValueError(
                "OPENAI_RESPONSE_FORMAT must be a JSON object with a type field."
            )
        return parsed

    def get_client(self):
        """Get the OpenAI SDK client configured for the selected endpoint."""
        from openai import OpenAI

        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60.0,
            max_retries=0,
        )

    def _create_completion(self, client, **kwargs):
        """Call the provider with bounded retries for transient failures."""
        model = kwargs.get("model")
        messages = kwargs.get("messages") or []
        prompt_chars = sum(len(str(message.get("content") or "")) for message in messages)
        endpoint = urlparse(self.base_url).netloc or self.base_url
        for attempt in range(self.MAX_RETRIES + 1):
            started = time.time()
            trace_event(
                "llm_request_started",
                provider=endpoint,
                model=model,
                attempt=attempt + 1,
                prompt_chars=prompt_chars,
                max_tokens=kwargs.get("max_tokens"),
                response_format=kwargs.get("response_format"),
            )
            try:
                response = client.chat.completions.create(**kwargs)
                usage = getattr(response, "usage", None)
                trace_event(
                    "llm_request_finished",
                    provider=endpoint,
                    model=model,
                    attempt=attempt + 1,
                    status="success",
                    duration_ms=int((time.time() - started) * 1000),
                    response_chars=len(str(getattr(getattr(response, "choices", [None])[0], "message", None) or "")),
                    usage={
                        "prompt_tokens": getattr(usage, "prompt_tokens", None),
                        "completion_tokens": getattr(usage, "completion_tokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None),
                    } if usage else None,
                )
                return response
            except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
                status_code = getattr(exc, "status_code", None)
                if attempt >= self.MAX_RETRIES:
                    trace_event(
                        "llm_request_finished",
                        provider=endpoint,
                        model=model,
                        attempt=attempt + 1,
                        status="failed",
                        status_code=status_code,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        duration_ms=int((time.time() - started) * 1000),
                    )
                    raise

                delay = self._retry_delay(exc, attempt)
                trace_event(
                    "llm_retry",
                    provider=endpoint,
                    model=model,
                    attempt=attempt + 1,
                    status_code=status_code,
                    error_type=type(exc).__name__,
                    delay_seconds=delay,
                )
                logger.warning(
                    "LLM request failed (%s); retrying in %.1fs (%d/%d)",
                    type(exc).__name__,
                    delay,
                    attempt + 1,
                    self.MAX_RETRIES,
                )
                time.sleep(delay)

    def _retry_delay(self, exc, attempt: int) -> float:
        """Prefer Retry-After, then use bounded exponential backoff."""
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", {}) if response else {}
        retry_after = headers.get("retry-after") if headers else None
        if retry_after:
            try:
                return min(float(retry_after), self.RETRY_MAX_SECONDS)
            except (TypeError, ValueError):
                pass

        return min(
            self.RETRY_BASE_SECONDS * (2 ** attempt),
            self.RETRY_MAX_SECONDS,
        )

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Call the configured OpenAI-compatible Chat Completions endpoint."""
        client = self.get_client()
        model = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request parameters
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if self.response_format:
            kwargs["response_format"] = self.response_format

        response = self._create_completion(client, **kwargs)
        return response.choices[0].message.content

    def call_detailed(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """Call the configured endpoint and return a rich response dict.

        Returns: {
            'content': str,          # main response text
            'thinking': str|None,    # reasoning content (if thinking mode)
            'prompt': str,           # the user prompt sent
            'model': str,            # model used
            'usage': dict|None,      # {prompt_tokens, completion_tokens, total_tokens}
            'duration_ms': int,      # wall-clock time
        }
        """
        import time

        client = self.get_client()
        model = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if self.response_format:
            kwargs["response_format"] = self.response_format

        t0 = time.time()
        response = self._create_completion(client, **kwargs)
        elapsed = int((time.time() - t0) * 1000)

        choice = response.choices[0]
        msg = choice.message

        # Extract thinking content if present
        thinking_text = None
        if hasattr(msg, 'reasoning_content') and msg.reasoning_content:
            thinking_text = msg.reasoning_content

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return {
            "content": msg.content,
            "thinking": thinking_text,
            "prompt": prompt,
            "model": model,
            "usage": usage,
            "duration_ms": elapsed,
        }

# Global provider instance
_provider: Optional[OpenAICompatibleProvider] = None


def get_provider() -> OpenAICompatibleProvider:
    """Get the global OpenAI-compatible provider instance."""
    global _provider
    if _provider is None:
        _provider = OpenAICompatibleProvider()
    return _provider


def reset_provider():
    """Reset global provider (useful for testing)."""
    global _provider
    _provider = None
