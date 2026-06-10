"""LLM access layer.

Wraps LangChain `ChatGoogleGenerativeAI` (Gemini). The `speak` step runs a REAL
function-calling / ReAct loop: the juror model is given the `lookup_evidence`
tool via `bind_tools`; when it requests a call we surface it (callbacks → SSE
events), execute the RAG retrieval ourselves, feed a ToolMessage back, and let
the model produce a grounded statement. Every call is wrapped in a fallback so a
transient API/parse failure degrades gracefully instead of crashing the game.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from . import prompts
from .cases import Case
from .rag import EvidenceRetriever, Hits
from .state import GameState, JurorState, Vote

VOTES = ("GUILTY", "NOT_GUILTY", "UNDECIDED")


# --------------------------------------------------------------------------- #
# Parsing helpers (structured output via tags / JSON).
# --------------------------------------------------------------------------- #
def extract_tag(text: str, tag: str, default: str = "") -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S | re.I)
    return m.group(1).strip() if m else default


def parse_vote(text: str, fallback: Vote = "UNDECIDED") -> Vote:
    raw = extract_tag(text, "vote").upper().replace(" ", "_").replace("-", "_")
    return raw if raw in VOTES else fallback  # type: ignore[return-value]


def clean_statement(text: str) -> str:
    """Strip thinking blocks and machine tags, leaving the spoken statement."""
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.S | re.I)
    text = re.sub(r"<(vote|reason)>.*?</\1>", "", text, flags=re.S | re.I)
    return text.strip()


def clamp_score(raw: str, default: int = 60) -> int:
    try:
        return max(0, min(100, int(round(float(re.sub(r"[^\d.\-]", "", raw) or default)))))
    except (ValueError, TypeError):
        return default


def prefetch_query(juror, move, case) -> str:
    """Heuristic RAG query for low-latency streaming pre-fetch (no model round-trip):
    aim at the target's weak point if known, else the juror's bias, else the charge."""
    tp = getattr(move, "target_point", "") if move else ""
    return (tp or juror.persona.bias or case.charge or "case evidence").strip()


# --------------------------------------------------------------------------- #
# The lookup tool schema (body unused — we execute retrieval manually so we can
# emit tool_call / tool_result events; binding only declares the schema).
# --------------------------------------------------------------------------- #
@tool
def lookup_evidence(query: str) -> str:
    """Search the case evidence file and return the most relevant excerpts.
    Call this BEFORE asserting any disputed fact (fingerprint, timeline, alibi,
    witness reliability, pawn record, etc.)."""
    return ""


class JuryLLM:
    """Real Gemini-backed LLM. Engine can swap in a fake for tests (duck-typed)."""

    def __init__(self, retriever: EvidenceRetriever, model: str | None = None,
                 lang: str = "en"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = model or os.environ.get("JURY_MODEL", "gemini-1.5-flash")
        fast_model = os.environ.get("JURY_FAST_MODEL", model)  # cheap tier for internal calls
        self.retriever = retriever
        self.lang = lang
        self.creative = ChatGoogleGenerativeAI(model=model, temperature=0.85)
        self.precise = ChatGoogleGenerativeAI(model=model, temperature=0.3)
        # judge / ToM / argument-extraction / reflection are structured + unseen → fast tier
        self.fast = ChatGoogleGenerativeAI(model=fast_model, temperature=0.2)
        self.tooled = self.creative.bind_tools([lookup_evidence])
        self.errors: list[dict] = []

    # --- fallback wrapper ------------------------------------------------- #
    def _safe(self, fn: Callable, *, fallback, stage: str):
        last = None
        for _ in range(2):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 — degrade, never crash the game
                last = e
        self.errors.append(
            {"type": "error", "stage": stage,
             "message": str(last)[:200], "recovered": True}
        )
        return fallback

    def drain_errors(self) -> list[dict]:
        errs, self.errors = self.errors, []
        return errs

    # --- juror turn steps ------------------------------------------------- #
    def think(self, juror: JurorState, state: GameState, case: Case) -> str:
        def run():
            msgs = [SystemMessage(prompts.persona_system(juror, case, self.lang)),
                    HumanMessage(prompts.think_prompt(juror, state, case, self.lang))]
            return self.precise.invoke(msgs).content.strip()

        return self._safe(run, fallback="(weighing the evidence...)", stage="think")

    def _statement(
        self,
        juror: JurorState,
        case: Case,
        human_prompt: str,
        on_tool_call: Callable[[str], None],
        on_tool_result: Callable[[Hits], None],
        stage: str,
    ) -> tuple[str, Vote]:
        """Shared tool-calling / ReAct loop used by both speak and respond:
        invoke → (model requests lookup_evidence → we retrieve & feed a
        ToolMessage back)* → grounded statement."""
        def run() -> tuple[str, Vote]:
            msgs = [SystemMessage(prompts.persona_system(juror, case, self.lang)),
                    HumanMessage(human_prompt)]
            ai: AIMessage = self.tooled.invoke(msgs)
            hops = 0
            while getattr(ai, "tool_calls", None) and hops < 3:
                hops += 1
                msgs.append(ai)
                for tc in ai.tool_calls:
                    query = str(tc.get("args", {}).get("query", "")).strip()
                    on_tool_call(query)
                    hits = self.retriever.lookup(query)
                    on_tool_result(hits)
                    msgs.append(ToolMessage(content=hits.as_text(),
                                            tool_call_id=tc.get("id", "0")))
                ai = self.tooled.invoke(msgs)
            text = ai.content if isinstance(ai.content, str) else str(ai.content)
            return clean_statement(text) or "(no comment)", parse_vote(text, juror.vote)

        return self._safe(run, fallback=("(I'll hold my position for now.)", juror.vote),
                          stage=stage)

    def speak(self, juror, state, case, on_tool_call, on_tool_result, move=None) -> tuple[str, Vote]:
        return self._statement(juror, case,
                               prompts.speak_prompt(juror, state, case, self.lang, move),
                               on_tool_call, on_tool_result, stage="speak")

    def respond(self, juror, state, case, target_name, target_text,
                on_tool_call, on_tool_result, move=None) -> tuple[str, Vote]:
        prompt = prompts.respond_prompt(juror, state, case, target_name, target_text, self.lang, move)
        return self._statement(juror, case, prompt, on_tool_call, on_tool_result,
                               stage="respond")

    def stream_speak(self, juror, state, case, move, on_tool_call, on_tool_result):
        """TRUE low-latency token streaming (Gemini): RAG-PRE-FETCH evidence with a
        numpy lookup (instant), inject it, then ONE streamed call — so the first
        token reaches the user without waiting on a model-driven tool loop."""
        query = prefetch_query(juror, move, case)
        on_tool_call(query)
        hits = self.retriever.lookup(query)
        on_tool_result(hits)
        user = (prompts.speak_prompt(juror, state, case, self.lang, move)
                + "\n\nRetrieved evidence:\n" + hits.as_text())
        msgs = [SystemMessage(prompts.persona_system(juror, case, self.lang)),
                HumanMessage(user)]
        for chunk in self.creative.stream(msgs):
            piece = chunk.content if isinstance(chunk.content, str) else ""
            if piece:
                yield piece

    def revote(self, juror: JurorState, state: GameState, case: Case) -> tuple[Vote, str]:
        def run() -> tuple[Vote, str]:
            msgs = [SystemMessage(prompts.persona_system(juror, case, self.lang)),
                    HumanMessage(prompts.vote_prompt(juror, state, case, self.lang))]
            out = self.precise.invoke(msgs).content
            return parse_vote(out, juror.vote), extract_tag(out, "reason", "")

        return self._safe(run, fallback=(juror.vote, ""), stage="vote")

    def hint(self, state: GameState, case: Case) -> str:
        def run():
            return self.precise.invoke(
                [HumanMessage(prompts.hint_prompt(state, case, self.lang))]
            ).content.strip()

        return self._safe(run, fallback="Consider whether the prosecution truly met "
                          "'beyond a reasonable doubt' — name one weak piece of evidence.",
                          stage="hint")

    def judge(self, statement: str, case: Case) -> dict:
        """CDA influence evaluator — score a statement's argument quality (0..1)
        and flag fallacies. Off the visible path; feeds the belief-update engine."""
        def run() -> dict:
            out = self.fast.invoke(
                [HumanMessage(prompts.judge_prompt(statement, case, self.lang))]
            ).content
            return {"quality": clamp_score(extract_tag(out, "quality"), 50) / 100.0,
                    "fallacy": extract_tag(out, "fallacy", "none")}

        return self._safe(run, fallback={"quality": 0.5, "fallacy": "none"}, stage="judge")

    def tom_read(self, juror: JurorState, state: GameState, case: Case) -> list[dict]:
        """CDA Theory of Mind — infer each opponent's mind from the transcript.
        Returns a list of {opponent_id, est_opinion, weakest_point, est_openness}."""
        def run() -> list[dict]:
            out = self.fast.invoke(
                [HumanMessage(prompts.tom_prompt(juror, state, case, self.lang))]
            ).content
            block = re.search(r"\[.*\]", out, re.S)
            return json.loads(block.group(0) if block else out)

        return self._safe(run, fallback=[], stage="tom")

    def extract_arguments(self, juror: JurorState, case: Case) -> list[dict]:
        """CDA Toulmin extraction — the juror's supporting arguments at game start.
        Returns a list of {claim, grounds, warrant, strength}."""
        def run() -> list[dict]:
            out = self.fast.invoke(
                [HumanMessage(prompts.args_prompt(juror, case, self.lang))]
            ).content
            block = re.search(r"\[.*\]", out, re.S)
            return json.loads(block.group(0) if block else out)

        return self._safe(run, fallback=[], stage="args")

    def reflect(self, juror: JurorState, state: GameState, case: Case) -> str:
        """CDA periodic reflection — one-line synthesis, refreshes inner_reasoning."""
        def run() -> str:
            return self.fast.invoke(
                [HumanMessage(prompts.reflect_prompt(juror, state, self.lang))]
            ).content.strip()

        return self._safe(run, fallback=juror.inner_reasoning, stage="reflect")

    def generate_personas(self, case: Case, n: int) -> list[dict]:
        def run() -> list[dict]:
            out = self.creative.invoke(
                [HumanMessage(prompts.rolegen_prompt(case, n, self.lang))]
            ).content
            block = re.search(r"\[.*\]", out, re.S)
            data = json.loads(block.group(0) if block else out)
            return data[:n]

        return self._safe(run, fallback=[], stage="rolegen")

    def rubric(self, case: Case, human_lines: str, state: GameState) -> dict:
        def run() -> dict:
            out = self.precise.invoke(
                [HumanMessage(prompts.rubric_prompt(case, human_lines, state, self.lang))]
            ).content
            dims = {
                "persuasiveness": clamp_score(extract_tag(out, "persuasiveness")),
                "evidence_use": clamp_score(extract_tag(out, "evidence_use")),
                "consistency": clamp_score(extract_tag(out, "consistency")),
                "engagement": clamp_score(extract_tag(out, "engagement")),
                "open_mindedness": clamp_score(extract_tag(out, "open_mindedness")),
            }
            recap = extract_tag(out, "recap", "The jury reached the end of deliberation.")
            total = round(sum(dims.values()) / len(dims))
            return {"dims": dims, "total": total, "recap": recap}

        fallback = {
            "dims": {k: 60 for k in
                     ["persuasiveness", "evidence_use", "consistency",
                      "engagement", "open_mindedness"]},
            "total": 60, "recap": "Scoring unavailable; deliberation completed.",
        }
        return self._safe(run, fallback=fallback, stage="rubric")
