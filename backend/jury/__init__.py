"""Jury Deliberation Simulator — core engine package.

Refactored from the Kaggle GenAI Capstone notebook into a reusable, testable
package: multi-agent LLM jury deliberation with a RAG-backed evidence-lookup
tool (Gemini function calling) and a ReAct turn loop.
"""

__all__ = ["state", "cases", "personas", "prompts", "rag", "llm", "eval", "engine"]
