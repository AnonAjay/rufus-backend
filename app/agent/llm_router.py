import asyncio
from typing import Any

from litellm import completion

from app.config import get_settings


class CompletionResult(str):
    model_used: str

    def __new__(cls, value: str, model_used: str) -> "CompletionResult":
        instance = str.__new__(cls, value)
        instance.model_used = model_used
        return instance


class LLMServiceUnavailableError(RuntimeError):
    """Raised when the configured local Ollama model is unavailable."""


def _extract_reply(response: Any) -> str:
    return response.choices[0].message.content or ""


def _build_error_message(exc: Exception) -> str:
    settings = get_settings()
    original_error = str(exc) or exc.__class__.__name__
    return (
        "Ollama request failed. "
        f"Configured model={settings.ollama_model}, "
        f"ollama_api_base={settings.ollama_api_base}, "
        f"timeout={settings.ollama_timeout}s. "
        "Check that `ollama serve` is running, "
        f"the model is pulled with `ollama pull {settings.ollama_model.removeprefix('ollama/')}`, "
        "and OLLAMA_API_BASE is reachable. "
        f"Original error: {original_error}"
    )


async def get_completion(messages: list[dict]) -> str:
    settings = get_settings()
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                completion,
                model=settings.ollama_model,
                messages=messages,
                api_base=settings.ollama_api_base,
                api_key="ollama",
                timeout=settings.ollama_timeout,
                max_tokens=180,
            ),
            timeout=settings.ollama_timeout + 2,
        )
    except TimeoutError as exc:
        raise LLMServiceUnavailableError(_build_error_message(exc)) from exc
    except Exception as exc:
        if exc.__class__.__module__.startswith("litellm"):
            raise LLMServiceUnavailableError(_build_error_message(exc)) from exc
        raise
    return CompletionResult(_extract_reply(response), settings.ollama_model)
