"""RAG evidence-lookup tool.

Embeds the case evidence corpus with Gemini embeddings (text-embedding-004),
stores vectors in memory, and retrieves the top-k most relevant chunks for a
query by cosine similarity. Exposed to jurors as a function-calling tool in
`llm.py`. `embed_fn` is injectable so tests run without an API key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Sequence

import numpy as np

EmbedFn = Callable[[str], Sequence[float]]


@dataclass(frozen=True)
class Hits:
    ids: list[int]
    snippets: list[str]
    scores: list[float]

    def as_text(self) -> str:
        if not self.snippets:
            return "No matching evidence found."
        return "\n".join(f"- {s}" for s in self.snippets)


@lru_cache(maxsize=1)
def _default_embedder():
    """LangChain Gemini embeddings, built once. Imported lazily so the module
    loads (and tests run) without the dependency / API key present."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    model = os.environ.get("JURY_EMBED_MODEL", "models/text-embedding-004")
    emb = GoogleGenerativeAIEmbeddings(model=model)
    return emb


def _default_embed(text: str) -> Sequence[float]:
    return _default_embedder().embed_query(text)


def _cosine(matrix: np.ndarray, vec: np.ndarray) -> np.ndarray:
    denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(vec)
    denom = np.where(denom == 0, 1e-9, denom)
    return (matrix @ vec) / denom


class EvidenceRetriever:
    """In-memory vector index over a case's evidence chunks."""

    def __init__(self, evidence: Sequence[str], embed_fn: Optional[EmbedFn] = None):
        self.evidence: list[str] = list(evidence)
        self._embed_fn: EmbedFn = embed_fn or _default_embed
        self._vecs: Optional[np.ndarray] = None

    def build(self) -> "EvidenceRetriever":
        """Embed every chunk once and cache the matrix. Idempotent."""
        if self._vecs is None:
            self._vecs = np.array(
                [list(self._embed_fn(e)) for e in self.evidence], dtype=float
            )
        return self

    def lookup(self, query: str, k: int = 3) -> Hits:
        self.build()
        q = np.asarray(list(self._embed_fn(query)), dtype=float)
        sims = _cosine(self._vecs, q)
        k = max(1, min(k, len(self.evidence)))
        idx = np.argsort(sims)[-k:][::-1]
        return Hits(
            ids=[int(i) for i in idx],
            snippets=[self.evidence[i] for i in idx],
            scores=[float(sims[i]) for i in idx],
        )
