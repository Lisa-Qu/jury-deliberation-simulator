"""Immutable game state.

All updates return NEW objects (frozen dataclasses + `dataclasses.replace`);
nothing is mutated in place. `JurorStateDict` / `GameStateDict` are TypedDicts
used for JSON serialization to the frontend (the "structured state management"
surface; also the shape a LangGraph StateGraph would carry).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Optional, TypedDict

Vote = Literal["GUILTY", "NOT_GUILTY", "UNDECIDED"]

HUMAN_ID = "you"


# --------------------------------------------------------------------------- #
# Serialized shapes (TypedDict) — what crosses the wire to the React client.
# --------------------------------------------------------------------------- #
class PersonaDict(TypedDict):
    id: str
    name: str
    archetype: str
    bias: str
    initial_leaning: Vote
    voice: str


class JurorStateDict(TypedDict):
    persona: PersonaDict
    vote: Vote
    speaking_score: float
    responding_score: float
    inner_reasoning: str
    is_human: bool
    # CDA belief summary (None until JURY_BELIEFS is enabled) — for frontend viz.
    opinion: Optional[float]          # signed scalar in [-1, 1]: +guilty / -not-guilty
    conviction: Optional[float]       # magnitude of confidence in [0, 1]
    belief_stance: Optional[str]


# --------------------------------------------------------------------------- #
# Runtime objects (frozen dataclasses) — immutable, replace() to update.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    archetype: str          # e.g. "retired structural engineer"
    bias: str               # cognitive bias / leaning, drives flavored reasoning
    initial_leaning: Vote
    voice: str              # speaking-style guidance for the prompt

    def public(self) -> PersonaDict:
        return PersonaDict(
            id=self.id, name=self.name, archetype=self.archetype,
            bias=self.bias, initial_leaning=self.initial_leaning, voice=self.voice,
        )


# --------------------------------------------------------------------------- #
# CDA (Cognitive Deliberation Architecture) belief model — see jury/beliefs.py.
# A Toulmin-structured argument and a layered belief held by one juror. All
# immutable; the numpy belief-update engine returns new copies.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ToulminArg:
    claim: str                  # the point being made
    grounds: str                # the evidence/data behind it
    warrant: str                # the (attackable) assumption linking grounds→claim
    strength: float             # 0..1, how strongly this juror holds it


UNDECIDED_BAND = 0.12   # |opinion| below this reads as UNDECIDED


@dataclass(frozen=True)
class BeliefStack:
    # `opinion` is the persisted signed scalar in [-1, 1]: + guilty / - not guilty.
    # stance & conviction are DERIVED so a small lean accumulates instead of being
    # flattened to 0 (the bug a stance+conviction representation would hide).
    opinion: float = 0.0
    arguments: tuple[ToulminArg, ...] = ()  # supporting arguments (v1+; empty in v0)
    epsilon: float = 0.6                    # bounded-confidence radius (openness)
    identity_stake: float = 0.5             # stubbornness (identity-bound the stance is)
    route_pref: float = 0.7                 # ELM: 1=central(quality) .. 0=peripheral(cue)

    @property
    def conviction(self) -> float:
        return round(abs(self.opinion), 4)

    @property
    def stance(self) -> Vote:
        if abs(self.opinion) < UNDECIDED_BAND:
            return "UNDECIDED"
        return "GUILTY" if self.opinion > 0 else "NOT_GUILTY"


@dataclass(frozen=True)
class ToMGuess:
    opponent_id: str
    est_opinion: float                      # my guess of their signed opinion [-1,1]
    weakest_point: str = ""                 # what they're least defensible on
    est_openness: float = 0.6               # my guess of their bounded-confidence ε


@dataclass(frozen=True)
class JurorState:
    persona: Persona
    vote: Vote
    speaking_score: float       # propensity to take the floor proactively
    responding_score: float     # propensity to react to others
    inner_reasoning: str = ""
    is_human: bool = False
    beliefs: Optional[BeliefStack] = None   # None until JURY_BELIEFS is enabled
    tom: tuple["ToMGuess", ...] = ()        # this juror's guesses about opponents (JURY_TOM)

    @property
    def id(self) -> str:
        return self.persona.id

    def public(self) -> JurorStateDict:
        opinion = conviction = belief_stance = None
        if self.beliefs is not None:
            opinion = round(self.beliefs.opinion, 3)
            conviction = round(self.beliefs.conviction, 3)
            belief_stance = self.beliefs.stance
        return JurorStateDict(
            persona=self.persona.public(),
            vote=self.vote,
            speaking_score=round(self.speaking_score, 3),
            responding_score=round(self.responding_score, 3),
            inner_reasoning=self.inner_reasoning,
            is_human=self.is_human,
            opinion=opinion,
            conviction=conviction,
            belief_stance=belief_stance,
        )


@dataclass(frozen=True)
class TranscriptEntry:
    juror_id: str
    name: str
    kind: Literal["speak", "respond", "human", "hint", "verdict"]
    text: str
    vote: Vote
    round: int

    def public(self) -> dict:
        return {
            "juror_id": self.juror_id, "name": self.name, "kind": self.kind,
            "text": self.text, "vote": self.vote, "round": self.round,
        }


@dataclass(frozen=True)
class GameState:
    case_id: str
    round: int
    jurors: tuple[JurorState, ...]
    transcript: tuple[TranscriptEntry, ...] = ()
    verdict_reached: bool = False
    verdict: Optional[str] = None        # "unanimous:GUILTY" | "hung" | "exited"
    max_rounds: int = 4

    # --- immutable update helpers ----------------------------------------- #
    def replace_juror(self, juror_id: str, new_juror: JurorState) -> "GameState":
        jurors = tuple(new_juror if j.id == juror_id else j for j in self.jurors)
        return replace(self, jurors=jurors)

    def update_juror(self, juror_id: str, **changes) -> "GameState":
        j = self.get_juror(juror_id)
        return self.replace_juror(juror_id, replace(j, **changes))

    def update_beliefs(self, juror_id: str, beliefs: BeliefStack) -> "GameState":
        return self.update_juror(juror_id, beliefs=beliefs)

    def add_entry(self, entry: TranscriptEntry) -> "GameState":
        return replace(self, transcript=self.transcript + (entry,))

    def next_round(self) -> "GameState":
        return replace(self, round=self.round + 1)

    def finish(self, verdict: str) -> "GameState":
        return replace(self, verdict_reached=True, verdict=verdict)

    # --- queries ---------------------------------------------------------- #
    def get_juror(self, juror_id: str) -> JurorState:
        for j in self.jurors:
            if j.id == juror_id:
                return j
        raise KeyError(juror_id)

    @property
    def human(self) -> JurorState:
        return self.get_juror(HUMAN_ID)

    @property
    def ai_jurors(self) -> tuple[JurorState, ...]:
        return tuple(j for j in self.jurors if not j.is_human)

    def tally(self) -> dict[str, int]:
        counts: dict[str, int] = {"GUILTY": 0, "NOT_GUILTY": 0, "UNDECIDED": 0}
        for j in self.jurors:
            counts[j.vote] = counts.get(j.vote, 0) + 1
        return counts

    def consensus(self) -> Optional[Vote]:
        """Unanimous decided verdict, else None."""
        votes = {j.vote for j in self.jurors}
        if len(votes) == 1 and "UNDECIDED" not in votes:
            return next(iter(votes))
        return None

    def public(self) -> dict:
        return {
            "case_id": self.case_id,
            "round": self.round,
            "max_rounds": self.max_rounds,
            "jurors": [j.public() for j in self.jurors],
            "transcript": [e.public() for e in self.transcript],
            "verdict_reached": self.verdict_reached,
            "verdict": self.verdict,
            "tally": self.tally(),
        }
