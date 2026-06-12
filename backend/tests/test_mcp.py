"""MCP evidence server — tool logic + registration."""
from __future__ import annotations

import pytest

import mcp_server


def test_search_evidence_returns_topk():
    out = mcp_server.search_evidence("fingerprint match points", k=2)
    assert len(out) == 2
    assert {"id", "text", "score"} <= set(out[0])
    assert isinstance(out[0]["text"], str) and out[0]["text"]


def test_k_clamped_to_corpus():
    out = mcp_server.search_evidence("evidence", k=999)
    assert 0 < len(out) <= len(mcp_server._case.evidence)


def test_registered_as_mcp_tool():
    if mcp_server.mcp is None:
        pytest.skip("mcp SDK not installed")
    assert mcp_server.mcp.name == "jury-evidence"
