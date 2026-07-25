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
        url = base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(
            {
                "model": request.model,
                "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
        ).encode("utf-8")

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

        return _extract_text(payload)


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


def _extract_text(payload: dict) -> str:
    """Pull the assistant message out of an OpenAI-compatible response."""
    try:
        choices = payload["choices"]
        if not choices:
            raise LLMError("AI endpoint returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):  # some servers return content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not content:
            raise LLMError("AI endpoint returned an empty message")
        return str(content)
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected AI response shape: {exc}") from exc
