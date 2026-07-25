"""
AI-panel configuration and provider presets (v2 Phase 5 · Slice A).

One OpenAI-compatible abstraction, three selectable presets (UMLBot pattern, Godwin & Melvin,
*SoftwareX* 102789):

    local   -> Ollama / llama.cpp on localhost. Nothing leaves the machine. Recommended for PHI.
    claude  -> Anthropic, via its OpenAI-compatible endpoint. Needs ANTHROPIC_API_KEY.
    kimi    -> Moonshot / Kimi (open weights). Needs MOONSHOT_API_KEY (or KIMI_API_KEY).

Keys come from the environment only — never hard-coded, never committed, never logged. The
feature is ADVANCED-only and enabled only when a key (or a local endpoint) is actually present.

Note on "Claude subscription": a claude.ai Pro/Max plan is not an API credential. The remote
Claude preset needs an Anthropic **API** key (console.anthropic.com). The Local preset is the
zero-key option.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

__all__ = ["Provider", "PROVIDERS", "AiConfig"]


@dataclass(frozen=True)
class Provider:
    """A named OpenAI-compatible endpoint preset."""

    key: str
    label: str
    base_url: str
    default_model: str
    api_key_env: tuple[str, ...] = ()  # env vars searched in order; empty => no key needed
    remote: bool = True  # remote endpoints can transmit data off the machine

    def resolve_key(self, env: dict[str, str] | None = None) -> str | None:
        env = env if env is not None else dict(os.environ)
        for name in self.api_key_env:
            val = env.get(name)
            if val:
                return val
        return None


#: The three presets. ``base_url``/``default_model`` are overridable per :class:`AiConfig`.
PROVIDERS: dict[str, Provider] = {
    "local": Provider(
        key="local",
        label="Local (Ollama / llama.cpp)",
        base_url="http://localhost:11434/v1",
        default_model="llama3.1",
        api_key_env=(),  # localhost needs no key
        remote=False,
    ),
    "claude": Provider(
        key="claude",
        label="Claude (Anthropic)",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-20250514",
        api_key_env=("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
        remote=True,
    ),
    "kimi": Provider(
        key="kimi",
        label="Kimi (Moonshot)",
        base_url="https://api.moonshot.ai/v1",
        default_model="kimi-k2-0711-preview",
        api_key_env=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
        remote=True,
    ),
}


@dataclass
class AiConfig:
    """Resolved configuration for one AI session.

    Build with :meth:`from_env`; never store the key on disk. ``enabled`` follows the product
    decision (ADVANCED + key present); it does not by itself bypass mode gating — the UI still
    asks :class:`~rbgyanx.services.ui_policy.UiPolicy`.
    """

    provider: str = "local"
    base_url: str | None = None  # None => provider default
    model: str | None = None  # None => provider default
    api_key: str | None = field(default=None, repr=False)  # never shown in logs/repr
    temperature: float = 0.2
    max_tokens: int = 1024
    max_retries: int = 2  # self-correction attempts

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            raise ValueError(
                f"unknown AI provider {self.provider!r}; choose from {sorted(PROVIDERS)}"
            )

    @property
    def preset(self) -> Provider:
        return PROVIDERS[self.provider]

    @property
    def resolved_base_url(self) -> str:
        return self.base_url or self.preset.base_url

    @property
    def resolved_model(self) -> str:
        return self.model or self.preset.default_model

    @property
    def is_remote(self) -> bool:
        """True when using this config would send data off the machine."""
        return self.preset.remote

    @property
    def is_ready(self) -> bool:
        """Enough is configured to make a request (local: always; remote: key present)."""
        return (not self.preset.remote) or bool(self.api_key)

    def redacted(self) -> AiConfig:
        """A copy safe to display/log — the key removed."""
        return replace(self, api_key=None)

    @classmethod
    def from_env(
        cls,
        provider: str = "local",
        env: dict[str, str] | None = None,
        **overrides,
    ) -> AiConfig:
        """Resolve a config for ``provider``, pulling the key from the environment only."""
        if provider not in PROVIDERS:
            raise ValueError(f"unknown AI provider {provider!r}; choose from {sorted(PROVIDERS)}")
        key = PROVIDERS[provider].resolve_key(env)
        return cls(provider=provider, api_key=key, **overrides)
