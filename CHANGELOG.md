# Changelog

## [0.4.0] - 2026-06-09
### Features
- **CDA belief engine (v0)** — opt-in psychologically-grounded persuasion model,
  enabled with `JURY_BELIEFS=1` (default off → legacy behavior untouched).
  - `jury/state.py`: `BeliefStack` (persisted signed `opinion ∈ [-1,1]`; `stance`
    and `conviction` derived), plus `ToulminArg`/`ToMGuess` scaffolding (v1+).
  - `jury/beliefs.py` (NEW): pure-numpy, deterministic `update_belief` applying the
    four gates — **distance** (bounded-confidence ε), **route** (ELM central/peripheral),
    **quality** (judge score), **identity** (dissonance damping, no boomerang) — plus
    `init_beliefs` (persona→ε/identity heuristic) and `propagate`.
  - `judge()` added to the LLM contract (`JuryLLM`/`DeepSeekLLM`/`StubLLM`/test `FakeLLM`)
    + `prompts.judge_prompt`: scores a statement's argument quality (off the visible path).
  - `jury/engine.py`: after each emit, judge the statement and propagate belief
    updates to listeners (`belief_update` events); closing votes become belief-driven
    (skips the extra `revote` LLM call) when beliefs are on.
  - Tests: `tests/test_beliefs.py` (7 pure-function unit tests) + `tests/test_engine_beliefs.py`
    (3 integration tests). Full suite **34 passing**.
### Design Rationale
- **Opinion is the persisted scalar, stance/conviction are derived** — a stance+conviction
  representation flattens an UNDECIDED juror's lean to 0, so small nudges never accumulate;
  persisting the signed opinion lets a swing juror accumulate across speakers and flip.
- **Additive + gated**: the belief loop only activates when jurors carry a `BeliefStack`
  (env opt-in), so the existing 24 tests and the default product behavior are unchanged.
- **No boomerang**: high `identity_stake` damps updates toward zero movement, never reverses
  them (PNAS 2019 shows true backfire is rare; "failure to update" is the realistic default).
### Notes & Caveats
- v0 keeps `arguments` empty (the opinion scalar carries state); Toulmin args, ToM,
  dual-process strategy, token streaming, and the small-model tier are v1/v2 (see plan).
- Belief updates run synchronously after the visible emit; true backgrounding + token
  streaming (the big latency win) land in v1.

## [0.3.0] - 2026-06-08
### Features
- **Multi-provider chat backend.** Added DeepSeek (`jury/deepseek_llm.py`) via the
  OpenAI-compatible API + real OpenAI-style function-calling / ReAct loop for
  `lookup_evidence`. `config.provider()` picks the backend (explicit `JURY_PROVIDER`,
  else inferred from whichever key is set; DeepSeek preferred). `/api/health` reports
  the active provider.
### Design Rationale
- DeepSeek has **no embeddings endpoint**, so when the provider is DeepSeek the RAG
  retriever falls back to the local CJK-aware embedder (`jury/stub.py:offline_embed`)
  — keyword/character overlap, not deep semantic vectors. Juror reasoning is fully
  DeepSeek-generated; only retrieval relevance is weaker than the Gemini path.
### Notes
- `jury/stub.py:offline_embed` now tokenizes CJK characters (+digits), fixing
  zero-vector retrieval for Chinese; StubLLM gives each persona a distinct line so
  the offline demo no longer shows identical statements.

## [0.2.0] - 2026-06-08
### Features
- **Bilingual (EN / 中文)** — language picked on the start screen and locked for the
  session. Backend `lang` propagates through case/evidence/personas (bilingual data
  in `cases.py`/`personas.py`), prompts (`prompts.py` zh+en, explicit reply-language
  directive; machine tags stay English for parsing), the stub LLM, and `/api/cases`
  + `/api/game`. Frontend `i18n.ts` (`TR[lang]`) localizes all UI chrome; a header
  toggle switches language before convening.
### Design Rationale
- No real-time translation: language is chosen at entry, so each game streams in one
  language and Gemini is instructed (in that language) to reply in it — cheaper and
  more coherent than translating streamed content.
- `<vote>` / `<reason>` / rubric dim tags keep English tokens in both languages so
  the regex parser stays language-agnostic.
### Notes
- 24/24 tests pass (defaults are `lang="en"`, so existing tests are unaffected).

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
