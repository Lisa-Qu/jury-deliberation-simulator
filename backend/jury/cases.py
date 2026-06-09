"""Case definitions + the evidence corpus that the RAG tool retrieves over.

Bilingual (en / zh): `get_case(case_id, lang)` returns a Case localized to the
chosen language so the evidence panel, prompts, and RAG all run in that language.
The evidence is intentionally CONTESTED (mix of incriminating and exculpatory) so
jurors genuinely need to look facts up — guaranteeing the ReAct trace shows up.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    charge: str
    summary: str
    evidence: tuple[str, ...]

    def public(self) -> dict:
        return {
            "id": self.id, "title": self.title, "charge": self.charge,
            "summary": self.summary, "evidence": list(self.evidence),
        }


_EVIDENCE_EN = (
    "E1 Fingerprint: A partial print on the broken display-case glass was found "
    "consistent with Reyes's right thumb. The examiner testified it had only 9 "
    "matching minutiae points — below the lab's own 12-point standard for a "
    "confident individualization.",
    "E2 CCTV: Store camera caught a figure in a dark hoodie at 11:41 PM. Height "
    "estimate 5'9\"–6'1\". Reyes is 5'10\". The face is never visible.",
    "E3 Informant: Marcus Hale, an inmate sharing a cell with Reyes, says Reyes "
    "bragged about 'the Marlin job.' Hale received a reduced sentence in exchange "
    "for his testimony.",
    "E4 Prior: Reyes has one prior conviction for shoplifting at age 19. No prior "
    "burglary or violent offenses.",
    "E5 Pawn record: A watch matching one stolen model was pawned two towns over on "
    "March 6 by a man who paid cash; the pawnshop clerk could not identify Reyes "
    "from a photo lineup.",
    "E6 Glove fibers: Black nitrile glove fibers were recovered at the scene, "
    "indicating the burglar likely wore gloves — which would not leave prints.",
    "E7 Alibi: Reyes's girlfriend, Tania Cruz, testified he was at her apartment "
    "watching a movie until past midnight on March 3.",
    "E8 Alibi corroboration: A food-delivery receipt shows an order delivered to "
    "Tania Cruz's address at 11:52 PM on March 3, signed for at the door.",
    "E9 Phone location: Reyes's cell phone connected to a tower covering Tania "
    "Cruz's neighborhood — about 4 miles from the store — at 11:38 PM and 11:55 PM.",
    "E10 Alibi weakness: The delivery driver could not recall who signed; the "
    "signature on the receipt is illegible.",
    "E11 No stolen goods: No watches, tools, or cash from the burglary were ever "
    "found in Reyes's home, car, or accounts.",
    "E12 Tool marks: The door was forced with a crowbar. No crowbar was linked to "
    "Reyes, and no tool marks matched any tool he owned.",
    "E13 Informant credibility: Hale has testified as an informant in two prior "
    "unrelated cases, each time for a sentencing benefit.",
    "E14 CCTV timing: The store clock on the CCTV was later found to run 6 minutes "
    "fast, so the 11:41 PM timestamp may correspond to ~11:35 PM real time.",
    "E15 Fingerprint context: Reyes had visited Marlin & Co. as a customer two weeks "
    "earlier to price an engagement ring; staff confirmed the visit.",
    "E16 Lineup: The pawnshop photo lineup was shown to the clerk 11 days after the "
    "transaction; the clerk described the pawner as 'taller, with a beard.' Reyes "
    "is clean-shaven.",
    "E17 Weather: It rained heavily the night of March 3; the CCTV figure left no "
    "visible muddy footprints inside, though the floor was tile.",
    "E18 Reasonable-doubt instruction: The judge instructs that the prosecution must "
    "prove every element beyond a reasonable doubt; the defendant need not prove "
    "innocence.",
)

_EVIDENCE_ZH = (
    "E1 指纹：展示柜破碎玻璃上的一枚部分指纹被认定与 Reyes 右手拇指一致。鉴定人作证称"
    "仅有 9 个匹配特征点——低于实验室自身用于确信认定的 12 点标准。",
    "E2 监控：店内摄像头在 23:41 拍到一个穿深色连帽衫的身影。身高估计 5'9\"–6'1\"。"
    "Reyes 身高 5'10\"。脸部始终不可见。",
    "E3 线人：与 Reyes 同囚室的犯人 Marcus Hale 称 Reyes 吹嘘过『Marlin 那票』。"
    "Hale 以作证换取了减刑。",
    "E4 前科：Reyes 在 19 岁时有一次入店行窃定罪。无入室盗窃或暴力前科。",
    "E5 当铺记录：3 月 6 日，一名付现金的男子在两镇之外典当了一块与被盗型号相符的手表；"
    "当铺店员无法从照片辨认队列中认出 Reyes。",
    "E6 手套纤维：现场提取到黑色丁腈手套纤维，表明盗贼很可能戴了手套——这不会留下指纹。",
    "E7 不在场证明：Reyes 的女友 Tania Cruz 作证称 3 月 3 日他在她的公寓看电影直到午夜过后。",
    "E8 不在场佐证：一张外卖收据显示 3 月 3 日 23:52 有订单送到 Tania Cruz 的住址，"
    "并在门口签收。",
    "E9 手机定位：Reyes 的手机在 23:38 和 23:55 连接到覆盖 Tania Cruz 社区的基站"
    "——距案发店铺约 4 英里。",
    "E10 不在场弱点：外卖司机记不清是谁签收的；收据上的签名难以辨认。",
    "E11 无赃物：Reyes 的住所、车辆或账户中从未发现任何被盗手表、工具或现金。",
    "E12 工具痕迹：门是被撬棍撬开的。没有撬棍与 Reyes 关联，也没有工具痕迹与他拥有的"
    "任何工具相符。",
    "E13 线人可信度：Hale 曾在另外两起无关案件中作为线人作证，每次都换取了量刑上的好处。",
    "E14 监控时间：监控上的店内时钟后来被发现快了 6 分钟，因此 23:41 的时间戳可能对应"
    "真实时间约 23:35。",
    "E15 指纹背景：Reyes 两周前曾作为顾客到访 Marlin & Co. 为订婚戒指询价；店员确认了这次到访。",
    "E16 辨认队列：当铺的照片辨认队列在交易 11 天后才出示给店员；店员形容典当者"
    "『个子更高、有胡子』。而 Reyes 是干净刮脸的。",
    "E17 天气：3 月 3 日夜里下了大雨；监控中的身影在店内没有留下可见的泥脚印，不过地面是瓷砖。",
    "E18 合理怀疑指示：法官指示控方必须排除合理怀疑地证明每一项要件；被告无需自证清白。",
)

_META = {
    "en": {
        "title": "People v. Daniel Reyes",
        "charge": "Second-degree burglary of the Marlin Street jewelry store (March 3, night).",
        "summary": (
            "Daniel Reyes, 27, is charged with breaking into Marlin & Co. jewelers "
            "around 11:40 PM on March 3 and stealing roughly $40,000 in watches. "
            "There is no confession. The case rests on circumstantial evidence: a "
            "partial fingerprint, grainy CCTV, a disputed alibi, and a jailhouse "
            "informant. You must decide GUILTY or NOT_GUILTY beyond a reasonable doubt."
        ),
        "evidence": _EVIDENCE_EN,
    },
    "zh": {
        "title": "公诉 Daniel Reyes 案",
        "charge": "二级入室盗窃 Marlin 街珠宝店（3 月 3 日夜间）。",
        "summary": (
            "27 岁的 Daniel Reyes 被控于 3 月 3 日约 23:40 闯入 Marlin & Co. 珠宝店，"
            "盗走约 4 万美元的手表。本案无认罪，依赖间接证据：一枚部分指纹、模糊的监控、"
            "有争议的不在场证明，以及一名狱中线人。你必须在『排除合理怀疑』的标准下，"
            "裁定 GUILTY（有罪）或 NOT_GUILTY（无罪）。"
        ),
        "evidence": _EVIDENCE_ZH,
    },
}

CASE_ID = "people-v-reyes"
DEFAULT_CASE_ID = CASE_ID
# Registry advertises the English title; localized copy is built on demand.
CASES = {CASE_ID: _META}


def get_case(case_id: str | None = None, lang: str = "en") -> Case:
    cid = case_id or DEFAULT_CASE_ID
    if cid not in CASES:
        raise KeyError(cid)
    m = _META[lang if lang in _META else "en"]
    return Case(id=cid, title=m["title"], charge=m["charge"],
                summary=m["summary"], evidence=m["evidence"])
