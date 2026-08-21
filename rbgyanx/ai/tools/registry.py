"""
Tool registry. Every tool the assistant can invoke passes through here, and only here.

The gate is structural rather than advisory: :func:`invoke` consults
:func:`rbgyanx.ai.capability.is_allowed` *before* the tool function is called, so a refused tool
never runs at all. A tool cannot opt out, because a tool never receives control until the
registry has decided. Refusals return the capability layer's own reason string, which names the
condition that failed, rather than a generic "not permitted".

This module is FROZEN. Freezing the policy in ``capability.py`` while leaving the code that
consults it editable would achieve nothing: an agent that can edit the caller does not need to
edit the policy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rbgyanx.ai.capability import (
    Capability,
    InstallType,
    effective_remote,
    is_allowed,
    scrub_required,
)

__all__ = [
    "ToolContext",
    "ToolResult",
    "Tool",
    "ToolRegistry",
    "REGISTRY",
    "register",
    "invoke",
]


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool needs to know about *where it is running*, not what it is doing."""

    provider: object  # a rbgyanx.ai.config.Provider
    install_type: InstallType
    base_url: str | None = None
    env: dict[str, str] | None = None
    #: Directories the user has explicitly declared to contain synthetic data.
    synthetic_roots: tuple[Path, ...] = ()

    @property
    def remote(self) -> bool:
        return effective_remote(self.provider, self.base_url)

    @property
    def provider_key(self) -> str:
        return str(getattr(self.provider, "key", "unknown"))


@dataclass(frozen=True)
class ToolResult:
    """Outcome of an invocation. A refusal is a result, not an exception."""

    ok: bool
    tool: str
    capability: str
    output: str = ""
    reason: str = ""
    findings_redacted: int = 0
    #: False when the output must not be forwarded to a remote provider.
    transmittable: bool = True
    metadata: dict = field(default_factory=dict)

    @classmethod
    def refused(cls, tool: str, capability: str, reason: str) -> ToolResult:
        return cls(ok=False, tool=tool, capability=capability, reason=reason, transmittable=False)


@dataclass(frozen=True)
class Tool:
    """A callable plus the capability it requires. The pairing is declared, never inferred."""

    name: str
    capability: Capability
    func: Callable[..., ToolResult]
    description: str = ""
    #: True when the tool reads or writes real patient data and must be gated additionally.
    touches_patient_data: bool = False


class ToolRegistry:
    """Name -> Tool, with the capability check wrapped around every invocation."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool
        return tool

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def available(self, ctx: ToolContext) -> list[str]:
        """Tools currently permitted - for showing the user what the assistant may do now."""
        return [
            name
            for name, tool in sorted(self._tools.items())
            if is_allowed(
                tool.capability,
                ctx.provider,
                ctx.install_type,
                base_url=ctx.base_url,
                env=ctx.env,
            ).allowed
        ]

    def invoke(self, name: str, ctx: ToolContext, /, **kwargs) -> ToolResult:
        """Check the capability, then run the tool. Never the other way round."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.refused(name, "", f"no such tool: {name!r}")

        decision = is_allowed(
            tool.capability,
            ctx.provider,
            ctx.install_type,
            base_url=ctx.base_url,
            env=ctx.env,
        )
        if not decision.allowed:
            return ToolResult.refused(tool.name, tool.capability.value, decision.reason)

        result = tool.func(ctx, **kwargs)

        # A tool may not quietly widen its own transmissibility: if the matrix says this
        # capability's output needs scrubbing on this provider, that verdict stands.
        if result.ok and scrub_required(
            tool.capability, ctx.provider, ctx.install_type, base_url=ctx.base_url
        ):
            object.__setattr__(result, "metadata", {**result.metadata, "scrub_required": True})
        return result


#: The process-wide registry. Tools register themselves on import of :mod:`rbgyanx.ai.tools`.
REGISTRY = ToolRegistry()


def register(tool: Tool) -> Tool:
    return REGISTRY.register(tool)


def invoke(name: str, ctx: ToolContext, /, **kwargs) -> ToolResult:
    return REGISTRY.invoke(name, ctx, **kwargs)
