"""Theory of Mind (ToM) — a speaker's per-opponent model of the others' minds.

Before an agent speaks, it estimates, for each opponent: their current lean
(`est_opinion`), the point they're weakest on (`weakest_point`), and how open they
are (`est_openness`). Following the EMO pattern, each opponent is a DISTINCT model.

This is a GENUINE inference: it asks the LLM (`llm.tom_read`) to read the transcript
and guess. No omniscient shortcut — if the model returns nothing (error / offline
stub provides its own), the speaker simply has no read this turn and falls back to a
generic, untargeted statement. (Offline runs get their guesses from the stub's
`tom_read`, which stands in for the model like everything else in stub mode.)
"""
from __future__ import annotations

from .cases import Case
from .state import GameState, JurorState, ToMGuess


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def update_tom(speaker: JurorState, state: GameState, llm, case: Case) -> tuple[ToMGuess, ...]:
    """Return the speaker's ToM guesses about every other AI juror, inferred by the
    LLM. Empty tuple when there's no read (no tom_read / error / nothing returned)."""
    if speaker.beliefs is None or not hasattr(llm, "tom_read"):
        return ()
    raw = llm.tom_read(speaker, state, case) or []
    valid = {j.id for j in state.ai_jurors if j.id != speaker.id}
    guesses = []
    for r in raw:
        oid = r.get("opponent_id")
        if oid not in valid:
            continue
        guesses.append(ToMGuess(
            opponent_id=oid,
            est_opinion=_clamp(float(r.get("est_opinion", 0.0)), -1.0, 1.0),
            weakest_point=str(r.get("weakest_point", "")),
            est_openness=_clamp(float(r.get("est_openness", 0.6)), 0.0, 1.0),
        ))
    return tuple(guesses)
