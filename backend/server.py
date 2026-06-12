"""FastAPI server: create game / SSE event stream / human action.

Each game runs as a background task. The engine pushes events into `session.out`
(drained by the SSE endpoint) and pauses on `session.inbox` for human actions
(fed by the action endpoint). State is held in-memory per process — fine for a
local demo; not horizontally scalable (noted in README).
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from jury import cases, config, engine, obs, personas
from jury.llm import JuryLLM
from jury.rag import EvidenceRetriever
from jury.state import GameState

config.ensure_env()

app = FastAPI(title="Jury Deliberation Simulator")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)


@dataclass
class GameSession:
    id: str
    out: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)
    inbox: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    done: bool = False


GAMES: dict[str, GameSession] = {}


def _fake_mode() -> bool:
    return os.environ.get("JURY_FAKE_LLM", "").lower() in ("1", "true", "yes")


def _max_rounds() -> int:
    return int(os.environ.get("JURY_MAX_ROUNDS", "4"))


class CreateReq(BaseModel):
    mode: str = "scripted"          # "scripted" | "dynamic"
    case_id: str | None = None
    lang: str = "en"                # "en" | "zh"


class ActionReq(BaseModel):
    action: str                     # SPEAK | VOTE | REJECT | EXIT | HINT
    text: str | None = ""


async def _run(session: GameSession, mode: str, case_id: str | None, lang: str) -> None:
    try:
        case = cases.get_case(case_id, lang)
        if _fake_mode():
            from jury.stub import StubLLM, offline_embed
            retriever = EvidenceRetriever(case.evidence, embed_fn=offline_embed)
            await asyncio.to_thread(retriever.build)
            llm = StubLLM(retriever, lang=lang)
        elif config.provider() == "deepseek":
            # DeepSeek has no embeddings endpoint → RAG uses the local CJK embedder.
            from jury.deepseek_llm import DeepSeekLLM
            from jury.stub import offline_embed
            retriever = EvidenceRetriever(case.evidence, embed_fn=offline_embed)
            await asyncio.to_thread(retriever.build)
            llm = DeepSeekLLM(retriever, lang=lang)
        else:
            retriever = EvidenceRetriever(case.evidence)
            await asyncio.to_thread(retriever.build)    # embed evidence up front
            llm = JuryLLM(retriever, lang=lang)
        jurors = await asyncio.to_thread(personas.build_jurors, case, mode, llm, lang)
        state = GameState(case_id=case.id, round=1, jurors=jurors, max_rounds=_max_rounds())

        async def emit(ev: dict) -> None:
            obs.trace_event(ev)            # structured tracing when JURY_TRACE=1
            await session.out.put(ev)

        async def get_action() -> dict:
            return await session.inbox.get()

        await engine.run_game(state, case, llm, emit, get_action)
    except Exception as e:  # noqa: BLE001 — surface fatal errors to the client
        await session.out.put(
            {"type": "error", "stage": "fatal", "message": str(e)[:300], "recovered": False}
        )
    finally:
        session.done = True
        await session.out.put({"type": "_eof"})


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "has_key": config.has_key(), "fake": _fake_mode(),
            "provider": "stub" if _fake_mode() else config.provider()}


@app.get("/api/cases")
def list_cases(lang: str = "en") -> list[dict]:
    return [cases.get_case(cid, lang).public() for cid in cases.CASES]


@app.post("/api/game")
async def create_game(req: CreateReq) -> dict:
    if not config.has_key() and not _fake_mode():
        raise HTTPException(
            500, "GEMINI_API_KEY not set. Copy backend/.env.example to .env and fill it in."
        )
    if req.case_id and req.case_id not in cases.CASES:
        raise HTTPException(404, "unknown case_id")
    gid = uuid.uuid4().hex[:12]
    session = GameSession(id=gid)
    GAMES[gid] = session
    session.task = asyncio.create_task(_run(session, req.mode, req.case_id, req.lang))
    return {"game_id": gid, "case": cases.get_case(req.case_id, req.lang).public(),
            "mode": req.mode, "lang": req.lang}


@app.get("/api/game/{gid}/stream")
async def stream(gid: str):
    session = GAMES.get(gid)
    if not session:
        raise HTTPException(404, "no such game")

    async def gen():
        while True:
            ev = await session.out.get()
            if ev.get("type") == "_eof":
                break
            yield {"event": "message", "data": json.dumps(ev, ensure_ascii=False)}

    return EventSourceResponse(gen())


@app.post("/api/game/{gid}/action")
async def post_action(gid: str, req: ActionReq) -> dict:
    session = GAMES.get(gid)
    if not session:
        raise HTTPException(404, "no such game")
    if session.done:
        raise HTTPException(409, "game already finished")
    await session.inbox.put({"action": req.action, "text": req.text or ""})
    return {"ok": True}
