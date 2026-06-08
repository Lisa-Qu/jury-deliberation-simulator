"""Async, event-driven deliberation engine.

`run_game` is an async coroutine that drives the jury room and pushes structured
events through `emit`. When it's the human's turn it pauses on
`await get_human_action()` until the server feeds an action in from the client.
Blocking LLM work runs in threads (`asyncio.to_thread`); events stream out with a
small delay so the UI animates naturally.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from typing import Awaitable, Callable

from . import eval as evaluation
from .cases import Case
from .state import HUMAN_ID, GameState, JurorState, TranscriptEntry, Vote

Emit = Callable[[dict], Awaitable[None]]
GetAction = Callable[[], Awaitable[dict]]

HUMAN_OPTS = ["SPEAK", "VOTE", "REJECT", "EXIT", "HINT"]
STREAM_DELAY = float(os.environ.get("JURY_STREAM_DELAY", "0.35"))
# A juror whose responding_score crosses this threshold gets to interject a
# direct response to the previous speaker — score-gated interaction scheduling.
RESPOND_THRESHOLD = float(os.environ.get("JURY_RESPOND_THRESHOLD", "0.6"))


# --------------------------------------------------------------------------- #
# Synchronous turn computation (runs in a thread). Returns ordered events so the
# async layer can stream thinking → tool_call → tool_result → speak in order.
# --------------------------------------------------------------------------- #
def _tool_events(juror: JurorState, collected: list) -> list[dict]:
    name = juror.persona.name
    evs: list[dict] = []
    for kind, payload in collected:
        if kind == "call":
            evs.append({"type": "tool_call", "juror_id": juror.id, "name": name,
                        "tool": "lookup_evidence", "query": payload})
        else:
            evs.append({"type": "tool_result", "juror_id": juror.id, "name": name,
                        "evidence_ids": payload.ids, "snippets": payload.snippets,
                        "scores": [round(s, 3) for s in payload.scores]})
    return evs


def compute_juror_turn(juror: JurorState, state: GameState, case: Case, llm):
    name = juror.persona.name
    thought = llm.think(juror, state, case)
    events: list[dict] = [
        {"type": "thinking", "juror_id": juror.id, "name": name, "text": thought}]

    collected: list[tuple[str, object]] = []
    text, vote = llm.speak(
        juror, state, case,
        on_tool_call=lambda q: collected.append(("call", q)),
        on_tool_result=lambda h: collected.append(("result", h)),
    )
    events.extend(_tool_events(juror, collected))
    events.append({"type": "speak", "juror_id": juror.id, "name": name,
                   "text": text, "vote": vote})
    events.extend(llm.drain_errors())
    return events, replace(juror, vote=vote, inner_reasoning=thought), text, vote


def compute_respond_turn(juror: JurorState, target_name: str, target_text: str,
                         state: GameState, case: Case, llm):
    name = juror.persona.name
    thought = llm.think(juror, state, case)
    events: list[dict] = [
        {"type": "thinking", "juror_id": juror.id, "name": name, "text": thought}]

    collected: list[tuple[str, object]] = []
    text, vote = llm.respond(
        juror, state, case, target_name, target_text,
        on_tool_call=lambda q: collected.append(("call", q)),
        on_tool_result=lambda h: collected.append(("result", h)),
    )
    events.extend(_tool_events(juror, collected))
    events.append({"type": "speak", "juror_id": juror.id, "name": name,
                   "text": text, "vote": vote, "responding_to": target_name})
    events.extend(llm.drain_errors())
    return events, replace(juror, vote=vote, inner_reasoning=thought), text, vote


# --------------------------------------------------------------------------- #
# Score dynamics — keep speaking order shifting round to round.
# --------------------------------------------------------------------------- #
def _after_speaker(state: GameState, speaker_id: str) -> GameState:
    out = state
    for j in state.ai_jurors:
        if j.id == speaker_id:
            out = out.update_juror(j.id, speaking_score=max(0.1, j.speaking_score * 0.6))
        else:
            out = out.update_juror(j.id, responding_score=min(1.0, j.responding_score + 0.08))
    return out


# --------------------------------------------------------------------------- #
# Phases.
# --------------------------------------------------------------------------- #
async def _ai_phase(state: GameState, case: Case, llm, emit: Emit) -> GameState:
    order = sorted(state.ai_jurors, key=lambda j: -j.speaking_score)
    for j in order:
        juror = state.get_juror(j.id)
        events, new_j, text, vote = await asyncio.to_thread(
            compute_juror_turn, juror, state, case, llm
        )
        for ev in events:
            await emit(ev)
            await asyncio.sleep(STREAM_DELAY)
        state = state.replace_juror(new_j.id, new_j)
        state = state.add_entry(TranscriptEntry(
            new_j.id, new_j.persona.name, "speak", text, vote, state.round))
        state = _after_speaker(state, new_j.id)
    return state


async def _response_phase(state: GameState, case: Case, llm, emit: Emit) -> GameState:
    """Score-gated interaction: the eligible juror with the highest
    responding_score (above RESPOND_THRESHOLD, not the last speaker) interjects
    a direct response to the previous statement."""
    if not state.transcript:
        return state
    last = state.transcript[-1]
    eligible = [j for j in state.ai_jurors
                if j.responding_score >= RESPOND_THRESHOLD and j.id != last.juror_id]
    if not eligible:
        return state
    responder = max(eligible, key=lambda j: j.responding_score)
    events, new_j, text, vote = await asyncio.to_thread(
        compute_respond_turn, state.get_juror(responder.id),
        last.name, last.text, state, case, llm)
    for ev in events:
        await emit(ev)
        await asyncio.sleep(STREAM_DELAY)
    state = state.replace_juror(new_j.id, new_j)
    state = state.add_entry(TranscriptEntry(
        new_j.id, new_j.persona.name, "respond", text, vote, state.round))
    return state.update_juror(new_j.id, responding_score=max(0.1, responder.responding_score * 0.5))


async def _human_phase(state, case, llm, emit, get_action) -> tuple[GameState, bool]:
    """Loop human micro-actions until a terminal one (VOTE/REJECT/EXIT)."""
    while True:
        await emit({"type": "awaiting_human", "options": HUMAN_OPTS, "round": state.round})
        action = await get_action()
        a = (action.get("action") or "").upper()
        txt = (action.get("text") or "").strip()
        await emit({"type": "human_action", "action": a, "text": txt})

        if a == "HINT":
            hint = await asyncio.to_thread(evaluation.coach_hint, state, case, llm)
            await emit({"type": "hint", "text": hint})
            for ev in llm.drain_errors():
                await emit(ev)
            continue
        if a == "SPEAK":
            human = state.human
            state = state.add_entry(TranscriptEntry(
                HUMAN_ID, "You", "human", txt or "(stays silent)", human.vote, state.round))
            for j in state.ai_jurors:  # human input perks up responders
                state = state.update_juror(
                    j.id, responding_score=min(1.0, j.responding_score + 0.05))
            continue
        if a == "VOTE":
            v: Vote = txt.upper().replace("-", "_")  # type: ignore[assignment]
            if v not in ("GUILTY", "NOT_GUILTY"):
                v = "UNDECIDED"
            state = state.update_juror(HUMAN_ID, vote=v)
            return state, False
        if a == "REJECT":  # abstain this round
            state = state.update_juror(HUMAN_ID, vote="UNDECIDED")
            return state, False
        if a == "EXIT":
            return state, True
        # unknown action → treat as no-op terminal to avoid deadlock
        return state, False


async def _closing_votes(state: GameState, case: Case, llm, emit: Emit) -> GameState:
    for j in state.ai_jurors:
        vote, reason = await asyncio.to_thread(llm.revote, state.get_juror(j.id), state, case)
        state = state.update_juror(j.id, vote=vote)
        await emit({"type": "vote", "juror_id": j.id, "name": j.persona.name,
                    "vote": vote, "reason": reason})
        for ev in llm.drain_errors():
            await emit(ev)
        await asyncio.sleep(STREAM_DELAY)
    return state


# --------------------------------------------------------------------------- #
# Main loop.
# --------------------------------------------------------------------------- #
async def run_game(state: GameState, case: Case, llm, emit: Emit, get_action: GetAction):
    await emit({"type": "game_start", **state.public()})

    while not state.verdict_reached:
        await emit({"type": "round_start", "round": state.round})
        state = await _ai_phase(state, case, llm, emit)
        state = await _response_phase(state, case, llm, emit)

        state, exited = await _human_phase(state, case, llm, emit, get_action)
        if exited:
            state = state.finish("exited")
            break

        state = await _closing_votes(state, case, llm, emit)
        consensus = state.consensus()
        last_round = state.round >= state.max_rounds
        status = "unanimous" if consensus else ("hung" if last_round else "open")
        await emit({"type": "tally", "votes": state.tally(), "status": status,
                    "round": state.round})

        if consensus:
            state = state.finish(f"unanimous:{consensus}")
        elif last_round:
            state = state.finish("hung")
        else:
            state = state.next_round()

    # final LLM-as-a-Judge scorecard for the human
    score = await asyncio.to_thread(evaluation.score_human, state, case, llm)
    await emit({"type": "scorecard", "verdict": state.verdict, **score, **state.public()})
    await emit({"type": "done"})
    return state
