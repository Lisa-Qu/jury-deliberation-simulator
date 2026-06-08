"""Fallback / parsing robustness (no network)."""
from __future__ import annotations

from jury.llm import (JuryLLM, clamp_score, clean_statement, extract_tag,
                      parse_vote)


def _bare_llm() -> JuryLLM:
    """A JuryLLM without running __init__ (no chat client / API key)."""
    obj = JuryLLM.__new__(JuryLLM)
    obj.errors = []
    return obj


def test_safe_returns_fallback_and_records_error():
    llm = _bare_llm()

    def boom():
        raise RuntimeError("api down")

    result = llm._safe(boom, fallback="SAFE", stage="speak")
    assert result == "SAFE"
    assert llm.errors and llm.errors[0]["stage"] == "speak"
    assert llm.errors[0]["recovered"] is True
    assert llm.errors[0]["type"] == "error"


def test_safe_retries_then_succeeds():
    llm = _bare_llm()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ValueError("transient")
        return "ok"

    assert llm._safe(flaky, fallback="X", stage="vote") == "ok"
    assert llm.errors == []


def test_drain_errors_clears():
    llm = _bare_llm()
    llm.errors.append({"type": "error"})
    assert llm.drain_errors()
    assert llm.errors == []


def test_parse_vote_variants():
    assert parse_vote("<vote>GUILTY</vote>") == "GUILTY"
    assert parse_vote("<vote>not guilty</vote>") == "NOT_GUILTY"
    assert parse_vote("no tag here", fallback="UNDECIDED") == "UNDECIDED"


def test_clean_statement_strips_tags():
    raw = "<thinking>secret</thinking>The print is weak.<vote>NOT_GUILTY</vote>"
    out = clean_statement(raw)
    assert "secret" not in out and "vote" not in out
    assert "print is weak" in out


def test_clamp_score_bounds():
    assert clamp_score("150") == 100
    assert clamp_score("-5") == 0
    assert clamp_score("abc", default=60) == 60
    assert clamp_score("82") == 82


def test_extract_tag_missing_returns_default():
    assert extract_tag("nothing", "recap", "fallback") == "fallback"
