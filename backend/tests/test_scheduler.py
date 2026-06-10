"""Unit tests for the CDA drive-based scheduler (pure functions, no LLM)."""
from __future__ import annotations

from jury import scheduler
from jury.state import BeliefStack, GameState, HUMAN_ID, JurorState, Persona


def _j(jid, opinion, respond=0.5):
    p = Persona(jid, jid, "arch", "bias", "GUILTY", "v")
    return JurorState(persona=p, vote="GUILTY", speaking_score=0.5,
                      responding_score=respond, beliefs=BeliefStack(opinion=opinion))


def _state(*jurors):
    human = JurorState(persona=Persona(HUMAN_ID, "You", "h", "h", "UNDECIDED", "v"),
                       vote="UNDECIDED", speaking_score=0.0, responding_score=0.0, is_human=True)
    return GameState(case_id="c", round=1, jurors=tuple(jurors) + (human,))


def test_drive_without_beliefs_falls_back_to_speaking_score():
    p = Persona("x", "x", "a", "b", "GUILTY", "v")
    j = JurorState(persona=p, vote="GUILTY", speaking_score=0.9, responding_score=0.1)
    assert scheduler.drive(j, 0.0) == 0.9


def test_strong_dissenter_speaks_first():
    st = _state(_j("a", 0.6), _j("b", 0.6), _j("d", -0.9))   # room leans guilty; d dissents hard
    order = [j.id for j in scheduler.speaking_order(st)]
    assert order[0] == "d"


def test_human_excluded_from_order():
    st = _state(_j("a", 0.6), _j("b", -0.6))
    ids = [j.id for j in scheduler.speaking_order(st)]
    assert HUMAN_ID not in ids and len(ids) == 2
