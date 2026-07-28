"""
rbGyanX AI panel — ADVANCED-only, opt-in assistant (v2 Phase 5).

One OpenAI-compatible abstraction with three presets (local / Claude / Kimi). The assistant
EXPLAINS outputs and drafts notes/code; it makes no clinical recommendations.

Safety model (see ``docs/PHASE5_AI_PANEL_DESIGN.md``): the PHI guard runs on every outgoing
request and WARNS but never blocks (owner decision, 2026-07-25); prompts/responses are never
persisted; BASIC/clinic can never enable the feature. The live HTTP transport is added in
Slice B — this package ships with :class:`~rbgyanx.ai.llm_client.NullTransport`, so importing it
cannot cause a network call.
"""

from __future__ import annotations

from rbgyanx.ai.config import PROVIDERS, AiConfig, Provider
from rbgyanx.ai.context import build_system_prompt, summarise_run
from rbgyanx.ai.llm_client import (
    LLMClient,
    LLMError,
    LLMMessage,
    LLMNotConfigured,
    LLMRequest,
    LLMResponse,
    NullTransport,
    Transport,
)
from rbgyanx.ai.phi_guard import PhiFinding, redact, scan_for_phi

__all__ = [
    "AiConfig",
    "Provider",
    "PROVIDERS",
    "scan_for_phi",
    "redact",
    "PhiFinding",
    "summarise_run",
    "build_system_prompt",
    "LLMClient",
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "Transport",
    "NullTransport",
    "LLMError",
    "LLMNotConfigured",
]
