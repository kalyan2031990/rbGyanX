"""
Live-provider smoke test (phase E). Opt-in; skipped unless RBGYANX_LIVE_LLM_TEST=1.

Everything else in this suite is unit-level with mocked transports. That proves the gate logic
and proves nothing about the wiring: whether the key is read from the right variable, whether
the endpoint accepts the request shape, whether the response parses, whether an audit record
lands. Those only fail against a real endpoint, and they fail on the day someone first uses it.

    # one round trip per provider that is actually configured
    RBGYANX_LIVE_LLM_TEST=1 python -m pytest tests/test_ai_live_provider.py -v

    # a specific provider only
    RBGYANX_LIVE_LLM_TEST=1 RBGYANX_LIVE_LLM_PROVIDERS=kimi python -m pytest \\
        tests/test_ai_live_provider.py -v

A provider with no key is skipped, not failed - a missing key is a configuration fact, not a
defect. This test SENDS DATA to whichever remote providers are configured, which is why it is
off by default: a test suite must not transmit anything the person running it did not ask for.
The text sent is a fixed, patient-free sentence.
"""

from __future__ import annotations

import os

import pytest
from rbgyanx.ai.audit import audit_path, read_records
from rbgyanx.ai.capability import detect_install_type, effective_remote
from rbgyanx.ai.config import PROVIDERS, AiConfig
from rbgyanx.ai.context import build_system_prompt
from rbgyanx.ai.http_transport import HttpTransport
from rbgyanx.ai.llm_client import LLMClient, LLMMessage

LIVE_ENV_VAR = "RBGYANX_LIVE_LLM_TEST"
PROVIDERS_ENV_VAR = "RBGYANX_LIVE_LLM_PROVIDERS"

#: Deliberately free of anything resembling patient data, in any provider's logs.
PROMPT = "In one sentence, what does the LKB model's TD50 parameter represent?"

pytestmark = pytest.mark.skipif(
    os.environ.get(LIVE_ENV_VAR) != "1",
    reason=f"live provider test is opt-in; set {LIVE_ENV_VAR}=1 to run it",
)


def _selected() -> list[str]:
    chosen = os.environ.get(PROVIDERS_ENV_VAR)
    if chosen:
        return [k.strip() for k in chosen.split(",") if k.strip()]
    return sorted(PROVIDERS)


@pytest.fixture(params=sorted(PROVIDERS))
def provider_key(request):
    key = request.param
    if key not in _selected():
        pytest.skip(f"{key} not selected via {PROVIDERS_ENV_VAR}")
    cfg = AiConfig.from_env(key)
    if not cfg.is_ready:
        pytest.skip(f"{key} has no API key configured; that is a config fact, not a failure")
    return key


def test_one_round_trip_reaches_the_provider_and_parses(provider_key, tmp_path, monkeypatch):
    """Build a request, transmit it, parse the response, confirm the audit record landed."""
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))

    cfg = AiConfig.from_env(provider_key)
    client = LLMClient(cfg, transport=HttpTransport(timeout=120.0))

    before = len(read_records(audit_path()))
    response = client.complete(
        [LLMMessage("system", build_system_prompt()), LLMMessage("user", PROMPT)],
        capability="live smoke test",
    )

    # 1. a response came back and parsed
    assert response.text.strip(), f"{provider_key} returned an empty response"
    assert response.model == cfg.resolved_model

    # 2. the complete assistant turn is available for replay
    assert response.message is not None
    replayed = response.message.to_wire()
    assert replayed.get("role") == "assistant"

    # 3. the audit record landed, and carries no payload
    records = read_records(audit_path())
    assert len(records) == before + 1, "no audit record was written for a live transmission"
    record = records[-1]
    assert record["provider"] == provider_key
    assert record["capability"] == "live smoke test"
    assert record["install_type"] == detect_install_type().value
    assert record["payload_bytes"] > 0
    assert len(record["payload_sha256"]) == 64
    raw = audit_path().read_text(encoding="utf-8")
    assert PROMPT not in raw, "the audit log persisted the payload"


def test_the_remote_flag_recorded_matches_the_endpoint(provider_key, tmp_path, monkeypatch):
    """The audit trail is evidence: its remote flag has to match where the data actually went."""
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))

    cfg = AiConfig.from_env(provider_key)
    client = LLMClient(cfg, transport=HttpTransport(timeout=120.0))
    client.complete([LLMMessage("user", PROMPT)], capability="live smoke test")

    record = read_records(audit_path())[-1]
    assert record["remote"] is effective_remote(cfg.preset, cfg.base_url)


def test_reasoning_fields_survive_when_the_provider_sends_them(provider_key, tmp_path, monkeypatch):
    """Not every provider returns reasoning; when one does, it must reach the caller intact."""
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))

    cfg = AiConfig.from_env(provider_key)
    client = LLMClient(cfg, transport=HttpTransport(timeout=120.0))
    response = client.complete([LLMMessage("user", PROMPT)], capability="live smoke test")

    raw = response.message.to_wire()
    if "reasoning_content" in raw:
        assert response.reasoning_content == raw["reasoning_content"]
    if "tool_calls" in raw:
        assert response.tool_calls == tuple(raw["tool_calls"])


def test_a_second_turn_replays_the_first_verbatim(provider_key, tmp_path, monkeypatch):
    """Multi-turn against a real endpoint: the replayed turn must be accepted, not rejected."""
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))

    cfg = AiConfig.from_env(provider_key)
    client = LLMClient(cfg, transport=HttpTransport(timeout=120.0))

    first = client.complete([LLMMessage("user", PROMPT)], capability="live smoke test")
    second = client.complete(
        [
            LLMMessage("user", PROMPT),
            first.message,
            LLMMessage("user", "And in one more sentence, why does it matter clinically?"),
        ],
        capability="live smoke test",
    )
    assert second.text.strip(), "the provider rejected or ignored the replayed assistant turn"
    assert len(read_records(audit_path())) == 2
