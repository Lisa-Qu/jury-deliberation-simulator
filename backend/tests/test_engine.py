"""End-to-end engine drive with a fake LLM: ReAct event order + both endings.

Plugin-free: async coroutines are run via asyncio.run() so no pytest-asyncio
dependency is required.
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


def _setup(forced_vote):
    case = get_case()
    retr = EvidenceRetriever(case.evidence, embed_fn=fake_embed).build()
    llm = FakeLLM(retr, forced_vote=forced_vote)
    state = GameState(case_id=case.id, round=1, jurors=scripted_jurors(case), max_rounds=4)
    return case, llm, state


def _play(forced_vote, actions):
    async def inner():
        case, llm, state = _setup(forced_vote)
        events: list[dict] = []
        queue = deque(actions)

        async def emit(ev):
            events.append(ev)

        async def get_action():
            return queue.popleft()

        final = await engine.run_game(state, case, llm, emit, get_action)
        return final, events

    return asyncio.run(inner())


def test_react_event_sequence_and_scorecard():
    final, events = _play("NOT_GUILTY", [{"action": "VOTE", "text": "NOT_GUILTY"}])
    types = [e["type"] for e in events]
    for t in ("thinking", "tool_call", "tool_result", "speak"):
        assert t in types, f"missing {t}"
    assert (types.index("thinking") < types.index("tool_call")
            < types.index("tool_result") < types.index("speak"))
    assert types[0] == "game_start"
    assert any(e["type"] == "scorecard" for e in events)
    assert types[-1] == "done"


def test_unanimous_verdict():
    final, events = _play("NOT_GUILTY", [{"action": "VOTE", "text": "NOT_GUILTY"}])
    assert final.verdict == "unanimous:NOT_GUILTY"
    assert any(e["type"] == "tally" and e["status"] == "unanimous" for e in events)


def test_hung_jury_after_max_rounds():
    actions = [{"action": "VOTE", "text": "GUILTY"} for _ in range(4)]
    final, events = _play(None, actions)        # alternating votes → never unanimous
    assert final.verdict == "hung"
    assert final.round == 4


def test_exit_ends_game():
    final, events = _play("GUILTY", [{"action": "EXIT"}])
    assert final.verdict == "exited"


def test_response_phase_triggers():
    # scripted jurors j2/j5 start with responding_score >= RESPOND_THRESHOLD,
    # so a score-gated response turn must fire (speak event carries responding_to).
    final, events = _play("NOT_GUILTY", [{"action": "VOTE", "text": "NOT_GUILTY"}])
    assert any(e["type"] == "speak" and e.get("responding_to") for e in events)
    assert any(it.kind == "respond" for it in final.transcript)


def test_hint_then_vote_loops():
    actions = [{"action": "HINT"}, {"action": "VOTE", "text": "GUILTY"}]
    final, events = _play("GUILTY", actions)
    assert any(e["type"] == "hint" for e in events)
    assert final.verdict == "unanimous:GUILTY"
