"""LLM-as-a-Judge scoring + coaching hint — thin wrappers over JuryLLM."""
from __future__ import annotations

from .cases import Case
from .state import HUMAN_ID, GameState


def human_lines(state: GameState) -> str:
    return "\n".join(
        f"- {e.text}" for e in state.transcript if e.juror_id == HUMAN_ID and e.kind == "human"
    )


def score_human(state: GameState, case: Case, llm) -> dict:
    """5-dimension rubric score (0-100) + recap for the human juror."""
    return llm.rubric(case, human_lines(state), state)


def coach_hint(state: GameState, case: Case, llm) -> str:
    return llm.hint(state, case)
