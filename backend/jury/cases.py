"""Case definitions + the evidence corpus that the RAG tool retrieves over.

The evidence is intentionally CONTESTED (mix of incriminating and exculpatory)
so jurors genuinely need to look facts up before asserting them — guaranteeing
the ReAct / tool-call trace shows up in a demo run.
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


_BURGLARY = Case(
    id="people-v-reyes",
    title="People v. Daniel Reyes",
    charge="Second-degree burglary of the Marlin Street jewelry store (March 3, night).",
    summary=(
        "Daniel Reyes, 27, is charged with breaking into Marlin & Co. jewelers "
        "around 11:40 PM on March 3 and stealing roughly $40,000 in watches. "
        "There is no confession. The case rests on circumstantial evidence: a "
        "partial fingerprint, grainy CCTV, a disputed alibi, and a jailhouse "
        "informant. You must decide GUILTY or NOT_GUILTY beyond a reasonable doubt."
    ),
    evidence=(
        # --- incriminating ---
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
        # --- exculpatory ---
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
        # --- procedural / reliability ---
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
    ),
)

CASES: dict[str, Case] = {_BURGLARY.id: _BURGLARY}
DEFAULT_CASE_ID = _BURGLARY.id


def get_case(case_id: str | None = None) -> Case:
    return CASES[case_id or DEFAULT_CASE_ID]
