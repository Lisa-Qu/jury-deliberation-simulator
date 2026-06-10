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

from . import beliefs as belief_engine
from . import eval as evaluation
from . import metrics
from . import scheduler
from . import strategy
from . import tom as tom_engine
from .cases import Case
from .llm import clean_statement, parse_vote
from .state import HUMAN_ID, GameState, JurorState, TranscriptEntry, Vote

Emit = Callable[[dict], Awaitable[None]]
GetAction = Callable[[], Awaitable[dict]]

HUMAN_OPTS = ["SPEAK", "VOTE", "REJECT", "EXIT", "HINT"]
STREAM_DELAY = float(os.environ.get("JURY_STREAM_DELAY", "0.35"))
# A juror whose responding_score crosses this threshold gets to interject a
# direct response to the previous speaker — score-gated interaction scheduling.
RESPOND_THRESHOLD = float(os.environ.get("JURY_RESPOND_THRESHOLD", "0.6"))


def _beliefs_on() -> bool:
    # CDA belief loop is opt-in so default/legacy behavior is untouched.
    return os.environ.get("JURY_BELIEFS", "").lower() in ("1", "true", "yes")


def _tom_on() -> bool:
    # Theory-of-Mind + targeted persuasion (v2). Only meaningful with beliefs on.
    return os.environ.get("JURY_TOM", "").lower() in ("1", "true", "yes")


def _stream_on() -> bool:
    # Token-style streaming of utterances over SSE (chunked replay in v1).
    return os.environ.get("JURY_STREAM", "").lower() in ("1", "true", "yes")


def _reflect_on() -> bool:
    return os.environ.get("JURY_REFLECT", "").lower() in ("1", "true", "yes")


async def _emit_event(emit: Emit, ev: dict) -> None:
    """Stream `speak` events as speak_start / speak_delta* / speak_end when
    JURY_STREAM is on (so the UI renders words as they arrive); pass everything
    else through unchanged. v1 chunks the already-computed text (not true
    token-level TTFT streaming — that's a later swap of the chunk source)."""
    if not (_stream_on() and ev.get("type") == "speak"):
        await emit(ev)
        return
    head = {k: ev.get(k) for k in ("juror_id", "name", "responding_to")}
    await emit({"type": "speak_start", **head})
    for word in (ev.get("text") or "").split(" "):
        await emit({"type": "speak_delta", "juror_id": ev.get("juror_id"), "text": word + " "})
    await emit({"type": "speak_end", **head, "vote": ev.get("vote"), "text": ev.get("text")})


async def _propagate_beliefs(state: GameState, case: Case, llm, emit: Emit,
                             speaker_id: str, text: str) -> GameState:
    """After a juror speaks, judge the statement (off the visible path — the
    utterance already streamed out) and let the numpy belief engine update every
    other juror. Emits `belief_update` events for the UI. No-op unless enabled."""
    if state.get_juror(speaker_id).beliefs is None:
        return state
    jq = await asyncio.to_thread(llm.judge, text, case)
    for ev in llm.drain_errors():
        await emit(ev)
    quality = float(jq.get("quality", 0.5))
    state, changes = belief_engine.propagate(state, speaker_id, quality)
    by = state.get_juror(speaker_id).persona.name
    for jid, opinion, stance, delta in changes:
        await emit({"type": "belief_update", "juror_id": jid, "opinion": opinion,
                    "stance": stance, "delta": delta, "by": by,
                    "quality": round(quality, 3)})
    return state


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


def compute_juror_turn(juror: JurorState, state: GameState, case: Case, llm, move=None):
    name = juror.persona.name
    thought = llm.think(juror, state, case)
    events: list[dict] = [
        {"type": "thinking", "juror_id": juror.id, "name": name, "text": thought}]

    collected: list[tuple[str, object]] = []
    text, vote = llm.speak(
        juror, state, case,
        on_tool_call=lambda q: collected.append(("call", q)),
        on_tool_result=lambda h: collected.append(("result", h)),
        move=move,
    )
    events.extend(_tool_events(juror, collected))
    events.append({"type": "speak", "juror_id": juror.id, "name": name,
                   "text": text, "vote": vote})
    events.extend(llm.drain_errors())
    return events, replace(juror, vote=vote, inner_reasoning=thought), text, vote


