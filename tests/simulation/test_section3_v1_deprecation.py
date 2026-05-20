"""Section 3 v1 chat 의 deprecation 처리 검증 (Phase 7, 2026-05-18).

`/api/section3/chat` (bridge_agent v1) 호출 시 응답 header 에 deprecation 표시 surface.
RFC 7234 Warning 299 + 자체 `X-Deprecated` / `X-Replacement` / `X-Deprecation-Date`.
"""
from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.section3.api import router as section3_router
from backend.section3.clients.modeling_client import ModelingClient


class _StubModelingClient:
    """ModelingClient stand-in — chat 호출이 즉시 끝나도록 query 결과만 stub."""

    async def aclose(self) -> None:
        pass


@pytest.fixture
def client(monkeypatch):
    # OPENAI_API_KEY 미설정 환경에서도 OK 하도록 LLM client + intent classifier 양쪽 stub.
    # 본 테스트는 SSE body 가 아닌 response header 만 검증.
    from backend.section3.agents import base as base_mod
    from backend.section3.llm import intent_classifier as ic_mod

    class _StubLLM:
        model = "stub"
        def chat(self, *a, **kw):
            return ""
        def chat_json(self, *a, **kw):
            return {}

    monkeypatch.setattr(base_mod, "get_llm_client", lambda: _StubLLM())

    class _IC:
        modeling_intent = "explain"
        parameters: dict = {}
        confidence = 0.5
        reasoning = "stub"
        suggested_followups: list[str] = []

    monkeypatch.setattr(ic_mod, "classify_intent", lambda *a, **kw: _IC())

    app = FastAPI()
    app.include_router(section3_router.router)
    app.dependency_overrides[section3_router.get_modeling_client] = (
        lambda: _StubModelingClient()  # type: ignore[return-value]
    )
    with TestClient(app) as c:
        yield c


def test_chat_v1_emits_deprecation_headers(client):
    """v1 /chat 응답에 deprecation 메타 헤더가 포함되어야 한다."""
    r = client.post("/api/section3/chat", json={"message": "x", "history": []})

    # SSE — content-type 검증
    assert r.headers.get("content-type", "").startswith("text/event-stream")

    # deprecation 메타
    assert r.headers.get("x-deprecated") == "true"
    assert r.headers.get("x-deprecation-date") == "2026-05-18"
    assert "/api/section3/multiturn/" in r.headers.get("x-replacement", "")

    warning = r.headers.get("warning", "")
    assert warning.startswith("299 ")
    assert "deprecated" in warning.lower()
    assert "multiturn" in warning.lower()


def test_chat_v1_still_streams_body(client):
    """deprecation header 추가가 SSE streaming 자체를 깨면 안 된다."""
    r = client.post("/api/section3/chat", json={"message": "x", "history": []})
    # body 첫 chunk 가 SSE event prefix 로 시작
    text = r.text
    assert "event:" in text or "data:" in text


__all__ = [
    "test_chat_v1_emits_deprecation_headers",
    "test_chat_v1_still_streams_body",
]
