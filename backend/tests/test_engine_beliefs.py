"""CDA belief loop wired into the engine — opt-in via JURY_BELIEFS.

Plugin-free: coroutines run via asyncio.run(). Verifies the loop activates only
when enabled and leaves the legacy path untouched when off.
"""
from __future__ import annotations

import asyncio
from collections import deque

from conftest import FakeLLM, fake_embed

from jury import engine
from jury.cases import get_case
from jury.personas import scripted_jurors
from jury.rag import EvidenceRetriever
from jury.state import GameState


def _run(actions):
    async def inner():
        case = get_case()
        retr = EvidenceRetriever(case.evidence, embed_fn=fake_embed).build()
        llm = FakeLLM(retr)
        state = GameState(case_id=case.id, round=1, jurors=scripted_jurors(case), max_rounds=4)
        events: list[dict] = []
        queue = deque(actions)

        async def emit(ev):
            events.append(ev)

        async def get_action():
            return queue.popleft() if queue else {"action": "EXIT"}

        final = await engine.run_game(state, case, llm, emit, get_action)
        return final, events

    return asyncio.run(inner())


def test_beliefs_attached_and_summarized_at_start(monkeypatch):
    monkeypatch.setenv("JURY_BELIEFS", "1")
    final, events = _run([{"action": "EXIT"}])
    start = next(e for e in events if e["type"] == "game_start")
    ai = [j for j in start["jurors"] if not j["is_human"]]
    assert ai and all(j["opinion"] is not None for j in ai)
    assert all(j["belief_stance"] in ("GUILTY", "NOT_GUILTY", "UNDECIDED") for j in ai)
    assert all(j.beliefs is not None for j in final.ai_jurors)


def test_belief_update_events_fire(monkeypatch):
    monkeypatch.setenv("JURY_BELIEFS", "1")
    final, events = _run([{"action": "VOTE", "text": "NOT_GUILTY"} for _ in range(4)])
    updates = [e for e in events if e["type"] == "belief_update"]
    assert updates, "expected at least one juror's belief to move"
    assert all({"juror_id", "opinion", "stance", "by"} <= set(e) for e in updates)


def test_disabled_by_default_keeps_legacy_path(monkeypatch):
    monkeypatch.delenv("JURY_BELIEFS", raising=False)
    final, events = _run([{"action": "EXIT"}])
    assert all(j.beliefs is None for j in final.ai_jurors)
    assert not any(e["type"] == "belief_update" for e in events)
