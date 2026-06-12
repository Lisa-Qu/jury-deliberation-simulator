"""LangGraph orchestration variant of the deliberation loop (`JURY_LANGGRAPH=1`).

The same phase functions become nodes in a `StateGraph`; a conditional edge decides
round → loop-or-finish. Behaviour-identical to `engine.run_game` because both share
`setup_cda` / `reflect_round` / `_ai_phase` / `_response_phase` / `_human_phase` /
`_closing_votes` / `settle_round` / `finalize`. Opt-in: the server uses this when
`JURY_LANGGRAPH=1` and `langgraph` is installed, else the hand-rolled loop.
"""
from __future__ import annotations

from typing import TypedDict

from . import engine
from .cases import Case
from .state import GameState


class GraphState(TypedDict):
    gs: GameState
    exited: bool


async def run_game_langgraph(state: GameState, case: Case, llm, emit, get_action):
    from langgraph.graph import END, StateGraph

    state, emit, belief_updates = await engine.setup_cda(state, case, llm, emit)
    await emit({"type": "game_start", **state.public()})

    async def round_node(s: GraphState) -> GraphState:
        gs = s["gs"]
        await emit({"type": "round_start", "round": gs.round})
        gs = await engine.reflect_round(gs, case, llm, emit)
        gs = await engine._ai_phase(gs, case, llm, emit)
        gs = await engine._response_phase(gs, case, llm, emit)
        return {"gs": gs, "exited": False}

    async def human_node(s: GraphState) -> GraphState:
        gs, exited = await engine._human_phase(s["gs"], case, llm, emit, get_action)
        return {"gs": gs, "exited": exited}

    async def closing_node(s: GraphState) -> GraphState:
        if s["exited"]:
            return {"gs": s["gs"].finish("exited"), "exited": True}
        gs = await engine._closing_votes(s["gs"], case, llm, emit)
        gs = await engine.settle_round(gs, emit)
        return {"gs": gs, "exited": False}

    def route(s: GraphState) -> str:
        return "end" if s["exited"] or s["gs"].verdict_reached else "loop"

    g = StateGraph(GraphState)
    g.add_node("round", round_node)
    g.add_node("human", human_node)
    g.add_node("closing", closing_node)
    g.set_entry_point("round")
    g.add_edge("round", "human")
    g.add_edge("human", "closing")
    g.add_conditional_edges("closing", route, {"loop": "round", "end": END})
    compiled = g.compile()

    out = await compiled.ainvoke({"gs": state, "exited": False},
                                 {"recursion_limit": 100})
    return await engine.finalize(out["gs"], case, llm, emit, belief_updates)
