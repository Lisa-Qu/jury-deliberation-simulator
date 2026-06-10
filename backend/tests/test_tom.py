"""Unit tests for CDA Theory-of-Mind assembly (LLM-read parsing, no real model)."""
from __future__ import annotations

from jury import tom
from jury.state import BeliefStack, GameState, HUMAN_ID, JurorState, Persona


def _j(jid, opinion):
    p = Persona(jid, jid, "arch", "bias", "GUILTY", "v")
    return JurorState(persona=p, vote="GUILTY", speaking_score=0.5, responding_score=0.5,
                      beliefs=BeliefStack(opinion=opinion, epsilon=0.7))


def _state(*jurors):
    human = JurorState(persona=Persona(HUMAN_ID, "You", "h", "h", "UNDECIDED", "v"),
                       vote="UNDECIDED", speaking_score=0.0, responding_score=0.0, is_human=True)
    return GameState(case_id="c", round=1, jurors=tuple(jurors) + (human,))


class _FakeToMLLM:
    """Stands in for llm.tom_read, returning canned inferred guesses."""
    def __init__(self, rows):
        self.rows = rows
    def tom_read(self, juror, state, case):
        return self.rows


class _NoToM:
    """No tom_read at all → update_tom must return ()."""


def test_parses_llm_guesses():
    st = _state(_j("a", 0.6), _j("b", -0.6))
    llm = _FakeToMLLM([{"opponent_id": "b", "est_opinion": -0.6,
                        "weakest_point": "alibi", "est_openness": 0.8}])
    guesses = tom.update_tom(st.get_juror("a"), st, llm, case=None)
    assert len(guesses) == 1
    assert guesses[0].opponent_id == "b" and guesses[0].weakest_point == "alibi"


def test_filters_unknown_opponent_id():
    st = _state(_j("a", 0.6), _j("b", -0.6))
    llm = _FakeToMLLM([{"opponent_id": "ghost", "est_opinion": 0.1}])
    assert tom.update_tom(st.get_juror("a"), st, llm, case=None) == ()


def test_clamps_out_of_range_values():
    st = _state(_j("a", 0.6), _j("b", -0.6))
    llm = _FakeToMLLM([{"opponent_id": "b", "est_opinion": 5.0, "est_openness": 9.0}])
    g = tom.update_tom(st.get_juror("a"), st, llm, case=None)[0]
    assert g.est_opinion == 1.0 and g.est_openness == 1.0


def test_no_tom_read_returns_empty():
    st = _state(_j("a", 0.6), _j("b", -0.6))
    assert tom.update_tom(st.get_juror("a"), st, _NoToM(), case=None) == ()


def test_no_beliefs_returns_empty():
    p = Persona("x", "x", "a", "b", "GUILTY", "v")
    no_belief = JurorState(persona=p, vote="GUILTY", speaking_score=0.5, responding_score=0.5)
    st = _state(no_belief, _j("b", -0.6))
    assert tom.update_tom(st.get_juror("x"), st, _FakeToMLLM([]), case=None) == ()
