"""Pluggable TCP/NTCP model registry (CURSOR_FIXES §18)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class TCPModelProtocol(Protocol):
    def compute_tcp_dvh(
        self,
        dvh_df,
        n_fractions: int,
        site_params: Any,
        target_type: str = "GTV",
    ) -> dict:
        ...


class NTCPModelProtocol(Protocol):
    def compute_ntcp_dvh(
        self,
        dvh_df,
        organ_params: Any,
        n_fractions: int = 1,
    ) -> dict:
        ...


_TCP_MODEL_REGISTRY: dict[str, TCPModelProtocol] = {}
_NTCP_MODEL_REGISTRY: dict[str, NTCPModelProtocol] = {}


def register_tcp_model(name: str, instance: TCPModelProtocol) -> None:
    _TCP_MODEL_REGISTRY[name] = instance
    logger.info("Registered TCP model: %s", name)


def register_ntcp_model(name: str, instance: NTCPModelProtocol) -> None:
    _NTCP_MODEL_REGISTRY[name] = instance
    logger.info("Registered NTCP model: %s", name)


def iter_tcp_models() -> dict[str, TCPModelProtocol]:
    return dict(_TCP_MODEL_REGISTRY)


def iter_ntcp_models() -> dict[str, NTCPModelProtocol]:
    return dict(_NTCP_MODEL_REGISTRY)


def clear_registries() -> None:
    """Test helper — reset registered models."""
    _TCP_MODEL_REGISTRY.clear()
    _NTCP_MODEL_REGISTRY.clear()
