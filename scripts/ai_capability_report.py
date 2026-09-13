#!/usr/bin/env python3
"""
Print what the AI assistant is allowed to do, for the currently configured provider.

    python scripts/ai_capability_report.py                    # the default (local) provider
    python scripts/ai_capability_report.py --provider kimi    # what Kimi K3 will see
    python scripts/ai_capability_report.py --all              # every provider, side by side

Run this BEFORE starting a cohort run, not after. The point is that "patient-level explanation
is refused on a remote provider" should be something you knew going in, rather than something
you discover halfway through and mistake for a bug.

Everything printed is read from the implemented capability matrix. Nothing here restates the
design from prose, so it cannot drift away from what the code actually does.
"""

from __future__ import annotations

import argparse
import os
import sys

from rbgyanx.ai.capability import (
    Capability,
    InstallType,
    available_providers,
    detect_install_type,
    effective_remote,
    is_allowed,
    remote_disabled,
)
from rbgyanx.ai.config import PROVIDERS, AiConfig


def _row(capability: Capability, cfg: AiConfig, install: InstallType) -> tuple[str, str, str]:
    decision = is_allowed(capability, cfg.preset, install, base_url=cfg.base_url)
    return capability.value, ("GRANTED" if decision.allowed else "DENIED"), decision.reason


def report(provider_key: str, install: InstallType) -> str:
    cfg = AiConfig.from_env(provider_key)
    remote = effective_remote(cfg.preset, cfg.base_url)

    lines = [
        "=" * 78,
        f"rbGyanX AI assistant - what {cfg.preset.label} is allowed to do",
        "=" * 78,
        f"provider        : {provider_key}  ({cfg.preset.label})",
        f"model           : {cfg.resolved_model}",
        f"endpoint        : {cfg.resolved_base_url}",
        f"data locality   : {'REMOTE - data leaves this machine' if remote else 'LOCAL - nothing leaves this machine'}",
        f"install type    : {install.value.upper()}",
        f"API key present : {'yes' if cfg.api_key else 'no'}",
        f"ready to send   : {'yes' if cfg.is_ready else 'no'}",
    ]
    if cfg.resolved_reasoning_effort:
        lines.append(f"reasoning effort: {cfg.resolved_reasoning_effort}")
    if remote_disabled():
        lines.append("kill switch     : ENGAGED - remote providers are disabled by policy")
    lines += ["", "-" * 78, ""]

    rows = [_row(c, cfg, install) for c in Capability]
    width = max(len(r[0]) for r in rows)
    for name, verdict, reason in rows:
        lines.append(f"  {name:<{width}}  {verdict:<8}  {reason}")

    granted = [r[0] for r in rows if r[1] == "GRANTED"]
    denied = [r[0] for r in rows if r[1] == "DENIED"]
    lines += [
        "",
        "-" * 78,
        "",
        f"GRANTED ({len(granted)}): " + (", ".join(granted) or "none"),
        f"DENIED  ({len(denied)}): " + (", ".join(denied) or "none"),
        "",
    ]
    if remote and denied:
        lines += [
            "A denial on a remote provider is correct behaviour, not a defect. To explain",
            "patient-level results, switch to the local provider; nothing else needs to change.",
            "",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the granted/denied capability table for a provider."
    )
    parser.add_argument("--provider", default=os.environ.get("RBGYANX_AI_PROVIDER", "local"))
    parser.add_argument("--all", action="store_true", help="report on every selectable provider")
    parser.add_argument(
        "--install",
        choices=[t.value for t in InstallType],
        default=None,
        help="override the detected install type (for checking another deployment)",
    )
    args = parser.parse_args(argv)

    install = InstallType(args.install) if args.install else detect_install_type()

    if args.all:
        keys = list(available_providers(PROVIDERS))
    else:
        if args.provider not in PROVIDERS:
            print(
                f"unknown provider {args.provider!r}; choose from {sorted(PROVIDERS)}",
                file=sys.stderr,
            )
            return 2
        keys = [args.provider]

    for key in keys:
        print(report(key, install))
    return 0


if __name__ == "__main__":
    sys.exit(main())
