import asyncio
from typing import Any

from litellm import completion

from app.config import get_settings


class CompletionResult(str):
    model_used: str
    tool_calls: list[dict]

    def __new__(cls, value: str, model_used: str, tool_calls: list[dict] | None = None) -> "CompletionResult":
        instance = str.__new__(cls, value)
        instance.model_used = model_used
        instance.tool_calls = tool_calls or []
        return instance


class LLMServiceUnavailableError(RuntimeError):
    """Raised when the configured local Ollama model is unavailable."""


def _extract_reply_and_tool_calls(response: Any, tools_provided: bool = False) -> tuple[str, list[dict]]:
    message = response.choices[0].message
    content = getattr(message, "content", "") or ""
    
    if not tools_provided:
        return content, []

    tool_calls_raw = getattr(message, "tool_calls", None) or []
    
    extracted_calls = []
    for tc in tool_calls_raw:
        func = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
        if func:
            name = getattr(func, "name", None) or (func.get("name") if isinstance(func, dict) else "")
            args_raw = getattr(func, "arguments", None) or (func.get("arguments") if isinstance(func, dict) else "{}")
            if isinstance(args_raw, str):
                import json
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}
            elif isinstance(args_raw, dict):
                args = args_raw
            else:
                args = {}
            if name:
                extracted_calls.append({"name": name, "arguments": args})

    # Fallback parsing for small local models outputting JSON tool calls in text
    if not extracted_calls and content and "{" in content and "}" in content:
        import json
        import re
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                tool_name = data.get("tool") or data.get("name") or data.get("action")
                args = data.get("arguments") or data.get("parameters") or {k: v for k, v in data.items() if k not in {"tool", "name", "action"}}
                if tool_name and isinstance(args, dict):
                    extracted_calls.append({"name": tool_name, "arguments": args})
            except Exception:
                pass

    return content, extracted_calls


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


async def get_completion(messages: list[dict], tools: list[dict] | None = None) -> CompletionResult:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "api_base": settings.ollama_api_base,
        "api_key": "ollama",
        "timeout": settings.ollama_timeout,
        "max_tokens": 180,
    }
    if tools:
        # Normalize tools to standard OpenAI function-calling format
        formatted = []
        for t in tools:
            if "parameters" in t and "type" not in t:
                formatted.append({"type": "function", "function": t})
            else:
                formatted.append(t)
        kwargs["tools"] = formatted

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(completion, **kwargs),
            timeout=settings.ollama_timeout + 2,
        )
    except TimeoutError as exc:
        raise LLMServiceUnavailableError(_build_error_message(exc)) from exc
    except Exception as exc:
        if exc.__class__.__module__.startswith("litellm"):
            raise LLMServiceUnavailableError(_build_error_message(exc)) from exc
        raise

    content, tool_calls = _extract_reply_and_tool_calls(response, tools_provided=bool(tools))
    return CompletionResult(content, settings.ollama_model, tool_calls)

