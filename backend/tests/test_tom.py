"""Unit tests for CDA Theory-of-Mind assembly (heuristic fallback, no LLM)."""
from __future__ import annotations

from jury import beliefs, tom
from jury.state import BeliefStack, GameState, HUMAN_ID, JurorState, Persona


def _j(jid, opinion, args=()):
    p = Persona(jid, jid, "arch", "bias", "GUILTY", "v")
    return JurorState(persona=p, vote="GUILTY", speaking_score=0.5, responding_score=0.5,
                      beliefs=BeliefStack(opinion=opinion, arguments=args, epsilon=0.7))


def _state(*jurors):
    human = JurorState(persona=Persona(HUMAN_ID, "You", "h", "h", "UNDECIDED", "v"),
                       vote="UNDECIDED", speaking_score=0.0, responding_score=0.0, is_human=True)
    return GameState(case_id="c", round=1, jurors=tuple(jurors) + (human,))


class _NoToMLLM:
    """Forces tom.update_tom onto the heuristic path (no tom_read)."""


def test_heuristic_models_each_opponent():
    st = _state(_j("a", 0.6), _j("b", -0.6))
    guesses = tom.update_tom(st.get_juror("a"), st, _NoToMLLM(), case=None)
    ids = {g.opponent_id for g in guesses}
    assert ids == {"b"}                                  # only the other AI juror
    assert guesses[0].est_opinion == -0.6                # reads their opinion


def test_weakest_point_is_lowest_strength_warrant():
    args = beliefs.set_arguments(
        BeliefStack(opinion=0.6),
        [{"claim": "c1", "warrant": "strong", "strength": 0.9},
         {"claim": "c2", "warrant": "shaky", "strength": 0.2}],
    ).arguments
    st = _state(_j("a", 0.6), _j("b", -0.6, args=args))
    guesses = tom.update_tom(st.get_juror("a"), st, _NoToMLLM(), case=None)
    b = next(g for g in guesses if g.opponent_id == "b")
    assert b.weakest_point == "shaky"                    # lowest-strength argument's warrant


def test_speaker_without_beliefs_returns_empty():
    p = Persona("x", "x", "a", "b", "GUILTY", "v")
    no_belief = JurorState(persona=p, vote="GUILTY", speaking_score=0.5, responding_score=0.5)
    st = _state(no_belief, _j("b", -0.6))
    assert tom.update_tom(st.get_juror("x"), st, _NoToMLLM(), case=None) == ()
