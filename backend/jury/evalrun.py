"""Offline eval harness — run K deliberations with the stub LLM and aggregate CDA
metrics (convergence, polarization, total belief movement). No API key / network.

A first step toward systematic LLM-agent evaluation: swap StubLLM for a real
provider to grade live deliberations, or assert these aggregates as regression
guards in CI.

    python -m jury.evalrun 5      # 5 games → aggregate report
"""
from __future__ import annotations

import asyncio
import os

from . import engine, metrics
from .cases import get_case
from .personas import scripted_jurors
from .rag import EvidenceRetriever
from .state import GameState
from .stub import StubLLM, offline_embed


async def _one_game(rounds: int) -> dict:
    case = get_case()
    retr = EvidenceRetriever(case.evidence, embed_fn=offline_embed).build()
    state = GameState(case_id=case.id, round=1, jurors=scripted_jurors(case), max_rounds=rounds)
    updates: list[dict] = []
    votes = iter([{"action": "VOTE", "text": "NOT_GUILTY"}] * rounds + [{"action": "EXIT"}])

    async def emit(ev):
        if ev.get("type") == "belief_update":
            updates.append(ev)

    async def act():
        return next(votes, {"action": "EXIT"})

    engine.STREAM_DELAY = 0.0
    final = await engine.run_game(state, case, StubLLM(retr), emit, act)
    opinions = [j.beliefs.opinion for j in final.ai_jurors if j.beliefs is not None]
    return {
        "convergence": metrics.convergence(opinions),
        "polarization": metrics.polarization(opinions),
        "belief_movement": round(sum(abs(u.get("delta", 0.0)) for u in updates), 3),
        "top_influencer": metrics.top_influencer(updates),
    }


def run_eval(n_games: int = 3, rounds: int = 2) -> dict:
    """Run n stub deliberations (beliefs + ToM forced on) and aggregate metrics."""
    prev = {k: os.environ.get(k) for k in ("JURY_BELIEFS", "JURY_TOM")}
    os.environ["JURY_BELIEFS"] = "1"
    os.environ["JURY_TOM"] = "1"
    try:
        games = [asyncio.run(_one_game(rounds)) for _ in range(n_games)]
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def avg(key):
        return round(sum(g[key] for g in games) / len(games), 3) if games else 0.0

    return {
        "n_games": n_games,
        "avg_convergence": avg("convergence"),
        "avg_polarization": avg("polarization"),
        "avg_belief_movement": avg("belief_movement"),
        "games": games,
    }


if __name__ == "__main__":
    import json
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(json.dumps(run_eval(n), indent=2, ensure_ascii=False))
