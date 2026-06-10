"""Prompt templates: speak / respond / vote / hint / recap(rubric) / rolegen.

Bilingual (en / zh). Machine-readable tags (<vote>, <reason>, the rubric dims)
keep ENGLISH tokens in both languages so the regex parser is language-agnostic;
only the natural-language scaffold and the explicit reply-language directive
change. Full deliberation transcript + case context are injected each turn.
"""
from __future__ import annotations

from .cases import Case
from .state import GameState, JurorState

VOTE_VALUES = "GUILTY | NOT_GUILTY | UNDECIDED"
_VOTE_ZH = {"GUILTY": "有罪", "NOT_GUILTY": "无罪", "UNDECIDED": "未决"}


def render_transcript(state: GameState, last: int = 12) -> str:
    if not state.transcript:
        return "(deliberation has not started; no statements yet)"
    rows = state.transcript[-last:]
    return "\n".join(f"[R{e.round}] {e.name} ({e.vote}): {e.text}" for e in rows)


def _targeting(move, state, lang: str = "en") -> str:
    """Append a CDA targeting directive to a generation prompt (JURY_TOM). Empty
    string when there is no specific target."""
    if move is None or not getattr(move, "target_id", ""):
        return ""
    from . import strategy
    try:
        name = state.get_juror(move.target_id).persona.name
    except KeyError:
        return ""
    guide = strategy.tactic_text(move.tactic, lang)
    pt = move.target_point
    if lang == "zh":
        s = f"\n\n【策略】你尤其想说服 {name}。"
        if pt:
            s += f"他最站不住的点：{pt}。"
        return s + f"做法：{guide}。"
    s = f"\n\n[STRATEGY] You especially want to move {name}."
    if pt:
        s += f" Their weakest point: {pt}."
    return s + f" Approach: {guide}."


def persona_system(juror: JurorState, case: Case, lang: str = "en") -> str:
    p = juror.persona
    if lang == "zh":
        return (
            f"你是陪审员 {p.name}，{p.archetype}。说话风格：{p.voice}。"
            f"你带有这样的认知偏见/倾向，它会影响你权衡证据（不要把偏见本身说出来，"
            f"让它自然影响你）：{p.bias}。你当前的倾向是 {_VOTE_ZH.get(juror.vote, juror.vote)}。\n\n"
            f"案件：{case.title}。指控：{case.charge}\n{case.summary}\n\n"
            f"你在陪审团评议室里争论以达成裁决。请保持人设、有情绪、像真人，针对具体证据推理。"
            f"标准是『排除合理怀疑』。全程用中文。"
        )
    return (
        f"You are {p.name}, a juror: {p.archetype}. Speaking style: {p.voice}. "
        f"You carry this cognitive bias / leaning, and it COLORS how you weigh "
        f"evidence (do not state the bias out loud, just let it shape you): {p.bias}. "
        f"Your current leaning is {juror.vote}.\n\n"
        f"CASE: {case.title}. CHARGE: {case.charge}\n{case.summary}\n\n"
        f"You are in a jury room arguing toward a verdict. Stay in character, be "
        f"emotional and human, and reason about the specific evidence. The standard "
        f"is proof BEYOND A REASONABLE DOUBT."
    )


