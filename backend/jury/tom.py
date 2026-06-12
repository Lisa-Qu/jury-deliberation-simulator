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
from .schemas import ToMRead, parse_list
from .state import GameState, JurorState, ToMGuess


def update_tom(speaker: JurorState, state: GameState, llm, case: Case) -> tuple[ToMGuess, ...]:
    """Return the speaker's ToM guesses about every other AI juror, inferred by the
    LLM and validated through the `ToMRead` pydantic schema. Empty tuple when there's
    no read (no tom_read / error / nothing returned)."""
    if speaker.beliefs is None or not hasattr(llm, "tom_read"):
        return ()
    raw = llm.tom_read(speaker, state, case) or []
    valid = {j.id for j in state.ai_jurors if j.id != speaker.id}
    guesses = []
    for r in parse_list(ToMRead, raw):       # pydantic-validated + coerced
        if r.opponent_id not in valid:
            continue
        guesses.append(ToMGuess(opponent_id=r.opponent_id, est_opinion=r.est_opinion,
                                weakest_point=r.weakest_point, est_openness=r.est_openness))
    return tuple(guesses)
