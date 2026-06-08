"""RAG retrieval: semantically relevant evidence ranks to the top."""
from __future__ import annotations

from conftest import fake_embed

from jury.cases import get_case
from jury.rag import EvidenceRetriever


def _retr():
    return EvidenceRetriever(get_case().evidence, embed_fn=fake_embed).build()


def test_lookup_returns_topk():
    hits = _retr().lookup("fingerprint", k=3)
    assert len(hits.snippets) == 3
    assert len(hits.ids) == 3 == len(hits.scores)


def test_fingerprint_query_finds_fingerprint_evidence():
    hits = _retr().lookup("fingerprint on the broken glass", k=3)
    joined = " ".join(hits.snippets).lower()
    assert "fingerprint" in joined or "print" in joined


def test_alibi_query_finds_alibi_evidence():
    hits = _retr().lookup("alibi girlfriend apartment delivery", k=4)
    joined = " ".join(hits.snippets).lower()
    assert "alibi" in joined or "delivery" in joined or "apartment" in joined


def test_as_text_formats_bullets():
    hits = _retr().lookup("informant", k=2)
    text = hits.as_text()
    assert text.startswith("- ")


def test_k_clamped_to_corpus_size():
    hits = _retr().lookup("anything", k=999)
    assert len(hits.snippets) == len(get_case().evidence)
