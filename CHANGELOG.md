# Changelog

## [0.6.0] - 2026-06-09
### Features — completes the remaining CDA roadmap (all additive + flag-gated)
- **Frontend visibility**: juror cards show an **opinion (lean) + conviction bar**; the
  deliberation stream renders `belief_update` (🧠), `strategy` (🎯), `metrics` (📊),
  `reflection` (🪞) lines and **token-streamed** `speak_delta`. `Juror` gains
  `opinion/conviction/belief_stance`; reducer + i18n (en/zh) extended. Reducer ignores
  unknown events, so all additions are backward-compatible.
- **Metrics** (`jury/metrics.py`, pure): convergence, polarization, top-influencer, and a
  who-convinced-whom edge list; emitted as a `metrics` event before the scorecard.
- **Drive-based scheduler** (`jury/scheduler.py`, pure): speaking order from belief-aware
  drives (reactivity + disagreement-with-room + conviction) when beliefs on; legacy
  `speaking_score` sort otherwise.
- **Response-phase ToM**: rebuttals now run `strategy.move_against` the last speaker
  (targeted), emitting a `strategy` event; `respond()` gains an optional `move`.
- **Toulmin arguments (lite)**: `llm.extract_arguments` populates `BeliefStack.arguments`
  at game start (`JURY_TOM`); ToM's `weakest_point` becomes the lowest-strength argument's
  warrant. Belief math stays scalar (no regression).
- **Fast model tier**: `JuryLLM.fast` (`JURY_FAST_MODEL`) serves judge/ToM/args/reflection
  (structured, unseen calls); generation stays on the big model.
- **Reflection (lite, `JURY_REFLECT`)**: per-round one-line `reflect()` refreshing
  `inner_reasoning`, emitted as `reflection` events.
- **Streaming (`JURY_STREAM`)**: utterances emit as `speak_start`/`speak_delta`/`speak_end`
  (chunked replay in v1; true token-level TTFT streaming is the one remaining deferral).
- Tests: `test_metrics.py`, `test_scheduler.py`, `test_tom.py`, `test_engine_stream.py`
  (+ earlier suites). Full suite **56 passing**.
### Notes & Caveats
- Each capability is gated by its own env flag; the default product path and legacy tests
  are unchanged. Streaming is computed-then-chunked (verifiable offline); swapping in
  true `creative.stream()` token streaming is left as a focused follow-up.
- Still deferred (needs data/GPU, low demo ROI): fine-tuning / RL strategy (ToMAP/OSCToM/
  DebateQD), higher-order ToM, full layered Values→Beliefs→Attitudes stack.

## [0.5.0] - 2026-06-09
### Features
- **CDA v2 — agent Theory of Mind + targeted persuasion** (opt-in, `JURY_TOM=1`;
  requires `JURY_BELIEFS=1`). Closes the v0 gap where the *speaking* side was generic.
  - `jury/tom.py` (NEW): `update_tom(speaker, state, llm, case)` — per-opponent
    `ToMGuess{est_opinion, weakest_point, est_openness}` (EMO-style distinct models);
    LLM inference via `llm.tom_read` with a belief-state heuristic fallback (offline).
  - `jury/strategy.py` (NEW): pure-Python `choose_move(speaker, guesses, state)` →
    `Move{target_id, tactic, target_point}`. Targets the closest disagreeing (most
    reachable) opponent; tactic follows the target's openness (ELM): open→`attack_weakest`,
    closed→`common_ground`.
  - `prompts.py`: `tom_prompt` + a `_targeting` directive appended to `speak_prompt`/
    `respond_prompt` so the generated argument is actually aimed at the target's weak point.
  - `tom_read()` added to the LLM contract (`JuryLLM`/`DeepSeekLLM`/`StubLLM`/`FakeLLM`);
    `speak()` gains an optional `move`.
  - `engine.py`: before each AI turn (when `JURY_TOM`), run ToM → `choose_move` →
    emit a `strategy` event (`who → target, tactic`) → conditioned generation. ToM
    guesses persist on `JurorState.tom`.
  - Tests: `tests/test_strategy.py` (5) + `tests/test_engine_tom.py` (2). Full suite **41 passing**.
### Design Rationale
- **Prompt-only, inference-time** ToM/strategy (grounded in EMO NAACL-2025, "Infusing ToM"
  2025, RebuttalAgent, DuET-PD). Fine-tuning / RL strategy optimization (ToMAP, OSCToM,
  DebateQD) deliberately **deferred** — needs data/GPU, diminishing returns for a demo.
- **Additive + gated** behind a separate `JURY_TOM` flag so v0's belief tests stay pure.
- Models the **mechanism** of strategic persuasion (legible: you see "A targets C's alibi"),
  not a claim of superhuman persuasion — empirical evidence that targeted > generic is mixed.
### Notes & Caveats
- ToM runs for the speaking agent each turn (~+1 small LLM call); make it every-K if tighter.
- Response phase still targets the last speaker directly (no separate ToM there yet).

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
