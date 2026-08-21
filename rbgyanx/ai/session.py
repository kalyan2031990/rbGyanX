"""
Assistant session state, kept out of the Qt layer so it can be tested without a display.

The panel needs to answer one question at a glance: *what is the assistant allowed to do right
now?* That answer depends on the provider, the install type and the kill switch, and it changes
when the user switches provider - so it is computed here and rendered by the panel, rather than
being assembled inline in a widget where it could not be tested.

The feature is opt-in and off by default: :attr:`AssistantSession.tools_enabled` starts False,
so a fresh install has the tool layer inert until someone deliberately turns it on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rbgyanx.ai.capability import (
    Capability,
    InstallType,
    available_providers,
    detect_install_type,
    effective_remote,
    granted_capabilities,
    is_allowed,
    remote_disabled,
)
from rbgyanx.ai.config import PROVIDERS, Provider

__all__ = ["AssistantSession", "KILL_SWITCH_NOTE", "TOOLS_OFF_NOTE"]

KILL_SWITCH_NOTE = (
    "Remote providers are disabled by institutional policy "
    "(RBGYANX_AI_DISABLE_REMOTE, or ai.disable_remote in the site config)."
)

TOOLS_OFF_NOTE = "Assistant tools are off. Enable them to let the assistant read code or run tests."


@dataclass
class AssistantSession:
    """What the assistant may do right now, and why."""

    provider_key: str = "local"
    base_url: str | None = None
    install_type: InstallType = field(default_factory=detect_install_type)
    #: Opt-in, off by default. The panel exposes this as an explicit checkbox.
    tools_enabled: bool = False
    synthetic_roots: tuple[Path, ...] = ()
    env: dict[str, str] | None = None

    # ------------------------------------------------------------------ providers

    def selectable_providers(self) -> dict[str, Provider]:
        """The providers the user may choose, after the kill switch has filtered them."""
        return available_providers(PROVIDERS, env=self.env)

    @property
    def provider(self) -> Provider:
        providers = self.selectable_providers()
        if self.provider_key in providers:
            return providers[self.provider_key]
        # The selected provider has been removed by policy: fall back to a local one.
        return next(iter(providers.values())) if providers else PROVIDERS["local"]

    @property
    def remote(self) -> bool:
        return effective_remote(self.provider, self.base_url)

    @property
    def kill_switch_engaged(self) -> bool:
        return remote_disabled(self.env)

    # ---------------------------------------------------------------- capabilities

    def granted(self) -> list[Capability]:
        return granted_capabilities(
            self.provider, self.install_type, base_url=self.base_url, env=self.env
        )

    def explain(self, capability: Capability) -> str:
        """The reason string for one capability, granted or not."""
        return is_allowed(
            capability, self.provider, self.install_type, base_url=self.base_url, env=self.env
        ).reason

    def available_tools(self) -> list[str]:
        """Tool names the assistant may invoke. Empty while the feature is switched off."""
        if not self.tools_enabled:
            return []
        from rbgyanx.ai.tools import REGISTRY, ToolContext

        return REGISTRY.available(
            ToolContext(
                self.provider,
                self.install_type,
                base_url=self.base_url,
                env=self.env,
                synthetic_roots=self.synthetic_roots,
            )
        )

    # -------------------------------------------------------------------- display

    def locality_text(self) -> str:
        """One line on where the data goes. This is the sentence that matters most."""
        if not self.remote:
            return "Local endpoint - nothing leaves this machine."
        label = getattr(self.provider, "label", self.provider_key)
        if not getattr(self.provider, "remote", True):
            # Flagged local but pointed off-machine: say so plainly rather than trusting the flag.
            return (
                f"Treated as REMOTE - the endpoint {self.base_url!r} is not on this machine, "
                "so patient data is withheld."
            )
        return f"Remote ({label}) - sends leave this machine. Patient data is withheld."

    def header_text(self) -> str:
        """Provider, install type and granted capabilities, for the panel header."""
        granted = self.granted()
        if self.install_type is InstallType.CI:
            capabilities = "none (CI)"
        elif not granted:
            capabilities = "none"
        else:
            capabilities = ", ".join(c.value for c in granted)
        label = getattr(self.provider, "label", self.provider_key)
        return (
            f"Provider: {label} ({'remote' if self.remote else 'local'})  |  "
            f"Install: {self.install_type.value.upper()}  |  "
            f"Allowed: {capabilities}"
        )

    def notes(self) -> list[str]:
        """Anything the user should know that the header line cannot carry."""
        out: list[str] = []
        if self.kill_switch_engaged:
            out.append(KILL_SWITCH_NOTE)
        if not self.tools_enabled:
            out.append(TOOLS_OFF_NOTE)
        if self.install_type is InstallType.CI:
            out.append("Running under CI: the assistant is disabled entirely.")
        return out