def compute_respond_turn(juror: JurorState, target_name: str, target_text: str,
                         state: GameState, case: Case, llm, move=None):
    name = juror.persona.name
    thought = llm.think(juror, state, case)
    events: list[dict] = [
        {"type": "thinking", "juror_id": juror.id, "name": name, "text": thought}]

    collected: list[tuple[str, object]] = []
    text, vote = llm.respond(
        juror, state, case, target_name, target_text,
        on_tool_call=lambda q: collected.append(("call", q)),
        on_tool_result=lambda h: collected.append(("result", h)),
        move=move,
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
async def _stream_ai_turn(state: GameState, juror: JurorState, move, case: Case,
                          llm, emit: Emit) -> GameState:
    """One AI speaking turn with TRUE token streaming. Runs the blocking
    `llm.stream_speak` generator in a thread and bridges its output to async SSE
    emits (tool_call/tool_result, then speak_start/speak_delta*/speak_end)."""
    import queue as _queue

    name = juror.persona.name
    thought = await asyncio.to_thread(llm.think, juror, state, case)
    await emit({"type": "thinking", "juror_id": juror.id, "name": name, "text": thought})

    q: "_queue.Queue" = _queue.Queue()

    def worker() -> None:
        try:
            for tok in llm.stream_speak(juror, state, case, move,
                                        on_tool_call=lambda x: q.put(("call", x)),
                                        on_tool_result=lambda h: q.put(("result", h))):
                q.put(("tok", tok))
        except Exception as e:  # noqa: BLE001 — degrade, never crash the game
            q.put(("err", str(e)[:200]))
        q.put(("done", None))

    loop = asyncio.get_event_loop()
    fut = loop.run_in_executor(None, worker)
    full: list[str] = []
    started = False
    while True:
        kind, val = await loop.run_in_executor(None, q.get)
        if kind == "call":
            await emit({"type": "tool_call", "juror_id": juror.id, "name": name,
                        "tool": "lookup_evidence", "query": val})
        elif kind == "result":
            await emit({"type": "tool_result", "juror_id": juror.id, "name": name,
                        "evidence_ids": val.ids, "snippets": val.snippets,
                        "scores": [round(s, 3) for s in val.scores]})
        elif kind == "tok":
            if not started:
                await emit({"type": "speak_start", "juror_id": juror.id, "name": name})
                started = True
            full.append(val)
            await emit({"type": "speak_delta", "juror_id": juror.id, "text": val})
        elif kind == "err":
            await emit({"type": "error", "stage": "stream", "message": val, "recovered": True})
        elif kind == "done":
            break
    await fut

    raw = "".join(full)
    text = clean_statement(raw) or "(I'll hold my position for now.)"
    vote = parse_vote(raw, juror.vote)
    if not started:
        await emit({"type": "speak_start", "juror_id": juror.id, "name": name})
    await emit({"type": "speak_end", "juror_id": juror.id, "name": name, "text": text, "vote": vote})
    for ev in llm.drain_errors():
        await emit(ev)

    new_j = replace(juror, vote=vote, inner_reasoning=thought)
    state = state.replace_juror(new_j.id, new_j)
    state = state.add_entry(TranscriptEntry(new_j.id, name, "speak", text, vote, state.round))
    state = _after_speaker(state, new_j.id)
    return await _propagate_beliefs(state, case, llm, emit, new_j.id, text)


async def _ai_phase(state: GameState, case: Case, llm, emit: Emit) -> GameState:
    # belief-aware drive scheduler when beliefs on; else legacy speaking_score sort
    order = (scheduler.speaking_order(state) if _beliefs_on()
             else sorted(state.ai_jurors, key=lambda j: -j.speaking_score))
    for j in order:
        juror = state.get_juror(j.id)
        move = None
        if _tom_on() and juror.beliefs is not None:
            # Theory of Mind: the speaker reads opponents, then targets one.
            guesses = await asyncio.to_thread(tom_engine.update_tom, juror, state, llm, case)
            for ev in llm.drain_errors():
                await emit(ev)
            state = state.update_juror(juror.id, tom=guesses)
            juror = state.get_juror(juror.id)
            move = strategy.choose_move(juror, guesses, state)
            if move.is_targeted:
                await emit({"type": "strategy", "juror_id": juror.id, "name": juror.persona.name,
                            "target_id": move.target_id,
                            "target": state.get_juror(move.target_id).persona.name,
                            "tactic": move.tactic, "target_point": move.target_point})
        if _stream_on() and hasattr(llm, "stream_speak"):
            # TRUE token streaming (real LLM): emit speak_delta as tokens arrive.
            state = await _stream_ai_turn(state, juror, move, case, llm, emit)
            continue
        events, new_j, text, vote = await asyncio.to_thread(
            compute_juror_turn, juror, state, case, llm, move
        )
        for ev in events:
            await _emit_event(emit, ev)
            await asyncio.sleep(STREAM_DELAY)
        state = state.replace_juror(new_j.id, new_j)
        state = state.add_entry(TranscriptEntry(
            new_j.id, new_j.persona.name, "speak", text, vote, state.round))
        state = _after_speaker(state, new_j.id)
        state = await _propagate_beliefs(state, case, llm, emit, new_j.id, text)
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
    move = None
    if _tom_on() and state.get_juror(responder.id).beliefs is not None:
        guesses = await asyncio.to_thread(
            tom_engine.update_tom, state.get_juror(responder.id), state, llm, case)
        for ev in llm.drain_errors():
            await emit(ev)
        state = state.update_juror(responder.id, tom=guesses)
        move = strategy.move_against(last.juror_id, guesses)   # reply targets the last speaker
        await emit({"type": "strategy", "juror_id": responder.id,
                    "name": responder.persona.name, "target_id": last.juror_id,
                    "target": last.name, "tactic": move.tactic,
                    "target_point": move.target_point})
    events, new_j, text, vote = await asyncio.to_thread(
        compute_respond_turn, state.get_juror(responder.id),
        last.name, last.text, state, case, llm, move)
    for ev in events:
        await _emit_event(emit, ev)
        await asyncio.sleep(STREAM_DELAY)
    state = state.replace_juror(new_j.id, new_j)
    state = state.add_entry(TranscriptEntry(
        new_j.id, new_j.persona.name, "respond", text, vote, state.round))
    state = state.update_juror(new_j.id, responding_score=max(0.1, responder.responding_score * 0.5))
    return await _propagate_beliefs(state, case, llm, emit, new_j.id, text)


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
        cur = state.get_juror(j.id)
        if cur.beliefs is not None:
            # belief-driven: the vote already tracks the belief stance — skip the
            # extra revote LLM call (also a latency win), use the stance directly.
            vote, reason = cur.beliefs.stance, "(belief-driven)"
        else:
            vote, reason = await asyncio.to_thread(llm.revote, cur, state, case)
        state = state.update_juror(j.id, vote=vote)
        await emit({"type": "vote", "juror_id": j.id, "name": j.persona.name,
                    "vote": vote, "reason": reason})
        if cur.beliefs is None:
            for ev in llm.drain_errors():
                await emit(ev)
        await asyncio.sleep(STREAM_DELAY)
    return state


# --------------------------------------------------------------------------- #
# Main loop.
# --------------------------------------------------------------------------- #
async def run_game(state: GameState, case: Case, llm, emit: Emit, get_action: GetAction):
    belief_updates: list[dict] = []
    if _beliefs_on():
        state = belief_engine.attach_initial(state)   # CDA opt-in belief model
        if _tom_on():
            # Toulmin arguments per juror (feeds ToM weakest-point). Offline → empty → no-op.
            for j in state.ai_jurors:
                raw = await asyncio.to_thread(llm.extract_arguments, j, case)
                if raw:
                    state = state.update_beliefs(j.id, belief_engine.set_arguments(j.beliefs, raw))
        base_emit = emit

        async def emit(ev: dict) -> None:             # capture belief_update for metrics
            if ev.get("type") == "belief_update":
                belief_updates.append(ev)
            await base_emit(ev)

    await emit({"type": "game_start", **state.public()})

    while not state.verdict_reached:
        await emit({"type": "round_start", "round": state.round})
        if _reflect_on():
            for j in state.ai_jurors:
                r = await asyncio.to_thread(llm.reflect, j, state, case)
                state = state.update_juror(j.id, inner_reasoning=r)
                await emit({"type": "reflection", "juror_id": j.id, "name": j.persona.name, "text": r})
            for ev in llm.drain_errors():
                await emit(ev)
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

    if _beliefs_on():
        opinions = [j.beliefs.opinion for j in state.ai_jurors if j.beliefs is not None]
        await emit({"type": "metrics", **metrics.summary(belief_updates, opinions)})

    # final LLM-as-a-Judge scorecard for the human
    score = await asyncio.to_thread(evaluation.score_human, state, case, llm)
    await emit({"type": "scorecard", "verdict": state.verdict, **score, **state.public()})
    await emit({"type": "done"})
    return state
