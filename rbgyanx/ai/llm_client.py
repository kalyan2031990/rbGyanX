"""
OpenAI-compatible LLM client abstraction (v2 Phase 5 · Slice A).

One interface, pluggable transport. The transport that actually performs an HTTP request lands
in Slice B; here the default is :class:`NullTransport`, which makes a live call impossible. That
keeps this slice free of any network code while still exercising the full request-building,
PHI-warning and self-correction/retry logic (UMLBot pattern, Godwin & Melvin, SoftwareX 102789).

PHI: this layer runs the PHI guard on every outgoing message and attaches the findings to the
result as a *warning*. Per the owner's documented policy it does not block. It never writes
prompts or responses to disk or logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from rbgyanx.ai.config import AiConfig
from rbgyanx.ai.phi_guard import PhiFinding, scan_for_phi

__all__ = [
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "Transport",
    "NullTransport",
    "LLMError",
    "LLMNotConfigured",
    "LLMClient",
]


class LLMError(RuntimeError):
    """Any failure talking to the model (transport or protocol)."""


class LLMNotConfigured(LLMError):
    """Raised when no usable transport/endpoint is configured (e.g. the default NullTransport)."""


@dataclass(frozen=True)
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMRequest:
    messages: list[LLMMessage]
    model: str
    temperature: float = 0.2
    max_tokens: int = 1024

    def outgoing_text(self) -> str:
        """The user/assistant text that would leave the machine (system prompt excluded)."""
        return "\n".join(m.content for m in self.messages if m.role != "system")


@dataclass
class LLMResponse:
    text: str
    model: str
    finish_reason: str = "stop"
    phi_findings: list[PhiFinding] = field(default_factory=list)
    attempts: int = 1

    @property
    def had_phi_warning(self) -> bool:
        return bool(self.phi_findings)


@runtime_checkable
class Transport(Protocol):
    """Sends a request to an OpenAI-compatible endpoint and returns the model's text."""

    def complete(self, request: LLMRequest, *, base_url: str, api_key: str | None) -> str: ...


class NullTransport:
    """The safe default: cannot reach any network. Present so Slice A ships no live path."""

    def complete(self, request: LLMRequest, *, base_url: str, api_key: str | None) -> str:
        raise LLMNotConfigured(
            "No AI transport is configured. The live HTTP transport is wired in Phase 5 Slice B; "
            "until then the panel runs in preview-only mode."
        )


class LLMClient:
    """Builds requests, runs the PHI guard, and drives self-correction/retry over a transport."""

    def __init__(self, config: AiConfig, transport: Transport | None = None) -> None:
        self.config = config
        self.transport: Transport = transport or NullTransport()

    # ------------------------------------------------------------------ request

    def build_request(self, messages: list[LLMMessage]) -> LLMRequest:
        return LLMRequest(
            messages=list(messages),
            model=self.config.resolved_model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    def scan(self, messages: list[LLMMessage]) -> list[PhiFinding]:
        """PHI findings across everything that would be transmitted (system prompt excluded)."""
        text = "\n".join(m.content for m in messages if m.role != "system")
        return scan_for_phi(text)

    # -------------------------------------------------------------------- send

    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        """Run one exchange. Warns on PHI (never blocks); retries with self-correction.

        Raises :class:`LLMNotConfigured` when only the NullTransport is available, and
        :class:`LLMError` after exhausting retries.
        """
        request = self.build_request(messages)
        findings = self.scan(messages)  # warn, do not block

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 2):  # 1 try + N retries
            try:
                text = self.transport.complete(
                    request, base_url=self.config.resolved_base_url, api_key=self.config.api_key
                )
            except LLMNotConfigured:
                raise  # not retryable; nothing is configured
            except Exception as exc:  # transport/protocol hiccup -> self-correct and retry
                last_exc = exc
                continue
            if not text or not text.strip():
                last_exc = LLMError("model returned an empty response")
                continue
            return LLMResponse(
                text=text,
                model=request.model,
                phi_findings=findings,
                attempts=attempt,
            )
        raise LLMError(
            f"AI request failed after {self.config.max_retries + 1} attempts: {last_exc}"
        )
