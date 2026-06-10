"""DeepSeek LLM backend (OpenAI-compatible API).

DeepSeek exposes an OpenAI-compatible chat endpoint with function calling, so we
drive it via the `openai` SDK (base_url=https://api.deepseek.com). Duck-types
JuryLLM, including a real OpenAI-style tool-calling / ReAct loop for
`lookup_evidence`.

NOTE: DeepSeek has NO embeddings endpoint, so RAG retrieval uses the local
CJK-aware embedder (jury.stub.offline_embed) — keyword/character overlap rather
than deep semantic vectors. Juror reasoning itself is fully DeepSeek-generated.
"""
from __future__ import annotations

import json
import os
from typing import Callable

from . import prompts
from .cases import Case
from .llm import clean_statement, clamp_score, extract_tag, parse_vote
from .rag import EvidenceRetriever, Hits
from .state import GameState, JurorState, Vote

_LOOKUP_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_evidence",
        "description": ("Search the case evidence file and return the most relevant "
                        "excerpts. Call BEFORE asserting any disputed fact (fingerprint, "
                        "timeline, alibi, witness reliability, etc.)."),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "what to look up"}},
            "required": ["query"],
        },
    },
}


class DeepSeekLLM:
    def __init__(self, retriever: EvidenceRetriever, lang: str = "en",
                 model: str | None = None):
        from openai import OpenAI

        self.retriever = retriever
        self.lang = lang
        self.model = model or os.environ.get("JURY_DEEPSEEK_MODEL", "deepseek-chat")
        self.client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        self.errors: list[dict] = []

    # --- fallback wrapper (mirrors JuryLLM._safe) ------------------------- #
    def _safe(self, fn: Callable, *, fallback, stage: str):
        last = None
        for _ in range(2):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001
                last = e
        self.errors.append({"type": "error", "stage": stage,
                            "message": str(last)[:200], "recovered": True})
        return fallback

    def drain_errors(self) -> list[dict]:
        errs, self.errors = self.errors, []
        return errs

    def _chat(self, messages, temperature=0.8, tools=None):
        kwargs = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
        return self.client.chat.completions.create(**kwargs)

    # --- turn steps ------------------------------------------------------- #
    def think(self, juror: JurorState, state: GameState, case: Case) -> str:
        def run():
            msgs = [{"role": "system", "content": prompts.persona_system(juror, case, self.lang)},
                    {"role": "user", "content": prompts.think_prompt(juror, state, case, self.lang)}]
            return (self._chat(msgs, temperature=0.3).choices[0].message.content or "").strip()

        return self._safe(run, fallback="(weighing the evidence...)", stage="think")

    def _statement(self, juror, case, human_prompt, on_tool_call, on_tool_result, stage):
        def run() -> tuple[str, Vote]:
            msgs = [{"role": "system", "content": prompts.persona_system(juror, case, self.lang)},
                    {"role": "user", "content": human_prompt}]
            msg = self._chat(msgs, temperature=0.85, tools=[_LOOKUP_TOOL]).choices[0].message
            hops = 0
            while getattr(msg, "tool_calls", None) and hops < 3:
                hops += 1
                msgs.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name,
                                                 "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls],
                })
                for tc in msg.tool_calls:
                    try:
                        query = json.loads(tc.function.arguments or "{}").get("query", "")
                    except json.JSONDecodeError:
                        query = ""
                    on_tool_call(str(query).strip())
                    hits: Hits = self.retriever.lookup(str(query))
                    on_tool_result(hits)
                    msgs.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": hits.as_text()})
                msg = self._chat(msgs, temperature=0.85, tools=[_LOOKUP_TOOL]).choices[0].message
            text = msg.content or ""
            return clean_statement(text) or "(no comment)", parse_vote(text, juror.vote)

        return self._safe(run, fallback=("(I'll hold my position for now.)", juror.vote),
                          stage=stage)

    def speak(self, juror, state, case, on_tool_call, on_tool_result, move=None):
        return self._statement(juror, case, prompts.speak_prompt(juror, state, case, self.lang, move),
                               on_tool_call, on_tool_result, stage="speak")

    def respond(self, juror, state, case, target_name, target_text,
                on_tool_call, on_tool_result):
        prompt = prompts.respond_prompt(juror, state, case, target_name, target_text, self.lang)
        return self._statement(juror, case, prompt, on_tool_call, on_tool_result, stage="respond")

    def revote(self, juror, state, case) -> tuple[Vote, str]:
        def run():
            msgs = [{"role": "system", "content": prompts.persona_system(juror, case, self.lang)},
                    {"role": "user", "content": prompts.vote_prompt(juror, state, case, self.lang)}]
            out = self._chat(msgs, temperature=0.3).choices[0].message.content or ""
            return parse_vote(out, juror.vote), extract_tag(out, "reason", "")

        return self._safe(run, fallback=(juror.vote, ""), stage="vote")

    def hint(self, state, case) -> str:
        def run():
            msgs = [{"role": "user", "content": prompts.hint_prompt(state, case, self.lang)}]
            return (self._chat(msgs, temperature=0.3).choices[0].message.content or "").strip()

        return self._safe(run, fallback="Consider whether the prosecution truly met "
                          "'beyond a reasonable doubt' — name one weak piece of evidence.",
                          stage="hint")

    def judge(self, statement, case) -> dict:
        def run() -> dict:
            out = self._chat(
                [{"role": "user", "content": prompts.judge_prompt(statement, case, self.lang)}],
                temperature=0.2,
            ).choices[0].message.content or ""
            return {"quality": clamp_score(extract_tag(out, "quality"), 50) / 100.0,
                    "fallacy": extract_tag(out, "fallacy", "none")}

        return self._safe(run, fallback={"quality": 0.5, "fallacy": "none"}, stage="judge")

    def tom_read(self, juror, state, case) -> list[dict]:
        def run() -> list[dict]:
            import re
            out = self._chat(
                [{"role": "user", "content": prompts.tom_prompt(juror, state, case, self.lang)}],
                temperature=0.2,
            ).choices[0].message.content or ""
            block = re.search(r"\[.*\]", out, re.S)
            return json.loads(block.group(0) if block else out)

        return self._safe(run, fallback=[], stage="tom")

    def generate_personas(self, case, n) -> list[dict]:
        def run():
            msgs = [{"role": "user", "content": prompts.rolegen_prompt(case, n, self.lang)}]
            out = self._chat(msgs, temperature=0.85).choices[0].message.content or ""
            import re
            block = re.search(r"\[.*\]", out, re.S)
            return json.loads(block.group(0) if block else out)[:n]

        return self._safe(run, fallback=[], stage="rolegen")

    def rubric(self, case, human_lines, state) -> dict:
        def run():
            msgs = [{"role": "user",
                     "content": prompts.rubric_prompt(case, human_lines, state, self.lang)}]
            out = self._chat(msgs, temperature=0.3).choices[0].message.content or ""
            dims = {k: clamp_score(extract_tag(out, k)) for k in
                    ["persuasiveness", "evidence_use", "consistency",
                     "engagement", "open_mindedness"]}
            recap = extract_tag(out, "recap", "Deliberation completed.")
            return {"dims": dims, "total": round(sum(dims.values()) / len(dims)), "recap": recap}

        fallback = {"dims": {k: 60 for k in ["persuasiveness", "evidence_use", "consistency",
                                             "engagement", "open_mindedness"]},
                    "total": 60, "recap": "Scoring unavailable; deliberation completed."}
        return self._safe(run, fallback=fallback, stage="rubric")
