"""Unit tests for the CDA belief-update engine (pure functions, no LLM/network)."""
from __future__ import annotations

from jury import beliefs
from jury.state import BeliefStack, Persona


_SIGN = {"GUILTY": 1.0, "NOT_GUILTY": -1.0, "UNDECIDED": 0.0}


def _b(stance, conv, eps=0.6, ident=0.5, route=0.7):
    return BeliefStack(opinion=_SIGN[stance] * conv, epsilon=eps,
                       identity_stake=ident, route_pref=route)


def test_opinion_sign_and_magnitude():
    assert beliefs.opinion_of(_b("GUILTY", 0.8)) == 0.8
    assert beliefs.opinion_of(_b("NOT_GUILTY", 0.8)) == -0.8
    assert beliefs.opinion_of(_b("UNDECIDED", 0.5)) == 0.0


def test_distance_gate_blocks_far_speaker():
    listener = _b("GUILTY", 0.9, eps=0.3)                       # opinion +0.9
    out = beliefs.update_belief(listener, -0.9, quality=0.9)    # d = 1.8 > 0.3
    assert out is listener                                      # unchanged object


def test_strong_argument_moves_open_listener():
    listener = _b("GUILTY", 0.4, eps=1.0, ident=0.2)           # within reach, low stake
    out = beliefs.update_belief(listener, -0.6, quality=0.9)
    assert beliefs.opinion_of(out) < beliefs.opinion_of(listener)   # pulled toward NOT_GUILTY


def test_high_identity_resists_more_than_open():
    # eps=2.0 so the distance gate never blocks — isolates the identity damping.
    open_out = beliefs.update_belief(_b("GUILTY", 0.5, eps=2.0, ident=0.1), -0.6, 0.9)
    stub_out = beliefs.update_belief(_b("GUILTY", 0.5, eps=2.0, ident=0.9), -0.6, 0.9)
    open_move = 0.5 - beliefs.opinion_of(open_out)
    stub_move = 0.5 - beliefs.opinion_of(stub_out)
    assert open_move > stub_move >= 0


def test_no_boomerang_under_high_identity():
    # high identity + opposing strong argument must NOT push opinion the wrong way
    out = beliefs.update_belief(_b("GUILTY", 0.5, eps=2.0, ident=0.95), -0.8, 1.0)
    assert beliefs.opinion_of(out) <= 0.5 + 1e-9


def test_can_flip_across_zero_under_sustained_pressure():
    b = _b("GUILTY", 0.1, eps=2.0, ident=0.0)      # eps=2.0 so a far speaker is heard
    assert b.stance == "UNDECIDED"                  # +0.1 is within the undecided band
    for _ in range(15):
        b = beliefs.update_belief(b, -1.0, quality=1.0)
    assert b.stance == "NOT_GUILTY"                 # sustained pressure flips it


def test_init_beliefs_stubborn_vs_open():
    stubborn = Persona("j", "X", "ex-cop", "credits law enforcement heavily", "GUILTY", "v")
    openp = Persona("j", "Y", "teacher", "swings with recency bias, emotional", "UNDECIDED", "v")
    sb = beliefs.init_beliefs(stubborn, "GUILTY")
    ob = beliefs.init_beliefs(openp, "UNDECIDED")
    assert sb.epsilon < ob.epsilon
    assert sb.identity_stake > ob.identity_stake
    assert sb.conviction > ob.conviction          # decided stance is held more firmly
