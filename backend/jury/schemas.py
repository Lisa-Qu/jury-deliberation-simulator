"""Pydantic schemas for LLM structured outputs (judge / ToM / arguments).

Centralizes validation + coercion of the JSON the model returns, replacing
ad-hoc float()/clamp() scattered across modules. Also usable as the target of
LangChain `.with_structured_output(Model)` for providers that support it.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _clamp(v, lo, hi):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return (lo + hi) / 2


class JudgeResult(BaseModel):
    """Argument-quality verdict for one statement."""
    quality: float = 0.5          # 0..1
    fallacy: str = "none"

    @field_validator("quality", mode="before")
    @classmethod
    def _norm_quality(cls, v):
        v = _clamp(v, 0.0, 100.0)
        return round(v / 100.0, 3) if v > 1.0 else round(_clamp(v, 0.0, 1.0), 3)


class ToMRead(BaseModel):
    """One opponent in a Theory-of-Mind read."""
    opponent_id: str
    est_opinion: float = 0.0       # -1..1
    weakest_point: str = ""
    est_openness: float = 0.6      # 0..1

    @field_validator("est_opinion", mode="before")
    @classmethod
    def _clamp_op(cls, v):
        return round(_clamp(v, -1.0, 1.0), 3)

    @field_validator("est_openness", mode="before")
    @classmethod
    def _clamp_eps(cls, v):
        return round(_clamp(v, 0.0, 1.0), 3)


class ArgumentOut(BaseModel):
    """One Toulmin argument extracted for a juror."""
    claim: str = ""
    grounds: str = ""
    warrant: str = ""
    strength: float = 0.5          # 0..1

    @field_validator("strength", mode="before")
    @classmethod
    def _clamp_strength(cls, v):
        return round(_clamp(v, 0.0, 1.0), 3)


def parse_list(model: type[BaseModel], rows) -> list[BaseModel]:
    """Validate a list of dicts into models, silently dropping malformed rows."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        try:
            out.append(model(**r))
        except Exception:  # noqa: BLE001 — skip malformed, never crash
            continue
    return out
