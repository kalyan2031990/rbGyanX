"""
Kimi K3 support (phase C): model id, reasoning_effort, and preserved thinking history.

The third of those is the one that fails silently. A reasoning model needs its own previous
assistant message replayed in full - ``reasoning_content`` and ``tool_calls`` included - or it
loses the chain it was part-way through and answers as if starting over. Nothing errors; the
answers just get worse, which is the hardest kind of defect to notice in a tool whose output a
physicist is meant to be able to trust.

So the assertions here are about *verbatim* survival, not merely presence.
"""

from __future__ import annotations

import io
import json

import pytest
from rbgyanx.ai.config import PROVIDERS, REASONING_EFFORTS, AiConfig
from rbgyanx.ai.http_transport import HttpTransport
from rbgyanx.ai.llm_client import LLMClient, LLMError, LLMMessage, LLMRequest


def _urlopen(response_obj, captured):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(json.dumps(response_obj).encode("utf-8"))

    return _fake


#: A K3-shaped assistant turn: thinking, a tool call, and a field this client does not model.
K3_MESSAGE = {
    "role": "assistant",
    "content": "The parotid mean dose is 26.4 Gy.",
    "reasoning_content": "First recall the QUANTEC threshold, then compare 26.4 against it...",
    "tool_calls": [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {"name": "explain_run", "arguments": '{"organ": "Parotid_L"}'},
        }
    ],
    "some_future_field": {"nested": [1, 2, 3]},
}


# ------------------------------------------------------------------------ 1. model id


def test_kimi_preset_targets_k3():
    assert PROVIDERS["kimi"].default_model == "kimi-k3"


def test_kimi_model_reaches_the_request():
    assert AiConfig(provider="kimi").resolved_model == "kimi-k3"


def test_an_explicit_model_still_overrides_the_preset():
    assert AiConfig(provider="kimi", model="kimi-k2-0711-preview").resolved_model == (
        "kimi-k2-0711-preview"
    )


# ------------------------------------------------------------- 2. reasoning_effort


def test_default_effort_is_max():
    assert AiConfig(provider="kimi").reasoning_effort == "max"
    assert AiConfig(provider="kimi").resolved_reasoning_effort == "max"


@pytest.mark.parametrize("effort", REASONING_EFFORTS)
def test_every_documented_effort_is_accepted(effort):
    assert AiConfig(provider="kimi", reasoning_effort=effort).resolved_reasoning_effort == effort


def test_an_unknown_effort_is_rejected_at_construction():
    with pytest.raises(ValueError, match="unknown reasoning_effort"):
        AiConfig(provider="kimi", reasoning_effort="turbo")


def test_effort_is_not_sent_to_providers_that_do_not_declare_support():
    """An unknown request field is not a harmless extra; some endpoints reject the request."""
    assert AiConfig(provider="claude").resolved_reasoning_effort is None
    assert AiConfig(provider="local").resolved_reasoning_effort is None


