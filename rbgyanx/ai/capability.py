"""
Capability matrix for the governed AI assistant (ADVANCED-only, opt-in, off by default).

Capability is granted on two axes, both enforced here in code rather than by convention:

  Axis 1 - DATA LOCALITY.  A provider is "remote" when using it would move bytes off this
           machine.  Remote providers NEVER receive patient data, under any capability, in
           any install type.  See :func:`effective_remote`: the declarative ``Provider.remote``
           flag is necessary but not sufficient, because ``AiConfig.base_url`` is overridable.

  Axis 2 - INSTALL TYPE.  A frozen binary has no git, no venv and no pytest, so source access,
           test execution and edits are meaningless there as well as unsafe.  CI disables the
           assistant outright.

  Axis 3 - INSTITUTIONAL KILL SWITCH.  ``RBGYANX_AI_DISABLE_REMOTE=1`` or ``ai.disable_remote``
           in a site config file removes every remote provider from the registry before anything
           else can see them.  IT departments must be able to enforce this without editing code.

This module is deliberately dependency-free: it imports no LLM client, no transport and no
network code, so it can be imported and tested in isolation and cannot itself leak anything.

It is a FROZEN file: the assistant must never be able to widen its own permissions.
"""

from __future__ import annotations

import ipaddress
import os
import sys
from enum import Enum
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

__all__ = [
    "InstallType",
    "Capability",
    "Column",
    "Grant",
    "Decision",
    "CAPABILITIES",
    "detect_install_type",
    "is_loopback_host",
    "effective_remote",
    "column_for",
    "is_allowed",
    "scrub_required",
    "remote_disabled",
    "available_providers",
    "granted_capabilities",
]


# --------------------------------------------------------------------------- axes


class InstallType(str, Enum):
    """How this copy of rbGyanX is installed. Detected, never asked of the user."""

    FROZEN = "frozen"  # PyInstaller/Inno binary: no git, no venv, no pytest
    SOURCE = "source"  # git checkout with a dev environment
    CI = "ci"  # continuous integration: assistant fully disabled


class Capability(str, Enum):
    """One row of the capability matrix."""

    EXPLAIN_AGGREGATE = "explain aggregate results"
    EXPLAIN_PATIENT_LEVEL = "explain patient-level results"
    LITERATURE_COMPARE = "literature quick-compare"
    READ_CODE = "read source code"
    MODIFY_CODE = "modify source code"
    RUN_TESTS = "run tests"
    RUN_SYNTHETIC = "run on synthetic data"
    RUN_REAL_PATIENT_DATA = "run on real patient data"
    READ_ERROR = "read error / traceback"


class Column(str, Enum):
    """One column of the capability matrix: an (install type, data locality) pair."""

    FROZEN_REMOTE = "FROZEN+remote"
    FROZEN_LOCAL = "FROZEN+local"
    SOURCE_REMOTE = "SOURCE+remote"
    SOURCE_LOCAL = "SOURCE+local"
    CI = "CI"


class Grant(NamedTuple):
    """One cell. ``scrub`` marks output that must be scrubbed before it is transmitted."""

    allowed: bool
    reason: str
    scrub: bool = False


class Decision(NamedTuple):
    """Result of :func:`is_allowed`. Unpacks as ``(allowed, reason)``."""

    allowed: bool
    reason: str


# --------------------------------------------------------------------------- the table
#
# This is the specification, expressed literally as a table rather than as scattered
# if-statements, so it can be read against the design document line by line.
#
#   Capability                    FROZEN+remote  FROZEN+local  SOURCE+remote  SOURCE+local  CI
#   explain aggregate results          yes           yes            yes           yes       no
#   explain patient-level results      NO            yes            NO            yes       no
#   literature quick-compare           yes           yes            yes           yes       no
#   read source code                   no            no             yes           yes       no
#   modify source code                 no            no             yes           yes       no
#   run tests                          no            no             yes           yes       no
#   run on synthetic data              no            no             yes           yes       no
#   run on real patient data           NO            NO             NO            yes       no
#   read error / traceback         yes, scrubbed  yes, raw     yes, scrubbed   yes, raw     no

