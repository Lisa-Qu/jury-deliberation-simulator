"""Shared test fixtures: offline fake embeddings + fake LLM (no API key needed)."""
from __future__ import annotations

import re

import numpy as np
import pytest

from jury import engine
from jury.rag import EvidenceRetriever


def fake_embed(text: str, dim: int = 512):
    """Deterministic hashing-bag-of-words embedding. Shared tokens → high cosine,
    so semantically-overlapping query/evidence rank together — enough to test
    retrieval ordering without a real embedding API."""
    v = np.zeros(dim)
    for tok in re.findall(r"[a-z]+", text.lower()):
        v[hash(tok) % dim] += 1.0
    return v


class FakeLLM:
    """Duck-typed stand-in for JuryLLM. Always triggers one evidence lookup so the
    ReAct trace (tool_call/tool_result) is exercised."""

    def __init__(self, retriever: EvidenceRetriever, forced_vote: str | None = None):
        self.retriever = retriever
        self.forced_vote = forced_vote
        self.errors: list[dict] = []
        self._vc = 0

    def think(self, juror, state, case):
        return f"{juror.persona.name} weighs the evidence."

    def speak(self, juror, state, case, on_tool_call, on_tool_result):
        on_tool_call("evidence relevant to the charge")
        hits = self.retriever.lookup("evidence about the burglary", k=2)
        on_tool_result(hits)
        return (f"{juror.persona.name} argues from the retrieved evidence.",
                self.forced_vote or juror.vote)

    def respond(self, juror, state, case, target_name, target_text,
                on_tool_call, on_tool_result):
        on_tool_call(f"rebut {target_name}")
        hits = self.retriever.lookup("evidence about the burglary", k=1)
        on_tool_result(hits)
        return (f"{juror.persona.name} responds to {target_name}.",
                self.forced_vote or juror.vote)

    def revote(self, juror, state, case):
        if self.forced_vote:
            return self.forced_vote, "settled"
        self._vc += 1                       # alternate → never unanimous → hung
        return ("GUILTY" if self._vc % 2 else "NOT_GUILTY"), "still split"

    def hint(self, state, case):
        return "Point at the 9-point fingerprint match falling below the 12-point standard."

    def rubric(self, case, human_lines, state):
        dims = {k: 70 for k in
                ["persuasiveness", "evidence_use", "consistency",
                 "engagement", "open_mindedness"]}
        return {"dims": dims, "total": 70, "recap": "Engaged and evidence-driven."}

    def generate_personas(self, case, n):
        return []

    def drain_errors(self):
        errs, self.errors = self.errors, []
        return errs


@pytest.fixture(autouse=True)
def _no_stream_delay():
    """Zero the inter-event delay so tests don't sleep."""
    original = engine.STREAM_DELAY
    engine.STREAM_DELAY = 0.0
    yield
    engine.STREAM_DELAY = original


@pytest.fixture
def retriever():
    from jury.cases import get_case
    return EvidenceRetriever(get_case().evidence, embed_fn=fake_embed).build()
