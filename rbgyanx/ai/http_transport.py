"""
Live HTTP transport for the AI panel (v2 Phase 5 · Slice B).

One OpenAI-compatible ``POST {base_url}/chat/completions`` covers all three presets:
Local (Ollama/llama.cpp), Kimi (Moonshot) and Claude (Anthropic's OpenAI-compatible endpoint).
Built on the standard library only (``urllib``), so it adds no dependency and bundles cleanly.

This is the module where data actually leaves the machine. It is reached only when the user has
enabled the feature and confirmed the send (see the Qt panel). It writes nothing to disk and
logs nothing — the request/response bodies live only for the duration of the call.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from rbgyanx.ai.llm_client import LLMError, LLMRequest

__all__ = ["HttpTransport"]


class HttpTransport:
    """OpenAI-compatible chat-completions transport over ``urllib``."""

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def complete(self, request: LLMRequest, *, base_url: str, api_key: str | None) -> str:
        """The assistant text. Kept for the :class:`Transport` protocol and simple callers."""
        message = self.complete_message(request, base_url=base_url, api_key=api_key)
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content:
            raise LLMError("AI endpoint returned an empty message")
        return str(content)

    def complete_message(self, request: LLMRequest, *, base_url: str, api_key: str | None) -> dict:
        """The COMPLETE assistant message, for replay into the next turn.

        Reasoning models need their own previous message back in full - reasoning_content and
        tool_calls included - so this returns the provider's dict rather than a parsed subset.
        A client that returns only the text degrades multi-turn silently.
        """
        url = base_url.rstrip("/") + "/chat/completions"
        payload: dict = {
            "model": request.model,
            # Assistant turns are replayed verbatim; see LLMMessage.to_wire.
            "messages": request.wire_messages(),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.reasoning_effort:
            payload["reasoning_effort"] = request.reasoning_effort
        body = json.dumps(payload).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if api_key:  # local endpoints need no key
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # 4xx/5xx from the provider
            detail = _safe_error_body(exc)
            raise LLMError(f"AI endpoint returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # DNS/connection/timeout
            raise LLMError(f"could not reach AI endpoint {url}: {exc.reason}") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMError(f"AI endpoint returned an unreadable response: {exc}") from exc

        return _extract_message(payload)


def _safe_error_body(exc: urllib.error.HTTPError) -> str:
    """A short, safe error string — never echo the whole body (may contain the prompt)."""
    try:
        raw = exc.read().decode("utf-8", "replace")
    except Exception:
        return exc.reason or "unknown error"
    try:
        obj = json.loads(raw)
        msg = obj.get("error", {})
        if isinstance(msg, dict):
            return str(msg.get("message", msg.get("type", "error")))[:200]
        return str(msg)[:200]
    except Exception:
        return raw[:200]


def _extract_message(payload: dict) -> dict:
    """Pull the assistant message out of an OpenAI-compatible response, unmodified.

    Deliberately does not require ``content``: a turn that only requests a tool call carries
    ``content: null`` and a populated ``tool_calls``, and rejecting it here would break tool
    use on exactly the models this matters most for.
    """
    try:
        choices = payload["choices"]
        if not choices:
            raise LLMError("AI endpoint returned no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LLMError("AI endpoint returned no assistant message")
        if not message.get("content") and not message.get("tool_calls"):
            raise LLMError("AI endpoint returned an empty message")
        return message
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected AI response shape: {exc}") from exc
