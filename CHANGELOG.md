# Changelog

## [0.1.0] - 2026-06-05
### Features
- Refactored the Kaggle GenAI Capstone notebook into a front-/back-end app:
  - `backend/jury/` engine package (state, cases, personas, prompts, rag, llm,
    eval, engine) + FastAPI `server.py` with SSE streaming.
  - `frontend/` React + Vite + Tailwind UI: juror cards, deliberation stream,
    evidence panel with retrieval highlighting, vote tally, scorecard.
- Added a **RAG evidence-lookup tool**: Gemini `text-embedding-004` embeddings,
  in-memory cosine top-k retrieval, exposed via LangChain `bind_tools` and driven
  by a manual **function-calling / ReAct loop** (think → tool → observe → speak).
- Added a score-gated **response phase**: the juror whose `responding_score`
  crosses a threshold interjects a direct rebuttal (real cross-agent interaction).
- Added `respond_prompt` (6 prompt templates total: speak/respond/vote/hint/
  recap/rolegen).
- LLM-as-a-Judge rubric scoring (5 dims, 0–100) + recap.
- Multi-level fallback on every LLM call (retry + parse fallback + error events).
- Plugin-free pytest suite (asyncio via `asyncio.run`): RAG, engine/ReAct events,
  fallback, API surface.
- Offline stub mode (`JURY_FAKE_LLM=1`) + `JURY_MAX_ROUNDS`: run the whole
  HTTP+SSE+engine pipeline with no API key (RAG via a local embedder) for CI/demos.
  `python-dotenv` import made optional.

### Design Rationale
- **Async generator engine + asyncio.Queue** for human turns: keeps the
  deliberation a single readable loop while supporting web interactivity and SSE
  streaming, instead of a blocking `while/input()` notebook loop.
- **Manual ReAct tool-loop** (rather than `enable_automatic_function_calling`):
  lets us surface `tool_call` / `tool_result` as discrete events for the UI trace.
- **Immutable frozen dataclasses** for all game state: no in-place mutation,
  easy reasoning about round-to-round transitions.

### Notes & Caveats
- Live mode only (needs `GEMINI_API_KEY`); in-memory single-process game store.
- The loop is hand-rolled; LangGraph is intentionally **not** used.
- PyPI was proxy-blocked at build time, so backend deps were validated across
  existing conda envs (`base` for rag/engine pytest; `quant` for llm/server
  import); frontend built clean via `npm run build`.
