"""CDA deliberation metrics — pure Python, no LLM. Summarize who-moved-whom and
how far the room converged. Fed the belief_update records the engine captured.
"""
from __future__ import annotations

import statistics


def influence_edges(updates: list[dict]) -> list[dict]:
    """updates: list of {by, juror_id, delta}. → [{by, to, weight}] (summed |delta|)."""
    agg: dict[tuple[str, str], float] = {}
    for u in updates:
        by, to = u.get("by"), u.get("juror_id")
        if by is None or to is None:
            continue
        agg[(by, to)] = agg.get((by, to), 0.0) + abs(float(u.get("delta", 0.0)))
    return [{"by": b, "to": t, "weight": round(w, 3)} for (b, t), w in agg.items()]


def top_influencer(updates: list[dict]) -> str | None:
    tot: dict[str, float] = {}
    for u in updates:
        by = u.get("by")
        if by is None:
            continue
        tot[by] = tot.get(by, 0.0) + abs(float(u.get("delta", 0.0)))
    return max(tot, key=tot.get) if tot else None


def convergence(opinions: list[float]) -> float:
    """1.0 = everyone agrees, → 0 as opinions spread apart. opinions in [-1, 1]."""
    if len(opinions) < 2:
        return 1.0
    return round(max(0.0, 1.0 - statistics.pstdev(opinions)), 3)


def polarization(opinions: list[float]) -> float:
    """Fraction of jurors holding a strong (|opinion| > 0.5) position."""
    if not opinions:
        return 0.0
    return round(sum(1 for o in opinions if abs(o) > 0.5) / len(opinions), 3)


def summary(updates: list[dict], opinions: list[float]) -> dict:
    return {
        "convergence": convergence(opinions),
        "polarization": polarization(opinions),
        "top_influencer": top_influencer(updates),
        "edges": influence_edges(updates),
    }
