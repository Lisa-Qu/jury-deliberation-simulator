"""CDA drive-based speaking scheduler — pure Python, no LLM.

Replaces the static `speaking_score` sort with a belief-aware "urge to speak" so
the order shifts with the debate: jurors who disagree most with the room (and hold
that position with conviction) take the floor sooner. Falls back to the legacy
`speaking_score` when a juror has no belief stack.
"""
from __future__ import annotations

from .state import GameState, JurorState

W_RESPOND = 0.5       # base reactivity (existing responding_score)
W_DISAGREE = 0.3      # distance from the room's mean opinion → urge to push back
W_CONVICTION = 0.2    # how firmly the juror holds their position


def drive(juror: JurorState, mean_opinion: float) -> float:
    if juror.beliefs is None:
        return juror.speaking_score
    op = juror.beliefs.opinion
    return (W_RESPOND * juror.responding_score
            + W_DISAGREE * abs(op - mean_opinion)
            + W_CONVICTION * abs(op))


def speaking_order(state: GameState) -> list[JurorState]:
    """AI jurors ordered by descending speaking drive."""
    ai = list(state.ai_jurors)
    ops = [j.beliefs.opinion for j in ai if j.beliefs is not None]
    mean = sum(ops) / len(ops) if ops else 0.0
    return sorted(ai, key=lambda j: -drive(j, mean))
