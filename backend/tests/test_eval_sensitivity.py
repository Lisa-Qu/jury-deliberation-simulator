"""Regression guards proving the eval harness is sensitive (not just deterministic),
plus the LEARNING_RATE live-config fix. All offline."""
from __future__ import annotations

from jury import beliefs, evalrun
from jury.state import BeliefStack
from jury.stub import StubLLM


def test_belief_movement_tracks_argument_quality(monkeypatch):
    """Weaker judged arguments must move beliefs less than stronger ones — the core
    'quality-sensitivity' the harness exists to detect. If this link breaks, fail."""
    monkeypatch.setattr(StubLLM, "judge", lambda self, s, c: {"quality": 0.1, "fallacy": "none"})
    low = evalrun.run_eval(1, rounds=2)["avg_belief_movement"]
    monkeypatch.setattr(StubLLM, "judge", lambda self, s, c: {"quality": 1.0, "fallacy": "none"})
    high = evalrun.run_eval(1, rounds=2)["avg_belief_movement"]
    assert low < high


def test_learning_rate_is_live_config():
    """beliefs.LEARNING_RATE must affect update_belief at call time (was dead config
    due to a default-arg binding bug)."""
    b = BeliefStack(opinion=0.0, epsilon=2.0, identity_stake=0.0, route_pref=1.0)
    orig = beliefs.LEARNING_RATE
    try:
        beliefs.LEARNING_RATE = 0.1
        small = beliefs.update_belief(b, 1.0, 1.0).opinion
        beliefs.LEARNING_RATE = 0.9
        big = beliefs.update_belief(b, 1.0, 1.0).opinion
        assert 0 < small < big
    finally:
        beliefs.LEARNING_RATE = orig


def test_stronger_args_unify_a_reachable_listener_more():
    """In the reachable regime (within ε), a stronger argument pulls the listener
    closer to the speaker → more convergence. Substantiates 'better args → more unity'."""
    def listener():
        return BeliefStack(opinion=0.5, epsilon=2.0, identity_stake=0.0, route_pref=1.0)

    weak = beliefs.update_belief(listener(), -0.5, quality=0.1)
    strong = beliefs.update_belief(listener(), -0.5, quality=0.9)
    assert abs(strong.opinion - (-0.5)) < abs(weak.opinion - (-0.5))
