"""Offline deterministic LLM stub (no network, no API key).

Enabled via JURY_FAKE_LLM=1 — lets the full HTTP + SSE + engine pipeline run for
CI / boot-smoke / offline demos when a Gemini key isn't available. Duck-types
JuryLLM. RAG still runs for real over a local hashing embedder so tool_call /
tool_result events fire exactly as in live mode.
"""
from __future__ import annotations

import re

import numpy as np


def offline_embed(text: str, dim: int = 512):
    v = np.zeros(dim)
    for tok in re.findall(r"[a-z]+", text.lower()):
        v[hash(tok) % dim] += 1.0
    return v


class StubLLM:
    def __init__(self, retriever):
        self.retriever = retriever
        self.errors: list[dict] = []

    def think(self, juror, state, case):
        return f"{juror.persona.name} weighs the fingerprint match against the alibi."

    def speak(self, juror, state, case, on_tool_call, on_tool_result):
        on_tool_call("fingerprint match reliability")
        hits = self.retriever.lookup("fingerprint 9 point match standard", k=2)
        on_tool_result(hits)
        return (f"{juror.persona.name}: the print is only a 9-point match, below the "
                f"lab standard — I lean {juror.vote.replace('_', ' ')}.", juror.vote)

    def respond(self, juror, state, case, target_name, target_text,
                on_tool_call, on_tool_result):
        on_tool_call("alibi delivery receipt")
        hits = self.retriever.lookup("alibi girlfriend delivery receipt phone tower", k=1)
        on_tool_result(hits)
        return (f"{juror.persona.name} to {target_name}: the delivery receipt and phone "
                f"tower complicate that.", juror.vote)

    def revote(self, juror, state, case):
        return juror.vote, "holding my position"

    def hint(self, state, case):
        return "Press the gap between the 9-point print match and the lab's 12-point standard."

    def generate_personas(self, case, n):
        return []

    def rubric(self, case, human_lines, state):
        dims = {k: 72 for k in
                ["persuasiveness", "evidence_use", "consistency",
                 "engagement", "open_mindedness"]}
        return {"dims": dims, "total": 72, "recap": "Offline demo deliberation completed."}

    def drain_errors(self):
        errs, self.errors = self.errors, []
        return errs
