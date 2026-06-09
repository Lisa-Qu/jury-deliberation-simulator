"""CDA belief-update engine — pure Python, no LLM, deterministic, testable.

A statement passes four psychological gates before it changes a listener's belief:

  1. distance  (bounded-confidence, Deffuant/Hegselmann–Krause): a speaker whose
     opinion lies farther than the listener's trust radius ``epsilon`` is ignored
     outright — models "you can't be moved by a view too far from your own".
  2. route     (Elaboration Likelihood Model): a listener who engages centrally
     weights the argument's *quality*; one who processes peripherally weights the
     speaker's *credibility cue* instead.
  3. quality   (the judge's argument-quality score) scales how much pull lands.
  4. identity  (cognitive-dissonance / motivated reasoning): a high
     ``identity_stake`` damps the update — the listener resists rather than
     updates. Deliberately NO boomerang/backfire (PNAS 2019 shows it is rare):
     resistance means "does not move", never "moves the wrong way".

Opinion is a signed scalar in [-1, 1] persisted on the BeliefStack: +1 fully
GUILTY, -1 fully NOT_GUILTY. A pull that drags the scalar across the undecided
band flips the derived stance — that is how a juror is genuinely "talked round".
"""
from __future__ import annotations

from dataclasses import replace

from .state import BeliefStack, GameState, Vote

LEARNING_RATE = 0.3       # global step size on each update


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def opinion_of(b: BeliefStack) -> float:
    """Signed opinion scalar in [-1, 1]."""
    return b.opinion


def update_belief(
    listener: BeliefStack,
    speaker_opinion: float,
    quality: float,
    *,
    source_credibility: float = 0.5,
    learning_rate: float = LEARNING_RATE,
) -> BeliefStack:
    """Return a NEW BeliefStack for ``listener`` after hearing a statement of the
    given ``quality`` (0..1) from someone at ``speaker_opinion`` (-1..1).

    Pure function. Returns the *same* object unchanged when the distance gate
    blocks the speaker (so callers can cheaply detect "no effect")."""
    cur = listener.opinion
    distance = abs(speaker_opinion - cur)
    if distance > listener.epsilon:                      # gate 1: too far → ignored
        return listener

    # gate 2 (route) + gate 3 (quality): central listeners weight argument quality,
    # peripheral listeners weight the speaker's credibility cue.
    route = _clamp(listener.route_pref, 0.0, 1.0)
    influence = route * quality + (1.0 - route) * source_credibility

    # gate 4 (identity): high stake damps the update; never inverts it.
    influence *= (1.0 - listener.identity_stake)
    influence *= learning_rate
    influence = max(0.0, influence)

    pull = (speaker_opinion - cur) * influence
    return replace(listener, opinion=_clamp(cur + pull))


# --------------------------------------------------------------------------- #
# Initialization + propagation helpers (used by the engine; still LLM-free).
# --------------------------------------------------------------------------- #
_SIGN = {"GUILTY": 1.0, "NOT_GUILTY": -1.0, "UNDECIDED": 0.0}

_STUBBORN_CUES = ("anchor", "distrust", "certain", "credits law", "fixated",
                  "hard on", "heavily", "信赖", "不信任", "采信", "执着", "笃定")
_OPEN_CUES = ("swings", "emotional", "weighs both", "empath", "recency",
              "感性", "权衡", "共情", "近因", "边想边说")


def init_beliefs(persona, vote: Vote) -> BeliefStack:
    """Derive an initial belief stack from a persona (heuristic, no LLM).
    Stubborn archetypes get a small epsilon + high identity_stake; open ones the
    reverse. v0 leaves ``arguments`` empty — the opinion scalar carries the state."""
    text = f"{persona.bias} {persona.archetype}".lower()
    stubborn = any(c in text for c in _STUBBORN_CUES)
    openish = any(c in text for c in _OPEN_CUES)
    epsilon = 0.4 if stubborn else (0.85 if openish else 0.6)
    identity = 0.8 if stubborn else (0.3 if openish else 0.5)
    conviction = 0.65 if vote != "UNDECIDED" else 0.0
    return BeliefStack(opinion=_SIGN.get(vote, 0.0) * conviction, arguments=(),
                       epsilon=epsilon, identity_stake=identity, route_pref=0.7)


def attach_initial(state: GameState) -> GameState:
    """Give every AI juror an initial belief stack (idempotent)."""
    for j in state.ai_jurors:
        if j.beliefs is None:
            state = state.update_juror(j.id, beliefs=init_beliefs(j.persona, j.vote))
    return state


def propagate(state: GameState, speaker_id: str, quality: float,
              *, source_credibility: float = 0.5):
    """Apply the speaker's statement to every other AI juror's belief.

    Returns (new_state, changes) where changes is a list of
    (juror_id, new_opinion, new_stance, delta) for jurors that actually moved.
    Votes are kept in sync with belief stance. No-op if beliefs aren't enabled."""
    speaker = state.get_juror(speaker_id)
    if speaker.beliefs is None:
        return state, []
    sp_op = speaker.beliefs.opinion
    changes: list[tuple[str, float, str, float]] = []
    for j in state.ai_jurors:
        if j.id == speaker_id or j.beliefs is None:
            continue
        before = j.beliefs.opinion
        nb = update_belief(j.beliefs, sp_op, quality, source_credibility=source_credibility)
        if abs(nb.opinion - before) < 1e-9:              # blocked or negligible
            continue
        state = state.update_juror(j.id, beliefs=nb, vote=nb.stance)
        changes.append((j.id, round(nb.opinion, 3), nb.stance, round(nb.opinion - before, 3)))
    return state, changes
