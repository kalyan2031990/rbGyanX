"""
Tool layer for the governed AI assistant.

Importing this package registers every tool. Nothing here decides what is permitted - that is
:mod:`rbgyanx.ai.capability`, consulted by :mod:`rbgyanx.ai.tools.registry` before any tool
function is entered.
"""

from __future__ import annotations

from rbgyanx.ai.tools.edit import Snapshot, edit_code
from rbgyanx.ai.tools.paths import PathRefused, is_within, resolve_within
from rbgyanx.ai.tools.readonly import (
    explain_run,
    read_code,
    read_error,
    run_synthetic,
    run_tests,
)
from rbgyanx.ai.tools.registry import (
    REGISTRY,
    Tool,
    ToolContext,
    ToolRegistry,
    ToolResult,
    invoke,
    register,
)

__all__ = [
    "REGISTRY",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "invoke",
    "register",
    "PathRefused",
    "is_within",
    "resolve_within",
    "read_code",
    "read_error",
    "run_tests",
    "run_synthetic",
    "explain_run",
    "edit_code",
    "Snapshot",
]
