"""LangGraph orchestration variant — must behave like the hand-rolled run_game."""
from __future__ import annotations

import asyncio
from collections import deque

import pytest

pytest.importorskip("langgraph")     # skip locally if not installed; runs in CI

from conftest import FakeLLM, fake_embed   # noqa: E402

from jury import engine                     # noqa: E402
from jury.cases import get_case             # noqa: E402
from jury.graph import run_game_langgraph   # noqa: E402
from jury.personas import scripted_jurors   # noqa: E402
from jury.rag import EvidenceRetriever      # noqa: E402
from jury.state import GameState            # noqa: E402


def _play(runner, actions):
    async def inner():
        case = get_case()
        retr = EvidenceRetriever(case.evidence, embed_fn=fake_embed).build()
        llm = FakeLLM(retr, forced_vote="NOT_GUILTY")
        state = GameState(case_id=case.id, round=1, jurors=scripted_jurors(case), max_rounds=4)
        events: list[dict] = []
        q = deque(actions)

        async def emit(ev):
            events.append(ev)

        async def act():
            return q.popleft()

        final = await runner(state, case, llm, emit, act)
        return final, events

    return asyncio.run(inner())


def test_langgraph_matches_run_game():
    f1, e1 = _play(engine.run_game, [{"action": "VOTE", "text": "NOT_GUILTY"}])
    f2, e2 = _play(run_game_langgraph, [{"action": "VOTE", "text": "NOT_GUILTY"}])
    assert f1.verdict == f2.verdict == "unanimous:NOT_GUILTY"
    for ev in (e1, e2):
        types = [x["type"] for x in ev]
        assert types[0] == "game_start" and types[-1] == "done"
        assert "scorecard" in types


def test_langgraph_exit():
    final, events = _play(run_game_langgraph, [{"action": "EXIT"}])
    assert final.verdict == "exited"
    assert events[-1]["type"] == "done"