_CI_DENIED = Grant(False, "the assistant is disabled entirely in CI environments")

_NEEDS_SOURCE = (
    "this capability requires a SOURCE (git checkout) install; this is a FROZEN binary install"
)
_NEEDS_LOCAL = (
    "this capability requires a local on-machine provider; the selected provider is remote"
)
_NEEDS_BOTH = (
    "this capability requires a SOURCE (git checkout) install AND a local on-machine provider; "
    "this is a FROZEN binary install and the selected provider is remote"
)

_AGGREGATE_OK = "aggregate results carry no patient identifiers"
_PATIENT_OK = "patient-level data stays on this machine"
_LITERATURE_OK = "compares published reference values, not patient data"
_SOURCE_OK = "source is present and carries no patient data"
_EDIT_OK = "edits are reviewed, verified and auto-reverted on failure"
_SYNTHETIC_OK = "synthetic data contains no patient information"

CAPABILITIES: dict[Capability, dict[Column, Grant]] = {
    Capability.EXPLAIN_AGGREGATE: {
        Column.FROZEN_REMOTE: Grant(True, _AGGREGATE_OK),
        Column.FROZEN_LOCAL: Grant(True, _AGGREGATE_OK),
        Column.SOURCE_REMOTE: Grant(True, _AGGREGATE_OK),
        Column.SOURCE_LOCAL: Grant(True, _AGGREGATE_OK),
        Column.CI: _CI_DENIED,
    },
    Capability.EXPLAIN_PATIENT_LEVEL: {
        Column.FROZEN_REMOTE: Grant(False, _NEEDS_LOCAL),
        Column.FROZEN_LOCAL: Grant(True, _PATIENT_OK),
        Column.SOURCE_REMOTE: Grant(False, _NEEDS_LOCAL),
        Column.SOURCE_LOCAL: Grant(True, _PATIENT_OK),
        Column.CI: _CI_DENIED,
    },
    Capability.LITERATURE_COMPARE: {
        Column.FROZEN_REMOTE: Grant(True, _LITERATURE_OK),
        Column.FROZEN_LOCAL: Grant(True, _LITERATURE_OK),
        Column.SOURCE_REMOTE: Grant(True, _LITERATURE_OK),
        Column.SOURCE_LOCAL: Grant(True, _LITERATURE_OK),
        Column.CI: _CI_DENIED,
    },
    Capability.READ_CODE: {
        Column.FROZEN_REMOTE: Grant(False, _NEEDS_SOURCE),
        Column.FROZEN_LOCAL: Grant(False, _NEEDS_SOURCE),
        Column.SOURCE_REMOTE: Grant(True, _SOURCE_OK),
        Column.SOURCE_LOCAL: Grant(True, _SOURCE_OK),
        Column.CI: _CI_DENIED,
    },
    Capability.MODIFY_CODE: {
        Column.FROZEN_REMOTE: Grant(False, _NEEDS_SOURCE),
        Column.FROZEN_LOCAL: Grant(False, _NEEDS_SOURCE),
        Column.SOURCE_REMOTE: Grant(True, _EDIT_OK),
        Column.SOURCE_LOCAL: Grant(True, _EDIT_OK),
        Column.CI: _CI_DENIED,
    },
    Capability.RUN_TESTS: {
        Column.FROZEN_REMOTE: Grant(False, _NEEDS_SOURCE),
        Column.FROZEN_LOCAL: Grant(False, _NEEDS_SOURCE),
        Column.SOURCE_REMOTE: Grant(
            True, "a test run needs a dev environment; output is scrubbed", scrub=True
        ),
        Column.SOURCE_LOCAL: Grant(True, "a test run needs a dev environment"),
        Column.CI: _CI_DENIED,
    },
    Capability.RUN_SYNTHETIC: {
        Column.FROZEN_REMOTE: Grant(False, _NEEDS_SOURCE),
        Column.FROZEN_LOCAL: Grant(False, _NEEDS_SOURCE),
        Column.SOURCE_REMOTE: Grant(True, _SYNTHETIC_OK),
        Column.SOURCE_LOCAL: Grant(True, _SYNTHETIC_OK),
        Column.CI: _CI_DENIED,
    },
    Capability.RUN_REAL_PATIENT_DATA: {
        Column.FROZEN_REMOTE: Grant(False, _NEEDS_BOTH),
        Column.FROZEN_LOCAL: Grant(False, _NEEDS_SOURCE),
        Column.SOURCE_REMOTE: Grant(False, _NEEDS_LOCAL),
        Column.SOURCE_LOCAL: Grant(True, "real patient data never leaves this machine"),
        Column.CI: _CI_DENIED,
    },
    Capability.READ_ERROR: {
        Column.FROZEN_REMOTE: Grant(
            True, "the traceback is scrubbed before transmission", scrub=True
        ),
        Column.FROZEN_LOCAL: Grant(True, "the traceback stays on this machine and is read raw"),
        Column.SOURCE_REMOTE: Grant(
            True, "the traceback is scrubbed before transmission", scrub=True
        ),
        Column.SOURCE_LOCAL: Grant(True, "the traceback stays on this machine and is read raw"),
        Column.CI: _CI_DENIED,
    },
}


