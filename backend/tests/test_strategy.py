"""Unit tests for CDA strategy selection (pure functions, no LLM)."""
from __future__ import annotations

from jury import strategy
from jury.state import BeliefStack, JurorState, Persona, ToMGuess


def _juror(opinion, eps=0.6):
    p = Persona("me", "Me", "arch", "bias", "GUILTY", "v")
    return JurorState(persona=p, vote="GUILTY", speaking_score=0.5, responding_score=0.5,
                      beliefs=BeliefStack(opinion=opinion, epsilon=eps))


def test_no_guesses_returns_assert():
    m = strategy.choose_move(_juror(0.6), [], None)
    assert m.tactic == strategy.ASSERT and not m.is_targeted


def test_picks_closest_disagreeing_opponent():
    me = _juror(0.6)                                                  # I lean guilty
    guesses = [
        ToMGuess("a", est_opinion=-0.9, weakest_point="alibi", est_openness=0.8),   # far
        ToMGuess("b", est_opinion=-0.2, weakest_point="prints", est_openness=0.8),  # closest
    ]
    m = strategy.choose_move(me, guesses, None)
    assert m.target_id == "b"                                        # most reachable disagreer
    assert m.target_point == "prints"
    assert m.is_targeted


def test_tactic_matches_openness():
    me = _juror(0.6)
    open_t = strategy.choose_move(me, [ToMGuess("x", -0.2, "p", 0.8)], None)
    closed_t = strategy.choose_move(me, [ToMGuess("y", -0.2, "p", 0.3)], None)
    assert open_t.tactic == strategy.ATTACK_WEAKEST                  # open → argue evidence
    assert closed_t.tactic == strategy.COMMON_GROUND                # closed → de-escalate


def test_agreeing_opponent_not_targeted():
    me = _juror(0.6)                                                 # guilty
    m = strategy.choose_move(me, [ToMGuess("z", est_opinion=0.7, est_openness=0.8)], None)
    assert m.tactic == strategy.ASSERT and not m.is_targeted        # same side → nothing to do


def test_tactic_text_bilingual():
    assert strategy.tactic_text(strategy.ATTACK_WEAKEST, "en")
    assert strategy.tactic_text(strategy.COMMON_GROUND, "zh")
