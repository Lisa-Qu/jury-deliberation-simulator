"""HTTP surface: health, cases, game creation, action routing (no real LLM).

Plugin-free: requests run via asyncio.run() over httpx ASGITransport.
"""
from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

import server
from jury import config


def _request(method, path, **kw):
    async def inner():
        transport = ASGITransport(app=server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, **kw)

    return asyncio.run(inner())


def test_health():
    r = _request("GET", "/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_cases_listed():
    r = _request("GET", "/api/cases")
    data = r.json()
    assert "people-v-reyes" in [x["id"] for x in data]
    assert any(len(x["evidence"]) > 5 for x in data)


def test_create_requires_key(monkeypatch):
    monkeypatch.setattr(config, "has_key", lambda: False)
    r = _request("POST", "/api/game", json={"mode": "scripted"})
    assert r.status_code == 500


def test_create_returns_game_id(monkeypatch):
    monkeypatch.setattr(config, "has_key", lambda: True)
    r = _request("POST", "/api/game", json={"mode": "scripted"})
    body = r.json()
    assert r.status_code == 200
    assert "game_id" in body and body["case"]["id"] == "people-v-reyes"
    sess = server.GAMES.get(body["game_id"])
    if sess and sess.task:
        sess.task.cancel()


def test_action_unknown_game_404():
    r = _request("POST", "/api/game/does-not-exist/action", json={"action": "VOTE"})
    assert r.status_code == 404


def test_unknown_case_404(monkeypatch):
    monkeypatch.setattr(config, "has_key", lambda: True)
    r = _request("POST", "/api/game", json={"mode": "scripted", "case_id": "nope"})
    assert r.status_code == 404
