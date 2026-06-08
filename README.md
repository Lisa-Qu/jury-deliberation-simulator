# ⚖️ Jury Deliberation Simulator

A playable, web-based **multi-agent LLM jury room**. Five AI jurors — each with a
distinct persona, cognitive bias, and leaning — deliberate a criminal case
alongside *you*, the human juror. The jurors **look evidence up with a tool**
before they argue (RAG + function calling + ReAct), shift their votes round by
round, and an **LLM-as-a-Judge** grades your participation at the end.

> Refactored and extended from a Kaggle GenAI Capstone notebook into a
> front-/back-end application.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE%20streaming-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Vite%20%2B%20TS-61DAFB?logo=react&logoColor=black)
![Gemini](https://img.shields.io/badge/Gemini-1.5%20Flash-8E75B2?logo=googlegemini&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-bind__tools-1C3C3C?logo=langchain&logoColor=white)
![Tests](https://img.shields.io/badge/tests-24%20passing-2ea44f)

---

## ✨ Highlights

- **Multi-Agent deliberation** — 5 LLM juror agents + 1 human, turn-based rounds,
  score-driven speaking order and response interjections.
- **RAG evidence tool** — case evidence embedded with Gemini `text-embedding-004`,
  cosine top-k retrieval, exposed to jurors via LangChain `bind_tools`
  (Gemini-native **function calling**).
- **ReAct loop** — think → call `lookup_evidence` → observe → grounded statement,
  streamed live to the UI as a visible trace.
- **LLM-as-a-Judge** — 5-dimension rubric (0–100) scores your performance + recap.
- **Robust** — every LLM call has retry + parse fallback + surfaced error events;
  a flaky API never crashes the game.
- **Live streaming UI** — FastAPI **SSE** backend, **React + Vite** front-end with
  juror cards, evidence highlighting, vote tally, and the ReAct trace.

## 🧱 Architecture

```mermaid
flowchart LR
    subgraph BROWSER["🖥️ Browser — React + Vite + TS"]
        UI["Juror cards · Evidence panel<br/>Vote tally · ReAct trace"]
        RED["gameReducer<br/>EventSource (SSE)"]
        UI --- RED
    end

    subgraph API["⚙️ FastAPI — server.py"]
        direction TB
        EP1["POST /api/game<br/><i>create</i>"]
        EP2["GET /api/game/:id/stream<br/><i>SSE events out</i>"]
        EP3["POST /api/game/:id/action<br/><i>human turn in</i>"]
        Q(["asyncio.Queue<br/>human actions"])
        ENG["jury engine<br/>async generator · per-game GameState"]
        EP1 --> ENG
        EP3 --> Q --> ENG
        ENG --> EP2
    end

    subgraph GEM["🤖 Google Gemini"]
        GEN["gemini-1.5-flash<br/>bind_tools"]
        EMB["text-embedding-004"]
    end

    RED -- "① create" --> EP1
    RED -. "② open stream" .-> EP2
    RED -- "③ Speak / Vote / Hint" --> EP3
    EP2 == "events" ==> RED
    ENG -- "ReAct / function calling" --> GEN
    ENG -- "RAG embed + cosine top-k" --> EMB

    classDef browser fill:#e7f0ff,stroke:#3b82f6,color:#1e3a8a;
    classDef api fill:#e9fbf4,stroke:#10b981,color:#065f46;
    classDef gem fill:#f3eafc,stroke:#8e75b2,color:#4c1d95;
    class UI,RED browser;
    class EP1,EP2,EP3,Q,ENG api;
    class GEN,EMB gem;
```

The engine is an async coroutine that streams structured events through `emit`
and **pauses on `await get_human_action()`** when it's your turn.

## 🔄 The deliberation loop

Each round cycles through four phases. Speaking order and cross-juror rebuttals
are **score-driven**, so the room reshuffles every round instead of replaying a
fixed script.

<p align="center">
  <img src="docs/deliberation-loop.png" alt="Multi-agent LLM jury deliberation loop" width="820">
</p>

<details>
<summary>📐 Mermaid source</summary>

```mermaid
flowchart LR
    RS([📣 round_start]) --> AI[🗣️ AI phase<br/>speak by score]
    AI --> RESP{resp_score<br/>≥ 0.6?}
    RESP -- yes --> INT[💬 rebuttal]
    RESP -- no --> HUMAN[🧑‍⚖️ Human turn]
    INT --> HUMAN
    HUMAN -- "Exit" --> SCORE
    HUMAN -- "Vote / Reject" --> CV[🗳️ Closing votes]
    CV --> TALLY{tally}
    TALLY -- "split" --> RS
    TALLY -- "unanimous / hung" --> SCORE[📊 LLM-as-Judge<br/>scorecard]
    SCORE --> DONE([✅ done])

    classDef phase fill:#eef2ff,stroke:#6366f1,color:#3730a3;
    classDef gate fill:#fff7ed,stroke:#f59e0b,color:#92400e;
    class AI,INT,HUMAN,CV,SCORE phase;
    class RESP,TALLY gate;
```

</details>

> **Score dynamics:** after a juror speaks, their `speaking_score` decays (×0.6)
> while everyone else's `responding_score` climbs (+0.08). Your human input nudges
> every responder up (+0.05) — so talking actually changes who speaks next.

## 🔍 Anatomy of a juror turn — RAG + function calling + ReAct

A juror never argues from thin air. Every statement runs a **think → call tool →
observe → speak** loop, and each step is emitted as a discrete event so the UI
can render the reasoning trace live.

```mermaid
sequenceDiagram
    autonumber
    participant ENG as Engine
    participant LLM as JuryLLM · gemini-1.5-flash
    participant TOOL as lookup_evidence (bind_tools)
    participant RAG as EvidenceRetriever

    ENG->>LLM: think(juror, state, case)
    LLM-->>ENG: 💭 thinking event
    ENG->>LLM: speak() — tools bound
    LLM->>TOOL: 🔧 tool_call · lookup_evidence(query)
    TOOL->>RAG: embed query → cosine top-k
    RAG-->>TOOL: snippets + similarity scores
    TOOL-->>LLM: 📎 tool_result (observe)
    LLM-->>ENG: 🗣️ grounded statement + vote
    ENG->>ENG: emit speak · update transcript & scores
    Note over ENG,RAG: Every LLM call is wrapped in retry + parse-fallback — failures surface as error events and never crash the game
```

## 🚀 Run it (local, live Gemini)

Get a free key from Google AI Studio.

**Backend**
```bash
cd backend
cp .env.example .env          # paste your GEMINI_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload   # http://localhost:8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Open http://localhost:5173, *Convene the jury*, watch the jurors deliberate and
pull evidence, then take your turn (Speak / Hint / Vote / Abstain / Exit).

**Terminal-only smoke test** (no frontend): `cd backend && python cli.py`

**Offline mode (no API key)** — boot the full HTTP + SSE + engine pipeline with a
deterministic stub LLM (RAG still runs over a local embedder), useful for CI /
demos:
```bash
JURY_FAKE_LLM=1 uvicorn server:app   # create a game; jurors deliberate without Gemini
```

> If requests to `localhost` return a proxy **403** (e.g. a squid proxy intercepts
> everything), set `no_proxy=localhost,127.0.0.1` before running.

## 🧪 Tests

```bash
cd backend && pytest          # RAG retrieval · engine/ReAct events · fallback · API
```

## 🔍 How the resume claims map to code

| Claim | Where |
|---|---|
| 5 jurors + human, dual init mode | `jury/personas.py` |
| Gemini 1.5 Flash / text-embedding-004 | `jury/llm.py`, `jury/rag.py` |
| RAG cosine top-k | `jury/rag.py` `EvidenceRetriever.lookup` |
| `bind_tools` + manual ReAct tool-loop | `jury/llm.py` `_statement` |
| 6 prompt templates (speak/respond/vote/hint/recap/rolegen) | `jury/prompts.py` |
| immutable frozen dataclass + TypedDict | `jury/state.py` |
| LLM-as-a-Judge rubric | `jury/eval.py`, `jury/llm.py` `rubric` |
| multi-level fallback | `jury/llm.py` `_safe` |
| SSE streaming + React viz | `server.py`, `frontend/src/` |

## ⚠️ Notes & caveats

- **Live mode only** — needs a Gemini API key; calls Google in real time.
- **In-memory game store** (`server.py` `GAMES` dict) — single process, fine for a
  local demo, not horizontally scalable.
- The `JurorState` is a frozen dataclass with a TypedDict serialization shape;
  the deliberation loop is hand-rolled (it does **not** use LangGraph).
