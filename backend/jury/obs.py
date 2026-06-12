"""Lightweight observability — structured per-event tracing (set `JURY_TRACE=1`).

Every SSE event the engine emits can be logged as a compact structured record, so a
full deliberation is replayable from logs (who spoke, who moved whom, what tactic,
how much belief shifted). Off by default; zero overhead when disabled.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("jury.trace")

_FIELDS = ("vote", "tactic", "target", "delta", "opinion", "stance",
           "quality", "round", "status")


def trace_on() -> bool:
    return os.environ.get("JURY_TRACE", "").lower() in ("1", "true", "yes")


def build_record(ev: dict) -> dict:
    """Flatten an event into a compact, log-friendly record (pure)."""
    rec = {"type": ev.get("type")}
    who = ev.get("name") or ev.get("juror_id") or ev.get("by")
    if who:
        rec["who"] = who
    for k in _FIELDS:
        if ev.get(k) is not None:
            rec[k] = ev[k]
    return rec


def trace_event(ev: dict) -> None:
    if trace_on():
        logger.info("event %s", json.dumps(build_record(ev), ensure_ascii=False))