# --------------------------------------------------------------------------- axis 2


#: Environment variables whose truthy presence means "this is CI".
_CI_ENV_VARS = (
    "CI",
    "CONTINUOUS_INTEGRATION",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "TF_BUILD",
    "BUILDKITE",
    "CIRCLECI",
    "TRAVIS",
)


def _truthy(value: str | None) -> bool:
    return bool(value) and value.strip().lower() not in {"0", "false", "no", "off", ""}


def detect_install_type(
    env: dict[str, str] | None = None,
    *,
    root: Path | None = None,
    frozen: bool | None = None,
) -> InstallType:
    """Detect how this copy is installed. Never asks the user.

    Precedence is deliberate and most-restrictive-first: CI wins over everything, then a frozen
    binary, then a git checkout. Anything else (e.g. a plain ``pip install`` with no git and no
    ``sys.frozen``) is treated as FROZEN, because that is the more restrictive of the two.
    """
    env = dict(os.environ) if env is None else env
    for name in _CI_ENV_VARS:
        if _truthy(env.get(name)):
            return InstallType.CI

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        return InstallType.FROZEN

    root = Path(__file__).resolve().parents[2] if root is None else Path(root)
    if (root / ".git").exists():
        return InstallType.SOURCE

    # No git and not frozen: a wheel install. Treat as FROZEN, the restrictive default.
    return InstallType.FROZEN


# --------------------------------------------------------------------------- axis 1


def is_loopback_host(host: str | None) -> bool:
    """True only for hosts that are provably on this machine.

    Deliberately an allow-list with no DNS resolution: a name that merely *resolves* to loopback
    today is not a guarantee, and resolving would be network I/O in what must stay a pure
    function. Anything not provably local is treated as remote - fail closed.
    """
    if not host:
        return False
    host = host.strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def effective_remote(provider, base_url: str | None = None) -> bool:
    """Whether using ``provider`` would move bytes off this machine.

    ``Provider.remote`` is declarative, and ``AiConfig.base_url`` can override the preset URL,
    so the flag alone is not a guarantee: a preset marked local but pointed at
    ``https://elsewhere.example/v1`` would otherwise be rated safe for patient data. A provider
    counts as local only when it is flagged local AND its resolved URL is on loopback.

    A LAN endpoint (e.g. an Ollama box at 192.168.1.5) is therefore *remote*: the data does
    leave this machine, which is precisely what axis 1 is about.
    """
    if getattr(provider, "remote", True):
        return True
    url = base_url or getattr(provider, "base_url", "") or ""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return True  # unparseable: fail closed
    return not is_loopback_host(host)