def speak_prompt(juror: JurorState, state: GameState, case: Case, lang: str = "en",
                 move=None) -> str:
    if lang == "zh":
        base = (
            f"目前的评议记录：\n{render_transcript(state)}\n\n"
            f"轮到你了（第 {state.round} 轮）。在断言任何有争议的事实之前，你可以调用 "
            f"`lookup_evidence` 工具从案卷中检索确切证据——只要你的论点依赖具体细节"
            f"（指纹、时间线、不在场证明、证人可靠性等）就用它。然后向其他陪审员做出"
            f"一段有说服力的发言（2-4 句），并以你检索到的证据为依据。\n\n"
            f"全程用中文发言。结尾必须有且仅有一个标签：<vote>{VOTE_VALUES}</vote>，"
            f"反映你当前的立场。"
        )
    else:
        base = (
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
    return base + _targeting(move, state, lang)


def respond_prompt(juror: JurorState, state: GameState, case: Case,
                   target_name: str, target_text: str, lang: str = "en",
                   move=None) -> str:
    if lang == "zh":
        base = (
            f"目前的评议记录：\n{render_transcript(state)}\n\n"
            f"{target_name} 刚刚说：「{target_text}」\n\n"
            f"你忍不住要直接回应 {target_name}（第 {state.round} 轮）。在挑战或支持某个"
            f"有争议的事实前，你可以调用 `lookup_evidence` 把回应建立在案卷之上。然后给出"
            f"一段有针对性的反应（2-3 句）——反驳、补强或使其复杂化。\n\n"
            f"全程用中文。结尾必须有且仅有一个标签：<vote>{VOTE_VALUES}</vote>。"
        )
    else:
        base = (
            f"Deliberation so far:\n{render_transcript(state)}\n\n"
            f"{target_name} just argued: \"{target_text}\"\n\n"
            f"You feel compelled to RESPOND directly to {target_name} (round {state.round}). "
            f"Before challenging or backing a disputed fact, you may call `lookup_evidence` "
            f"to ground your reply in the case file. Then give ONE pointed reaction (2-3 "
            f"sentences) — rebut, reinforce, or complicate their point.\n\n"
            f"End with exactly one tag: <vote>{VOTE_VALUES}</vote>."
        )
    return base + _targeting(move, state, lang)


def think_prompt(juror: JurorState, state: GameState, case: Case, lang: str = "en") -> str:
    if lang == "zh":
        return (
            f"目前的评议记录：\n{render_transcript(state, last=8)}\n\n"
            f"私下想清楚你的下一步（1-2 句）：你要提出哪个点、需要核查哪条证据？"
            f"只回复你的内心想法（中文），不要任何前缀。"
        )
    return (
        f"Deliberation so far:\n{render_transcript(state, last=8)}\n\n"
        f"Privately think through your next move in 1-2 sentences: what point will you "
        f"raise and which evidence do you need to check? Reply with ONLY the inner "
        f"thought, no preamble."
    )


def vote_prompt(juror: JurorState, state: GameState, case: Case, lang: str = "en") -> str:
    if lang == "zh":
        return (
            f"目前的评议记录：\n{render_transcript(state)}\n\n"
            f"第 {state.round} 轮即将结束。请根据所有发言重新投票。如果论点和证据说服了你，"
            f"可以改变立场。严格按以下格式回复：\n"
            f"<vote>{VOTE_VALUES}</vote>\n<reason>一句话中文理由</reason>"
        )
    return (
        f"Deliberation so far:\n{render_transcript(state)}\n\n"
        f"Round {state.round} is closing. Re-cast your vote given everything said. "
        f"You may shift if the arguments and evidence moved you. "
        f"Reply in exactly this format:\n"
        f"<vote>{VOTE_VALUES}</vote>\n<reason>one short sentence</reason>"
    )


def hint_prompt(state: GameState, case: Case, lang: str = "en") -> str:
    if lang == "zh":
        return (
            f"你是一位犀利的陪审团评议教练，正在帮助一位人类陪审员。"
            f"案件：{case.title} —— {case.charge}\n\n"
            f"目前的评议记录：\n{render_transcript(state)}\n\n"
            f"用 2 句话（中文）建议这位人类下一步最该提出的、被讨论得最不充分的一个有力论点，"
            f"并点名要引用的具体证据。要具体。"
        )
    return (
        f"You are a sharp jury-deliberation coach helping a human juror. "
        f"CASE: {case.title} — {case.charge}\n\n"
        f"Deliberation so far:\n{render_transcript(state)}\n\n"
        f"Suggest, in 2 sentences, the single strongest under-discussed point the human "
        f"could raise next, naming the specific evidence to cite. Be concrete."
    )


def judge_prompt(statement: str, case: Case, lang: str = "en") -> str:
    """CDA influence evaluator: score one statement's argument quality + flag any
    obvious logical fallacy. Structured tags (English) so the parser is language-
    agnostic; consumed by the numpy belief-update engine, never shown to the user."""
    if lang == "zh":
        return (
            f"你是论证质量裁判。案件：{case.title}。\n\n"
            f"评估这段陪审团发言的论证质量：\n「{statement}」\n\n"
            f"按以下格式回复（标签用英文）：\n"
            f"<quality>0-100：是否以具体证据为依据、针对争议事实、逻辑扎实</quality>\n"
            f"<fallacy>若存在明显逻辑谬误写其名称，否则写 none</fallacy>"
        )
    return (
        f"You are an argument-quality judge. Case: {case.title}.\n\n"
        f"Rate this jury-room statement's argument quality:\n\"{statement}\"\n\n"
        f"Reply in exactly this format:\n"
        f"<quality>0-100: is it grounded in specific evidence, on-point, logically sound</quality>\n"
        f"<fallacy>name an obvious logical fallacy if present, else none</fallacy>"
    )


def tom_prompt(speaker: JurorState, state: GameState, case: Case, lang: str = "en") -> str:
    """CDA Theory-of-Mind: ask the speaker to infer each opponent's mind from the
    transcript. Output is structured JSON (consumed by jury/tom.py), never shown."""
    others = [j for j in state.ai_jurors if j.id != speaker.id]
    roster = ", ".join(f"{j.persona.id}={j.persona.name}" for j in others)
    if lang == "zh":
        return (
            f"你是 {speaker.persona.name}。读评议记录，推测每个其他陪审员现在的心理。\n\n"
            f"评议记录：\n{render_transcript(state)}\n\n"
            f"其他陪审员：{roster}\n\n"
            f"对每个人输出一个 JSON 对象放进数组，字段：\n"
            f'{{"opponent_id": 编号, "est_opinion": -1到1(负=偏无罪,正=偏有罪), '
            f'"weakest_point": 他论证里最站不住的一点, "est_openness": 0到1(越大越易被说服)}}\n'
            f"只返回 JSON 数组。"
        )
    return (
        f"You are {speaker.persona.name}. Read the deliberation and infer each other "
        f"juror's current state of mind.\n\n"
        f"Deliberation:\n{render_transcript(state)}\n\n"
        f"Other jurors: {roster}\n\n"
        f"For each, output one JSON object in an array with fields:\n"
        f'{{"opponent_id": id, "est_opinion": -1..1 (neg=leans not-guilty, pos=guilty), '
        f'"weakest_point": their least-defensible point, "est_openness": 0..1 (higher=easier to persuade)}}\n'
        f"Return ONLY the JSON array."
    )


def rolegen_prompt(case: Case, n: int, lang: str = "en") -> str:
    if lang == "zh":
        return (
            f"为这起案件的评议设计 {n} 位鲜明、彼此不同的陪审员。\n"
            f"案件：{case.title} —— {case.charge}\n{case.summary}\n\n"
            f"每位都要有不同的原型、清晰的认知偏见、初始倾向和说话风格。"
            f"只返回一个 JSON 数组，每项格式如下（字段名用英文，值用中文，"
            f"initial_leaning 用 GUILTY/NOT_GUILTY/UNDECIDED）：\n"
            f'{{"name": str, "archetype": str, "bias": str, '
            f'"initial_leaning": "GUILTY|NOT_GUILTY|UNDECIDED", "voice": str}}'
        )
    return (
        f"Design {n} vivid, DISTINCT jurors for a deliberation on this case.\n"
        f"CASE: {case.title} — {case.charge}\n{case.summary}\n\n"
        f"Give each a different archetype, a clear cognitive bias, an initial leaning, "
        f"and a speaking voice. Return ONLY a JSON array, each item:\n"
        f'{{"name": str, "archetype": str, "bias": str, '
        f'"initial_leaning": "GUILTY|NOT_GUILTY|UNDECIDED", "voice": str}}'
    )


def rubric_prompt(case: Case, human_lines: str, state: GameState, lang: str = "en") -> str:
    if lang == "zh":
        return (
            f"你是一位 LLM-as-a-Judge，正在评估一位人类陪审员在『{case.title}』评议中的表现。\n\n"
            f"这位人类的发言：\n{human_lines or '(这位人类几乎没怎么发言)'}\n\n"
            f"完整评议上下文：\n{render_transcript(state, last=20)}\n\n"
            f"请对这位人类在每个维度上 0-100 打分，然后写 2-3 句复盘。"
            f"严格按以下格式回复（标签用英文，recap 内容用中文）：\n"
            f"<persuasiveness>0-100</persuasiveness>\n"
            f"<evidence_use>0-100</evidence_use>\n"
            f"<consistency>0-100</consistency>\n"
            f"<engagement>0-100</engagement>\n"
            f"<open_mindedness>0-100</open_mindedness>\n"
            f"<recap>一段简短的中文复盘</recap>"
        )
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
