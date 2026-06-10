"""Theory of Mind (ToM) — a speaker's per-opponent model of the others' minds.

Before an agent speaks, it estimates, for each opponent: their current lean
(`est_opinion`), the point they're weakest on (`est_weakest_point`), and how open
they are (`est_openness`). Following the EMO pattern, each opponent is modeled as a
DISTINCT entity (not a monolithic "other").

`update_tom` prefers a real LLM inference from the transcript (`llm.tom_read`); if
that's unavailable/empty (offline stub, error) it falls back to a cheap heuristic
that reads opponents' actual belief state — approximate but keeps the loop running.
"""
from __future__ import annotations

from .cases import Case
from .state import GameState, JurorState, ToMGuess


def _heuristic(speaker: JurorState, state: GameState) -> tuple[ToMGuess, ...]:
    """LLM-free fallback: approximate each opponent from their belief stack."""
    out = []
    for j in state.ai_jurors:
        if j.id == speaker.id or j.beliefs is None:
            continue
        out.append(ToMGuess(opponent_id=j.id, est_opinion=j.beliefs.opinion,
                            weakest_point="", est_openness=j.beliefs.epsilon))
    return tuple(out)


def update_tom(speaker: JurorState, state: GameState, llm, case: Case) -> tuple[ToMGuess, ...]:
    """Return the speaker's ToM guesses about every other AI juror."""
    if speaker.beliefs is None:
        return ()
    raw = []
    if hasattr(llm, "tom_read"):
        raw = llm.tom_read(speaker, state, case) or []
    if not raw:
        return _heuristic(speaker, state)
    valid = {j.id for j in state.ai_jurors if j.id != speaker.id}
    guesses = []
    for r in raw:
        oid = r.get("opponent_id")
        if oid not in valid:
            continue
        guesses.append(ToMGuess(
            opponent_id=oid,
            est_opinion=max(-1.0, min(1.0, float(r.get("est_opinion", 0.0)))),
            weakest_point=str(r.get("weakest_point", "")),
            est_openness=max(0.0, min(1.0, float(r.get("est_openness", 0.6)))),
        ))
    return tuple(guesses) if guesses else _heuristic(speaker, state)