def column_for(install_type: InstallType, remote: bool) -> Column:
    """Map an (install type, data locality) pair onto a matrix column."""
    if install_type is InstallType.CI:
        return Column.CI
    if install_type is InstallType.FROZEN:
        return Column.FROZEN_REMOTE if remote else Column.FROZEN_LOCAL
    return Column.SOURCE_REMOTE if remote else Column.SOURCE_LOCAL


# --------------------------------------------------------------------------- axis 3


def _site_config_paths(env: dict[str, str]) -> list[Path]:
    """Candidate site-config locations, most specific first."""
    paths: list[Path] = []
    explicit = env.get("RBGYANX_SITE_CONFIG")
    if explicit:
        paths.append(Path(explicit))
    if os.name == "nt":
        program_data = env.get("PROGRAMDATA")
        if program_data:
            paths.append(Path(program_data) / "rbGyanX" / "site.yaml")
    else:
        paths.append(Path("/etc/rbgyanx/site.yaml"))
    return paths


def _site_disable_remote(env: dict[str, str]) -> bool:
    """Read ``ai.disable_remote`` from a site config file, if one is present and readable."""
    for path in _site_config_paths(env):
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # an unreadable site config is not a licence to enable remote
        data = None
        try:
            import yaml  # pyyaml is already a core dependency

            data = yaml.safe_load(text)
        except Exception:
            try:
                import json

                data = json.loads(text)
            except Exception:
                data = None
        if isinstance(data, dict):
            ai = data.get("ai")
            if isinstance(ai, dict) and bool(ai.get("disable_remote", False)):
                return True
    return False


def remote_disabled(env: dict[str, str] | None = None) -> bool:
    """True when the institutional kill switch is engaged. Most restrictive source wins."""
    env = dict(os.environ) if env is None else env
    if _truthy(env.get("RBGYANX_AI_DISABLE_REMOTE")):
        return True
    return _site_disable_remote(env)


def available_providers(providers=None, env: dict[str, str] | None = None) -> dict:
    """The provider registry with remote providers removed when the kill switch is engaged.

    Filters before anything else sees the registry, so a disabled remote provider is not merely
    refused at send time - it is not selectable at all.
    """
    if providers is None:
        # Local import keeps this module importable without touching provider presets.
        from rbgyanx.ai.config import PROVIDERS as providers

    if not remote_disabled(env):
        return dict(providers)
    return {k: p for k, p in providers.items() if not effective_remote(p)}


# --------------------------------------------------------------------------- the gate


def is_allowed(
    capability: Capability,
    provider,
    install_type: InstallType,
    *,
    base_url: str | None = None,
    env: dict[str, str] | None = None,
) -> Decision:
    """Whether ``capability`` may run. Returns ``(allowed, reason)``.

    ``reason`` is user-facing and always names which condition failed, so the panel can tell a
    user *why* something is unavailable rather than silently hiding it.
    """
    remote = effective_remote(provider, base_url)

    # Defence in depth: the kill switch removes remote providers from the registry, but if one
    # reaches this function anyway it is refused outright rather than merely rated remote.
    if remote and remote_disabled(env):
        return Decision(
            False,
            "remote providers are disabled by an institutional policy "
            "(RBGYANX_AI_DISABLE_REMOTE or ai.disable_remote in the site config)",
        )

    column = column_for(install_type, remote)
    grant = CAPABILITIES[capability][column]
    return Decision(grant.allowed, grant.reason)


def scrub_required(
    capability: Capability,
    provider,
    install_type: InstallType,
    *,
    base_url: str | None = None,
) -> bool:
    """Whether this capability's output must be scrubbed before it is transmitted."""
    column = column_for(install_type, effective_remote(provider, base_url))
    return CAPABILITIES[capability][column].scrub


def granted_capabilities(
    provider,
    install_type: InstallType,
    *,
    base_url: str | None = None,
    env: dict[str, str] | None = None,
) -> list[Capability]:
    """Every capability currently granted - for display in the panel header."""
    return [
        cap
        for cap in Capability
        if is_allowed(cap, provider, install_type, base_url=base_url, env=env).allowed
    ]