def test_effort_appears_in_the_request_body(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": {"content": "ok"}}]}, captured),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=HttpTransport())
    client.complete([LLMMessage("user", "explain")])
    assert captured["body"]["reasoning_effort"] == "max"
    assert captured["body"]["model"] == "kimi-k3"


def test_effort_is_absent_from_the_body_for_other_providers(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": {"content": "ok"}}]}, captured),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="claude", api_key="k"), transport=HttpTransport())
    client.complete([LLMMessage("user", "explain")])
    assert "reasoning_effort" not in captured["body"]


def test_a_chosen_effort_reaches_the_wire(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": {"content": "ok"}}]}, captured),
        raising=True,
    )
    client = LLMClient(
        AiConfig(provider="kimi", api_key="sk-x", reasoning_effort="low"), transport=HttpTransport()
    )
    client.complete([LLMMessage("user", "explain")])
    assert captured["body"]["reasoning_effort"] == "low"


# ------------------------------------------------- 3. preserved thinking history


def test_the_response_carries_the_complete_assistant_message(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": K3_MESSAGE}]}, captured),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=HttpTransport())
    resp = client.complete([LLMMessage("user", "explain")])

    assert resp.message is not None
    assert resp.reasoning_content == K3_MESSAGE["reasoning_content"]
    assert resp.tool_calls == tuple(K3_MESSAGE["tool_calls"])


def test_the_assistant_message_round_trips_verbatim(monkeypatch):
    """The acceptance criterion: what came back is what goes out again, byte for byte."""
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": K3_MESSAGE}]}, captured),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=HttpTransport())
    resp = client.complete([LLMMessage("user", "explain")])

    replayed = resp.message.to_wire()
    assert replayed == K3_MESSAGE, "the assistant turn must be replayed unchanged"


def test_a_replayed_turn_reaches_the_next_request_intact(monkeypatch):
    """Multi-turn: the second call must carry the first turn's thinking and tool calls."""
    first: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": K3_MESSAGE}]}, first),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=HttpTransport())
    resp = client.complete([LLMMessage("user", "explain")])

    second: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": {"content": "done"}}]}, second),
        raising=True,
    )
    client.complete([LLMMessage("user", "explain"), resp.message, LLMMessage("user", "and now?")])

    sent = second["body"]["messages"]
    assert sent[1] == K3_MESSAGE, "the assistant turn was altered on replay"
    assert sent[1]["reasoning_content"] == K3_MESSAGE["reasoning_content"]
    assert sent[1]["tool_calls"] == K3_MESSAGE["tool_calls"]


def test_fields_this_client_does_not_model_survive(monkeypatch):
    """Preservation by construction, not by enumeration: unknown keys must not be dropped."""
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": K3_MESSAGE}]}, captured),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=HttpTransport())
    resp = client.complete([LLMMessage("user", "explain")])
    assert resp.message.to_wire()["some_future_field"] == {"nested": [1, 2, 3]}


def test_a_tool_call_only_turn_is_not_treated_as_empty(monkeypatch):
    """content is null when the model only wants a tool run; rejecting that breaks tool use."""
    tool_only = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "run_tests", "arguments": "{}"}}
        ],
    }
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": tool_only}]}, captured),
        raising=True,
    )
    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=HttpTransport())
    resp = client.complete([LLMMessage("user", "run the controls")])
    assert resp.tool_calls is not None
    assert resp.message.to_wire()["tool_calls"] == tool_only["tool_calls"]


def test_a_genuinely_empty_message_is_still_an_error(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen({"choices": [{"message": {"role": "assistant", "content": ""}}]}, captured),
        raising=True,
    )
    with pytest.raises(LLMError):
        HttpTransport().complete_message(
            LLMRequest(messages=[LLMMessage("user", "hi")], model="kimi-k3"),
            base_url="https://api.moonshot.ai/v1",
            api_key="sk-x",
        )


# ------------------------------------------------------------- message serialisation


def test_a_plain_message_serialises_without_extra_keys():
    assert LLMMessage("user", "hi").to_wire() == {"role": "user", "content": "hi"}


def test_reasoning_and_calls_serialise_when_set_without_a_raw_message():
    msg = LLMMessage("assistant", "text", reasoning_content="thinking", tool_calls=({"id": "c1"},))
    wire = msg.to_wire()
    assert wire["reasoning_content"] == "thinking"
    assert wire["tool_calls"] == [{"id": "c1"}]


def test_to_wire_returns_a_copy_not_the_stored_dict():
    msg = LLMMessage.from_provider(dict(K3_MESSAGE))
    wire = msg.to_wire()
    wire["content"] = "mutated"
    assert msg.to_wire()["content"] == K3_MESSAGE["content"]


def test_content_parts_are_flattened_for_text_but_raw_is_untouched():
    parts = {"role": "assistant", "content": [{"type": "text", "text": "a"}, {"text": "b"}]}
    msg = LLMMessage.from_provider(parts)
    assert msg.content == "ab"
    assert msg.to_wire() == parts


# ------------------------------------------------------------------ compatibility


def test_a_transport_without_complete_message_still_works():
    """Older transports return text only; the client must not require the new method."""

    class TextOnly:
        def complete(self, request, *, base_url, api_key):
            return "plain reply"

    client = LLMClient(AiConfig(provider="kimi", api_key="sk-x"), transport=TextOnly())
    resp = client.complete([LLMMessage("user", "hi")])
    assert resp.text == "plain reply"
    assert resp.message.to_wire() == {"role": "assistant", "content": "plain reply"}


def test_kimi_remains_a_remote_provider():
    """K3 is hosted. Nothing in this phase may soften that."""
    assert AiConfig(provider="kimi").is_remote is True
