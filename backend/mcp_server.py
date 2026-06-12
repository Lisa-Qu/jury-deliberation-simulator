"""MCP server — exposes the case-evidence RAG tool over the Model Context Protocol.

Run:  python backend/mcp_server.py        (stdio transport)
Any MCP client (Claude Desktop, an agent runtime, etc.) can then call
`lookup_evidence`. Self-contained: uses the offline embedder, so no API key needed.

This is the same retrieval the jurors use, re-exposed as a standard, reusable MCP
tool instead of an in-process call.
"""
from __future__ import annotations

from jury.cases import get_case
from jury.rag import EvidenceRetriever
from jury.stub import offline_embed

_case = get_case()
_retriever = EvidenceRetriever(_case.evidence, embed_fn=offline_embed).build()


def search_evidence(query: str, k: int = 3) -> list[dict]:
    """Search the case evidence file and return the top-k most relevant excerpts.

    Args:
        query: what to look up (fingerprint, alibi, timeline, witness, …).
        k: how many excerpts to return.
    """
    hits = _retriever.lookup(query, k=k)
    return [{"id": i, "text": s, "score": round(sc, 3)}
            for i, s, sc in zip(hits.ids, hits.snippets, hits.scores)]


try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("jury-evidence")
    mcp.tool()(search_evidence)        # register `search_evidence` as an MCP tool
except ImportError:                    # mcp SDK is optional
    mcp = None


def main() -> None:
    if mcp is None:
        raise SystemExit("mcp SDK not installed — `pip install mcp`")
    mcp.run()


if __name__ == "__main__":
    main()
