"""Terminal smoke runner — play a full deliberation without the web UI.

    python cli.py        # needs GEMINI_API_KEY in backend/.env

Verifies the real Gemini path: multi-agent turns, evidence tool calls (ReAct),
voting, and the final LLM-as-a-Judge scorecard.
"""
from __future__ import annotations

import asyncio

from jury import cases, config, engine, personas
from jury.llm import JuryLLM
from jury.rag import EvidenceRetriever
from jury.state import GameState

config.ensure_env()


def render(ev: dict) -> None:
    t = ev.get("type")
    name = ev.get("name", "")
    if t == "round_start":
        print(f"\n===== ROUND {ev['round']} =====")
    elif t == "thinking":
        print(f"  💭 {name}: {ev['text']}")
    elif t == "tool_call":
        print(f"  🔧 {name} → lookup_evidence({ev['query']!r})")
    elif t == "tool_result":
        print(f"  📄 retrieved: {', '.join('E' + str(i + 1) for i in ev['evidence_ids'])}")
    elif t == "speak":
        print(f"  🗣  {name} [{ev['vote']}]: {ev['text']}")
    elif t == "vote":
        print(f"  🗳  {name}: {ev['vote']} — {ev.get('reason', '')}")
    elif t == "tally":
        print(f"  📊 {ev['votes']}  ({ev['status']})")
    elif t == "hint":
        print(f"  💡 HINT: {ev['text']}")
    elif t == "error":
        print(f"  ⚠️  [{ev['stage']}] {ev['message']}")
    elif t == "scorecard":
        print(f"\n===== VERDICT: {ev['verdict']} =====")
        print(f"Your score: {ev['total']}/100  {ev['dims']}")
        print(f"Recap: {ev['recap']}")


async def main() -> None:
    case = cases.get_case()
    print(f"CASE: {case.title}\n{case.charge}\n")
    retr = EvidenceRetriever(case.evidence)
    print("Embedding evidence corpus...")
    await asyncio.to_thread(retr.build)
    llm = JuryLLM(retr)
    jurors = personas.build_jurors(case, "scripted", llm)
    state = GameState(case_id=case.id, round=1, jurors=jurors, max_rounds=3)

    async def emit(ev: dict) -> None:
        render(ev)

    async def get_action() -> dict:
        print("\n  YOUR TURN — options: SPEAK <text> | VOTE GUILTY|NOT_GUILTY | "
              "HINT | REJECT | EXIT")
        raw = (await asyncio.to_thread(input, "  > ")).strip()
        if not raw:
            return {"action": "REJECT", "text": ""}
        head, _, tail = raw.partition(" ")
        return {"action": head.upper(), "text": tail.strip()}

    await engine.run_game(state, case, llm, emit, get_action)


if __name__ == "__main__":
    asyncio.run(main())
