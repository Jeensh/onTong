"""ClaudeTermResolver tests — Anthropic API 응답 파싱 + 환각 방어 흐름.

실제 API 호출은 안 함. `_client` 를 stub 으로 주입.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from backend.modeling.mapping.mapping_models import BusinessTerm, BusinessTermSource
from backend.modeling.query.llm_term_resolver import ClaudeTermResolver
from backend.modeling.query.term_resolver import LLMProposal


def _term(fqn: str, label: str, aliases: list[str] | None = None) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=fqn, canonical_label=label,
        aliases=aliases or [], domain="t",
        source=BusinessTermSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeResp:
    def __init__(self, text: str) -> None:
        self.content = [_FakeBlock(text)]


class _FakeClient:
    """Anthropic SDK 흉내 — `messages.create` 만."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

        class _Messages:
            def __init__(self, parent: "_FakeClient") -> None:
                self._parent = parent

            def create(self, **kwargs: Any) -> _FakeResp:
                self._parent.calls.append(kwargs)
                if not self._parent._responses:
                    raise RuntimeError("no more fake responses")
                return _FakeResp(self._parent._responses.pop(0))

        self.messages = _Messages(self)


def _resolver_with(client: _FakeClient | None) -> ClaudeTermResolver:
    r = ClaudeTermResolver()
    r._client = client  # type: ignore[assignment]
    return r


# ---------------------------------------------------------------------------
# Graceful no-op when client missing
# ---------------------------------------------------------------------------
def test_no_client_returns_none() -> None:
    r = _resolver_with(None)
    out = r.propose("anything", [_term("term.x", "X")])
    assert out is None


def test_no_terms_returns_none() -> None:
    r = _resolver_with(_FakeClient(['{"term_fqn":"term.x","confidence":0.9}']))
    assert r.propose("anything", []) is None


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------
class TestJsonParsing:
    def test_clean_json_response(self) -> None:
        client = _FakeClient([
            '{"term_fqn":"term.품종코드","confidence":0.85,"reasoning":"필드명이 product_type 변형"}',
        ])
        r = _resolver_with(client)
        out = r.propose("product_type_cd", [_term("term.품종코드", "품종코드")])
        assert isinstance(out, LLMProposal)
        assert out.term_fqn == "term.품종코드"
        assert out.confidence == 0.85
        assert "product_type" in out.reasoning

    def test_fenced_json_response(self) -> None:
        client = _FakeClient([
            '여기 매칭 결과입니다:\n```json\n{"term_fqn":"term.x","confidence":0.7,"reasoning":"r"}\n```\n끝',
        ])
        r = _resolver_with(client)
        out = r.propose("q", [_term("term.x", "X")])
        assert out is not None and out.term_fqn == "term.x"

    def test_null_term_fqn_returns_none(self) -> None:
        client = _FakeClient(['{"term_fqn":null,"confidence":0.0,"reasoning":"매칭 없음"}'])
        r = _resolver_with(client)
        assert r.propose("q", [_term("term.x", "X")]) is None

    def test_invalid_json_returns_none(self) -> None:
        client = _FakeClient(["this is not json at all"])
        r = _resolver_with(client)
        assert r.propose("q", [_term("term.x", "X")]) is None

    def test_invalid_confidence_returns_none(self) -> None:
        client = _FakeClient(['{"term_fqn":"term.x","confidence":"high"}'])
        r = _resolver_with(client)
        assert r.propose("q", [_term("term.x", "X")]) is None


# ---------------------------------------------------------------------------
# Prompt content sanity
# ---------------------------------------------------------------------------
def test_prompt_includes_terms_and_query() -> None:
    client = _FakeClient(['{"term_fqn":null,"confidence":0.0}'])
    r = _resolver_with(client)
    r.propose("필드 a1 클래스 HrCalc 안", [
        _term("term.품종코드", "품종코드", ["product_type", "품종"]),
        _term("term.열연공장코드", "열연공장코드", ["hr_plant"]),
    ])
    assert client.calls
    msg = client.calls[0]["messages"][0]["content"]
    assert "term.품종코드" in msg
    assert "term.열연공장코드" in msg
    assert "품종" in msg
    assert "필드 a1" in msg


# ---------------------------------------------------------------------------
# API error → graceful None
# ---------------------------------------------------------------------------
def test_api_exception_returns_none() -> None:
    class _ExplodingClient:
        class _Messages:
            def create(self, **kwargs: Any) -> Any:
                raise RuntimeError("network down")
        def __init__(self) -> None:
            self.messages = _ExplodingClient._Messages()

    r = _resolver_with(_ExplodingClient())  # type: ignore[arg-type]
    assert r.propose("q", [_term("term.x", "X")]) is None
