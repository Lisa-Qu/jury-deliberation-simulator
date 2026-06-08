"""Prompt templates: speak / respond / vote / hint / recap(rubric) / rolegen.

Structured output convention: models wrap inner reasoning in <thinking>…</thinking>
and emit machine-readable fields in tags (e.g. <vote>GUILTY</vote>), parsed by
regex in llm.py. Full deliberation transcript + case context are injected each
turn (context engineering).
"""
from __future__ import annotations

from .cases import Case
from .state import GameState, JurorState

VOTE_VALUES = "GUILTY | NOT_GUILTY | UNDECIDED"


def render_transcript(state: GameState, last: int = 12) -> str:
    if not state.transcript:
        return "(deliberation has not started; no statements yet)"
    rows = state.transcript[-last:]
    return "\n".join(
        f"[R{e.round}] {e.name} ({e.vote}): {e.text}" for e in rows
    )


def persona_system(juror: JurorState, case: Case) -> str:
    p = juror.persona
    return (
        f"You are {p.name}, a juror: {p.archetype}. "
        f"Speaking style: {p.voice}. "
        f"You carry this cognitive bias / leaning, and it COLORS how you weigh "
        f"evidence (do not state the bias out loud, just let it shape you): {p.bias}. "
        f"Your current leaning is {juror.vote}.\n\n"
        f"CASE: {case.title}. CHARGE: {case.charge}\n{case.summary}\n\n"
        f"You are in a jury room arguing toward a verdict. Stay in character, be "
        f"emotional and human, and reason about the specific evidence. The standard "
        f"is proof BEYOND A REASONABLE DOUBT."
    )


def speak_prompt(juror: JurorState, state: GameState, case: Case) -> str:
    return (
        f"Deliberation so far:\n{render_transcript(state)}\n\n"
        f"It is your turn (round {state.round}). Before asserting any disputed FACT, "
        f"you may call the `lookup_evidence` tool to pull the exact evidence from the "
        f"case file — use it whenever your point depends on a specific detail "
        f"(fingerprint, timeline, alibi, witness reliability, etc.). "
        f"Then make ONE persuasive statement (2-4 sentences) to the other jurors, "
        f"grounded in the evidence you retrieved.\n\n"
        f"End your message with exactly one tag: <vote>{VOTE_VALUES}</vote> "
        f"reflecting where you now stand."
    )


def respond_prompt(juror: JurorState, state: GameState, case: Case,
                   target_name: str, target_text: str) -> str:
    return (
        f"Deliberation so far:\n{render_transcript(state)}\n\n"
        f"{target_name} just argued: \"{target_text}\"\n\n"
        f"You feel compelled to RESPOND directly to {target_name} (round {state.round}). "
        f"Before challenging or backing a disputed fact, you may call `lookup_evidence` "
        f"to ground your reply in the case file. Then give ONE pointed reaction (2-3 "
        f"sentences) — rebut, reinforce, or complicate their point.\n\n"
        f"End with exactly one tag: <vote>{VOTE_VALUES}</vote>."
    )


def think_prompt(juror: JurorState, state: GameState, case: Case) -> str:
    return (
        f"Deliberation so far:\n{render_transcript(state, last=8)}\n\n"
        f"Privately think through your next move in 1-2 sentences: what point will you "
        f"raise and which evidence do you need to check? Reply with ONLY the inner "
        f"thought, no preamble."
    )


def vote_prompt(juror: JurorState, state: GameState, case: Case) -> str:
    return (
        f"Deliberation so far:\n{render_transcript(state)}\n\n"
        f"Round {state.round} is closing. Re-cast your vote given everything said. "
        f"You may shift if the arguments and evidence moved you. "
        f"Reply in exactly this format:\n"
        f"<vote>{VOTE_VALUES}</vote>\n<reason>one short sentence</reason>"
    )


def hint_prompt(state: GameState, case: Case) -> str:
    return (
        f"You are a sharp jury-deliberation coach helping a human juror. "
        f"CASE: {case.title} — {case.charge}\n\n"
        f"Deliberation so far:\n{render_transcript(state)}\n\n"
        f"Suggest, in 2 sentences, the single strongest under-discussed point the human "
        f"could raise next, naming the specific evidence to cite. Be concrete."
    )


def rolegen_prompt(case: Case, n: int) -> str:
    return (
        f"Design {n} vivid, DISTINCT jurors for a deliberation on this case.\n"
        f"CASE: {case.title} — {case.charge}\n{case.summary}\n\n"
        f"Give each a different archetype, a clear cognitive bias, an initial leaning, "
        f"and a speaking voice. Return ONLY a JSON array, each item:\n"
        f'{{"name": str, "archetype": str, "bias": str, '
        f'"initial_leaning": "GUILTY|NOT_GUILTY|UNDECIDED", "voice": str}}'
    )


def rubric_prompt(case: Case, human_lines: str, state: GameState) -> str:
    return (
        f"You are an LLM-as-a-Judge evaluating ONE human juror's participation in a "
        f"deliberation on {case.title}.\n\n"
        f"The human's contributions:\n{human_lines or '(the human said very little)'}\n\n"
        f"Full deliberation context:\n{render_transcript(state, last=20)}\n\n"
        f"Score the HUMAN 0-100 on each dimension, then write a 2-3 sentence recap.\n"
        f"Reply in exactly this format:\n"
        f"<persuasiveness>0-100</persuasiveness>\n"
        f"<evidence_use>0-100</evidence_use>\n"
        f"<consistency>0-100</consistency>\n"
        f"<engagement>0-100</engagement>\n"
        f"<open_mindedness>0-100</open_mindedness>\n"
        f"<recap>short paragraph</recap>"
    )
