"""CDA Theory-of-Mind + targeted persuasion wired into the engine (JURY_TOM).

Plugin-free. With JURY_TOM on, speakers read opponents (heuristic fallback via the
stub `tom_read` → belief state) and emit a `strategy` event naming a target.
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


def _run(monkeypatch, actions, tom=True):
    monkeypatch.setenv("JURY_BELIEFS", "1")
    if tom:
        monkeypatch.setenv("JURY_TOM", "1")
    else:
        monkeypatch.delenv("JURY_TOM", raising=False)

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

        final = await engine.run_game(state, case, llm, emit, act)
        return final, events

    return asyncio.run(inner())


def test_strategy_events_fire_with_tom(monkeypatch):
    final, events = _run(monkeypatch, [{"action": "VOTE", "text": "NOT_GUILTY"},
                                       {"action": "VOTE", "text": "NOT_GUILTY"}])
    strat = [e for e in events if e["type"] == "strategy"]
    assert strat, "expected at least one targeted strategy event"
    assert all({"juror_id", "target_id", "tactic"} <= set(e) for e in strat)
    assert any(j.tom for j in final.ai_jurors)                  # ToM guesses persisted


def test_no_strategy_when_tom_off(monkeypatch):
    final, events = _run(monkeypatch, [{"action": "EXIT"}], tom=False)
    assert not any(e["type"] == "strategy" for e in events)
    assert all(not j.tom for j in final.ai_jurors)
