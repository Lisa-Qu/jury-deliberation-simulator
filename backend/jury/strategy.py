"""Persuasion strategy selection — pure Python, no LLM, deterministic, testable.

Given a speaker's Theory-of-Mind guesses about opponents (jury/tom.py), pick WHO to
try to move and WHICH tactic to use. This is the "audience adaptation" layer: the
tactic is matched to the target's estimated openness (ELM — open/central listeners
get a hard evidence attack; closed/peripheral listeners get common ground first).

Kept LLM-free so it is fast and unit-testable; the chosen Move is then injected into
the generation prompt so the spoken argument is actually targeted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .state import JurorState, ToMGuess

# Tactic vocabulary (a small, named taxonomy — upgradeable to LLM scoring later).
ATTACK_WEAKEST = "attack_weakest"     # hit the target's least-defensible point with evidence
COMMON_GROUND = "common_ground"       # agree on something first, then nudge
CITE_AUTHORITY = "cite_authority"     # lean on credible source / standard (peripheral route)
ASSERT = "assert"                      # no one worth targeting → just state your case

OPEN_ROUTE_THRESHOLD = 0.6            # est_openness above this → central route (argue hard)


@dataclass(frozen=True)
class Move:
    target_id: str          # "" means no specific target (generic assertion)
    tactic: str
    target_point: str = ""  # the opponent's weak point to aim at (from ToM)

    @property
    def is_targeted(self) -> bool:
        return bool(self.target_id)


def _sign(x: float) -> int:
    return (x > 1e-9) - (x < -1e-9)


def choose_move(speaker: JurorState, guesses: Sequence[ToMGuess],
                state) -> Move:
    """Pick the most-persuadable pivotal opponent and a tactic. Pure function.

    Target = an opponent who disagrees with the speaker but is *closest* to them
    (most reachable), preferring the more open one on ties. Tactic follows the
    target's estimated openness (ELM route)."""
    if speaker.beliefs is None or not guesses:
        return Move("", ASSERT, "")
    sp = speaker.beliefs.opinion

    def disagrees(g: ToMGuess) -> bool:
        return _sign(g.est_opinion) != _sign(sp) or abs(g.est_opinion - sp) > 0.3

    candidates = [g for g in guesses if disagrees(g)]
    if not candidates:
        return Move("", ASSERT, "")

    # most reachable = smallest opinion distance; break ties toward the more open
    target = min(candidates, key=lambda g: (abs(g.est_opinion - sp), -g.est_openness))
    if target.est_openness >= OPEN_ROUTE_THRESHOLD:
        tactic = ATTACK_WEAKEST          # open/central → argue the evidence
    else:
        tactic = COMMON_GROUND           # closed/peripheral → de-escalate first
    return Move(target.opponent_id, tactic, target.weakest_point or "")


def move_against(target_id: str, guesses: Sequence[ToMGuess]) -> Move:
    """Build a Move aimed at a SPECIFIC opponent (used in the response phase, where
    the responder is already replying to the last speaker). Tactic from openness."""
    g = next((x for x in guesses if x.opponent_id == target_id), None)
    if g is None:
        return Move(target_id, ATTACK_WEAKEST, "")
    tactic = ATTACK_WEAKEST if g.est_openness >= OPEN_ROUTE_THRESHOLD else COMMON_GROUND
    return Move(target_id, tactic, g.weakest_point or "")


# Human-readable tactic guidance injected into the generation prompt.
TACTIC_GUIDANCE = {
    ATTACK_WEAKEST: {
        "en": "directly attack that weak point with specific evidence",
        "zh": "用具体证据直接攻击那个薄弱点",
    },
    COMMON_GROUND: {
        "en": "first acknowledge something they're right about, then gently shift them",
        "zh": "先承认他们对的一点，再温和地动摇他们",
    },
    CITE_AUTHORITY: {
        "en": "lean on a credible standard or authority they respect",
        "zh": "搬出他们认可的权威标准",
    },
    ASSERT: {"en": "make your strongest general case", "zh": "陈述你最有力的总体论点"},
}


def tactic_text(tactic: str, lang: str = "en") -> str:
    return TACTIC_GUIDANCE.get(tactic, TACTIC_GUIDANCE[ASSERT])[lang if lang in ("en", "zh") else "en"]
