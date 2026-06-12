"""Phase-B units: pydantic schemas, observability records, offline eval harness."""
from __future__ import annotations

from jury import evalrun, obs
from jury.schemas import ArgumentOut, JudgeResult, ToMRead, parse_list


# --- schemas (structured-output validation/coercion) ----------------------- #
def test_judge_result_coerces_0_100_to_0_1():
    assert JudgeResult(quality="85").quality == 0.85
    assert JudgeResult(quality=0.7).quality == 0.7
    assert JudgeResult(quality="nonsense").quality == 50.0 / 100  # _clamp midpoint → 0.5


def test_tom_read_clamps_ranges():
    g = ToMRead(opponent_id="b", est_opinion=5.0, est_openness=9.0)
    assert g.est_opinion == 1.0 and g.est_openness == 1.0
    g2 = ToMRead(opponent_id="c", est_opinion=-3.0)
    assert g2.est_opinion == -1.0


def test_argument_clamps_strength():
    assert ArgumentOut(claim="c", strength=2.0).strength == 1.0


def test_parse_list_drops_malformed():
    rows = [{"opponent_id": "b"}, {"no_id": 1}, "not-a-dict"]
    out = parse_list(ToMRead, rows)
    assert len(out) == 1 and out[0].opponent_id == "b"


# --- observability ---------------------------------------------------------- #
def test_build_record_flattens_event():
    rec = obs.build_record({"type": "strategy", "name": "Marian", "juror_id": "j1",
                            "target": "Priya", "tactic": "attack_weakest", "extra": "x"})
    assert rec["type"] == "strategy" and rec["who"] == "Marian"
    assert rec["target"] == "Priya" and rec["tactic"] == "attack_weakest"
    assert "extra" not in rec                       # only whitelisted fields kept


# --- offline eval harness --------------------------------------------------- #
def test_run_eval_returns_aggregate(monkeypatch):
    report = evalrun.run_eval(n_games=1, rounds=1)
    assert report["n_games"] == 1
    for k in ("avg_convergence", "avg_polarization", "avg_belief_movement"):
        assert k in report and isinstance(report[k], float)
    assert len(report["games"]) == 1
