"""Streaming (JURY_STREAM) + reflection (JURY_REFLECT) engine paths — plugin-free."""
from __future__ import annotations

import asyncio
from collections import deque

from conftest import FakeLLM, fake_embed

from jury import engine
from jury.cases import get_case
from jury.personas import scripted_jurors
from jury.rag import EvidenceRetriever
from jury.state import GameState


def _run(monkeypatch, env, actions):
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    async def inner():
        case = get_case()
        retr = EvidenceRetriever(case.evidence, embed_fn=fake_embed).build()
        llm = FakeLLM(retr)
        state = GameState(case_id=case.id, round=1, jurors=scripted_jurors(case), max_rounds=2)
        events: list[dict] = []
        q = deque(actions)

        async def emit(ev):
            events.append(ev)

        async def act():
            return q.popleft() if q else {"action": "EXIT"}

        await engine.run_game(state, case, llm, emit, act)
        return events

    return asyncio.run(inner())


def test_streaming_replaces_speak_with_deltas(monkeypatch):
    types = [e["type"] for e in _run(monkeypatch, {"JURY_STREAM": "1"}, [{"action": "EXIT"}])]
    assert "speak_start" in types and "speak_delta" in types and "speak_end" in types
    assert "speak" not in types                          # the trio replaces the single event


def test_no_streaming_by_default(monkeypatch):
    monkeypatch.delenv("JURY_STREAM", raising=False)
    types = [e["type"] for e in _run(monkeypatch, {}, [{"action": "EXIT"}])]
    assert "speak" in types and "speak_delta" not in types


def test_reflection_events_fire(monkeypatch):
    events = _run(monkeypatch, {"JURY_REFLECT": "1"}, [{"action": "EXIT"}])
    assert any(e["type"] == "reflection" for e in events)
