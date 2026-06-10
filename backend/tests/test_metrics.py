"""Unit tests for CDA metrics (pure functions, no LLM)."""
from __future__ import annotations

from jury import metrics


def test_convergence_full_when_agree():
    assert metrics.convergence([0.6, 0.6, 0.6]) == 1.0
    assert metrics.convergence([0.9]) == 1.0          # singleton


def test_convergence_drops_when_split():
    spread = metrics.convergence([1.0, -1.0, 0.0])
    assert 0.0 <= spread < 0.3                          # wide spread → low convergence


def test_polarization_counts_strong_positions():
    assert metrics.polarization([0.9, -0.8, 0.1, 0.0]) == 0.5   # 2 of 4 strong
    assert metrics.polarization([]) == 0.0


def test_top_influencer_and_edges():
    updates = [
        {"by": "Marian", "juror_id": "j5", "delta": 0.2},
        {"by": "Marian", "juror_id": "j5", "delta": -0.1},
        {"by": "Aisha", "juror_id": "j2", "delta": 0.05},
    ]
    assert metrics.top_influencer(updates) == "Marian"  # 0.3 abs total > 0.05
    edges = metrics.influence_edges(updates)
    marian_j5 = next(e for e in edges if e["by"] == "Marian" and e["to"] == "j5")
    assert marian_j5["weight"] == 0.3                   # |0.2| + |-0.1|


def test_top_influencer_empty():
    assert metrics.top_influencer([]) is None


def test_summary_shape():
    s = metrics.summary([{"by": "a", "juror_id": "b", "delta": 0.3}], [0.5, -0.5])
    assert set(s) == {"convergence", "polarization", "top_influencer", "edges"}
