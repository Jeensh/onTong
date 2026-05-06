"""OD-11-D3-3 : Gap scan / queue REST + SSE API tests.

Endpoints :
    POST   /api/modeling/gaps/scan          → JSON `UnifiedScanResponse`
    POST   /api/modeling/gaps/scan/stream   → SSE (scanning / stage1 / stage2 / complete)
    GET    /api/modeling/gaps               → list + filters
    POST   /api/modeling/gaps/{id}/confirm  → confirm one gap (human-in-loop)

Contract :
    - POST body `{repo_id, gap_mode?, business_terms?, rules, described_in,
      fragments?}` — fragments None 이면 ManualRegistry 에서 auto-pull.
    - BusinessRule / DescribedInBinding 은 store 가 없어서 body 에 명시 필수.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import gaps_api
from backend.modeling.gap_detection.embedding_drifter import CosineDrifter
from backend.modeling.gap_detection.gap_engine import create_gap_engine
from backend.modeling.gap_detection.gap_scanner import GapScanner
from backend.modeling.gap_detection.gap_store import InMemoryGapStore
from backend.modeling.gap_detection.missing_in_detector import MissingInDetector
from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manuals.manual_models import (
    GapDirection,
    GapMode,
    GapSeverity,
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
)


_NOW = datetime(2026, 4, 21, 10, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
class _ControlledEmbedder:
    def __init__(self, mapping: dict[str, list[float]]):
        self._map = mapping

    def embed(self, text: str) -> list[float]:
        return list(self._map[text])


def _fragment_payload(fqn: str, text: str) -> dict:
    return {
        "qualified_name": fqn,
        "section_fqn": fqn.rsplit("#", 1)[0] + "#sec",
        "kind": "text",
        "text": text,
        "order_index": 0,
        "created_at": _NOW.isoformat(),
    }


def _rule_payload(fqn: str, statement: str) -> dict:
    return {
        "qualified_name": fqn,
        "statement": statement,
        "severity": "hard",
        "confirmed": True,
        "created_at": _NOW.isoformat(),
    }


def _described_payload(source_fqn: str, target_fqn: str) -> dict:
    return {
        "source_fqn": source_fqn,
        "target_fqn": target_fqn,
        "target_kind": "manual_fragment",
        "confidence": 1.0,
        "source": "manual",
        "created_at": _NOW.isoformat(),
    }


def _term_payload(fqn: str, label: str | None = None) -> dict:
    return {
        "qualified_name": fqn,
        "canonical_label": label or fqn.split(".")[-1],
        "aliases": [],
        "source": "manual",
        "confirmed": True,
        "created_at": _NOW.isoformat(),
    }


def _seed_registry_fragment(
    registry: InMemoryManualRegistry, *, fqn: str, text: str
) -> None:
    doc = ManualDocument(
        qualified_name="doc",
        title="Doc",
        source_path="/tmp/doc.md",
        format=ManualFormat.MARKDOWN,
        version="",
        checksum="a" * 64,
        authoritative=True,
        created_at=_NOW,
    )
    section = ManualSection(
        qualified_name="doc#sec",
        doc_fqn="doc",
        title="sec",
        heading_path=["Root"],
        order_index=0,
        created_at=_NOW,
    )
    frag = ManualFragment(
        qualified_name=fqn,
        section_fqn="doc#sec",
        kind=ManualFragmentKind.TEXT,
        text=text,
        order_index=0,
        created_at=_NOW,
    )
    registry.add(doc, sections=[section], fragments=[frag])


def _make_app(
    *,
    embeddings: dict[str, list[float]] | None = None,
):
    store = InMemoryGapStore()
    registry = InMemoryManualRegistry()
    embedder = _ControlledEmbedder(embeddings or {})
    detector = MissingInDetector(gap_store=store, clock=lambda: _NOW)
    engine = create_gap_engine(
        mode=GapMode.HIERARCHICAL,
        rule_differ=RuleASTDiffer(clock=lambda: _NOW),
        drifter=CosineDrifter(embedder=embedder, clock=lambda: _NOW, cutoff=0.65),
        llm_comparator=None,
        gap_store=store,
        clock=lambda: _NOW,
    )
    scanner = GapScanner(
        missing_detector=detector,
        gap_engine=engine,
        fragment_source=registry,
    )
    gaps_api.init(scanner=scanner, gap_store=store, manual_registry=registry)

    app = FastAPI()
    app.include_router(gaps_api.router)
    return app, store, registry


# ---------------------------------------------------------------------------
# 1. Service not initialized
# ---------------------------------------------------------------------------
def test_unconfigured_service_returns_503() -> None:
    gaps_api.reset()
    app = FastAPI()
    app.include_router(gaps_api.router)
    client = TestClient(app)

    r = client.post(
        "/api/modeling/gaps/scan",
        json={"repo_id": "prod", "rules": [], "described_in": []},
    )
    assert r.status_code == 503
    assert "not initialized" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. POST /scan — unified result shape (code_only + manual_only + conflicts)
# ---------------------------------------------------------------------------
def test_scan_returns_unified_result_with_three_buckets() -> None:
    app, store, _ = _make_app(
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    client = TestClient(app)

    body = {
        "repo_id": "prod",
        "gap_mode": "hierarchical",
        "business_terms": [_term_payload("inv.safety_stock")],
        "rules": [_rule_payload("rule.safety", "재고 10 이상")],
        "described_in": [_described_payload("rule.safety", "doc#sec#f0")],
        "fragments": [_fragment_payload("doc#sec#f0", "재고 20 이상")],
    }
    r = client.post("/api/modeling/gaps/scan", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert "code_only" in payload
    assert "manual_only" in payload
    assert "conflicts" in payload

    code_targets = {g["target_fqn"] for g in payload["code_only"]}
    conflict_targets = {g["target_fqn"] for g in payload["conflicts"]}
    assert code_targets == {"inv.safety_stock"}
    assert conflict_targets == {"rule.safety"}


# ---------------------------------------------------------------------------
# 3. POST /scan — auto-pull fragments from ManualRegistry when body omits
# ---------------------------------------------------------------------------
def test_scan_auto_pulls_fragments_when_body_omits() -> None:
    app, _, registry = _make_app()
    _seed_registry_fragment(
        registry, fqn="doc#sec#f0", text="**레지스트리용어** 등장"
    )
    client = TestClient(app)

    body = {
        "repo_id": "prod",
        "rules": [],
        "described_in": [],
        # fragments 생략 — registry 에서 auto-pull
    }
    r = client.post("/api/modeling/gaps/scan", json=body)
    assert r.status_code == 200
    payload = r.json()
    manual_targets = {g["target_fqn"] for g in payload["manual_only"]}
    assert manual_targets == {"레지스트리용어"}


def test_scan_uses_body_fragments_when_provided_ignoring_registry() -> None:
    app, _, registry = _make_app()
    _seed_registry_fragment(
        registry, fqn="doc#sec#fA", text="**레지스트리만** 등장"
    )
    client = TestClient(app)

    body = {
        "repo_id": "prod",
        "rules": [],
        "described_in": [],
        "fragments": [_fragment_payload("doc#sec#fB", "**바디만** 등장")],
    }
    r = client.post("/api/modeling/gaps/scan", json=body)
    assert r.status_code == 200
    manual_targets = {g["target_fqn"] for g in r.json()["manual_only"]}
    assert manual_targets == {"바디만"}


# ---------------------------------------------------------------------------
# 4. GET /gaps — list all + filters
# ---------------------------------------------------------------------------
def test_list_gaps_returns_all_pending_by_default() -> None:
    app, store, _ = _make_app()
    client = TestClient(app)

    # Scan first to seed store.
    client.post(
        "/api/modeling/gaps/scan",
        json={
            "repo_id": "prod",
            "business_terms": [_term_payload("inv.x")],
            "rules": [],
            "described_in": [],
            "fragments": [_fragment_payload("doc#sec#f0", "**발주점** 등장")],
        },
    )

    r = client.get("/api/modeling/gaps")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert len(body["items"]) >= 2   # 1 code_only + 1 manual_only


def test_list_gaps_direction_filter() -> None:
    app, _, _ = _make_app()
    client = TestClient(app)
    client.post(
        "/api/modeling/gaps/scan",
        json={
            "repo_id": "prod",
            "business_terms": [_term_payload("inv.x")],
            "rules": [],
            "described_in": [],
            "fragments": [_fragment_payload("doc#sec#f0", "**발주점** 등장")],
        },
    )

    r = client.get("/api/modeling/gaps", params={"direction": "code_only"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    for g in items:
        assert g["direction"] == "code_only"


def test_list_gaps_confirmed_filter_excludes_confirmed_by_default() -> None:
    app, store, _ = _make_app()
    client = TestClient(app)
    client.post(
        "/api/modeling/gaps/scan",
        json={
            "repo_id": "prod",
            "business_terms": [_term_payload("inv.x")],
            "rules": [],
            "described_in": [],
            "fragments": [],
        },
    )
    pending = list(store.list_pending())
    assert len(pending) == 1
    store.confirm(pending[0].id)

    # Default — only pending (unconfirmed) gaps.
    r = client.get("/api/modeling/gaps")
    assert r.status_code == 200
    assert r.json()["items"] == []

    # include_confirmed=true — all gaps.
    r2 = client.get("/api/modeling/gaps", params={"include_confirmed": "true"})
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["confirmed"] is True


# ---------------------------------------------------------------------------
# 5. POST /gaps/{id}/confirm — set confirmed=True
# ---------------------------------------------------------------------------
def test_confirm_gap_marks_gap_confirmed() -> None:
    app, store, _ = _make_app()
    client = TestClient(app)
    client.post(
        "/api/modeling/gaps/scan",
        json={
            "repo_id": "prod",
            "business_terms": [_term_payload("inv.x")],
            "rules": [],
            "described_in": [],
            "fragments": [],
        },
    )
    pending = list(store.list_pending())
    gap_id = pending[0].id

    r = client.post(f"/api/modeling/gaps/{gap_id}/confirm")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == gap_id
    assert body["confirmed"] is True

    # Sanity : store reflects confirmation.
    assert store.list_pending() == []


def test_confirm_unknown_gap_returns_404() -> None:
    app, _, _ = _make_app()
    client = TestClient(app)
    r = client.post("/api/modeling/gaps/does-not-exist/confirm")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 6. SSE stream — staged events in order
# ---------------------------------------------------------------------------
def test_scan_stream_emits_staged_sequence() -> None:
    app, _, _ = _make_app(
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    client = TestClient(app)

    body = {
        "repo_id": "prod",
        "business_terms": [_term_payload("inv.safety_stock")],
        "rules": [_rule_payload("rule.safety", "재고 10 이상")],
        "described_in": [_described_payload("rule.safety", "doc#sec#f0")],
        "fragments": [_fragment_payload("doc#sec#f0", "재고 20 이상")],
    }
    with client.stream(
        "POST", "/api/modeling/gaps/scan/stream", json=body,
    ) as r:
        assert r.status_code == 200
        events = _parse_sse(r.iter_lines())

    names = [e["event"] for e in events]
    assert names[0] == "scanning"
    assert "stage1_missing_in" in names
    assert "stage2_conflicts" in names
    assert names[-1] == "complete"

    complete_event = next(e for e in events if e["event"] == "complete")
    payload = json.loads(complete_event["data"])
    assert "code_only" in payload
    assert "conflicts" in payload
    code_targets = {g["target_fqn"] for g in payload["code_only"]}
    conflict_targets = {g["target_fqn"] for g in payload["conflicts"]}
    assert code_targets == {"inv.safety_stock"}
    assert conflict_targets == {"rule.safety"}


# ---------------------------------------------------------------------------
# 6b. SSE stream — real-time emission (E1-h)
# ---------------------------------------------------------------------------
async def test_scan_stream_pattern_pushes_stages_via_threadsafe_queue() -> None:
    """E1-h regression : `_on_progress` 가 worker thread 에서 호출되더라도
    main loop 의 asyncio.Queue 에 즉시 도착해야 함 (`loop.call_soon_threadsafe`
    경유). buffered-flush 였다면 worker scan 종료 전까진 queue 에 아무것도
    안 들어감.

    구현 패턴 자체를 검증 — HTTP TestClient 는 ASGITransport 가 스트림을
    버퍼링해서 real-time 검증이 어려움. 본 테스트는 그 우회 :
      - 진짜 async loop + 진짜 worker thread + 진짜 queue 사용.
      - worker 가 stage1 을 push 한 직후 main loop 가 queue 에서 꺼낼 수
        있는지 (= scan 종료 전에 가져갈 수 있는지) 검증.
    """
    import threading

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    gate = threading.Event()

    def _on_progress(stage: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, stage)

    def _worker() -> None:
        # 1) 즉시 두 stage push.
        _on_progress("scanning")
        _on_progress("stage1_missing_in")
        # 2) gate 대기 — main loop 가 위 두 stage 를 먼저 가져가야 풀린다.
        if not gate.wait(timeout=5.0):
            raise TimeoutError("gate not released — main loop blocked?")
        # 3) gate 풀린 후 나머지 stage push.
        _on_progress("stage2_conflicts")
        _on_progress("complete")

    # main loop 에서 worker 를 fire-and-forget. await 하면 buffered 됨.
    worker_task = asyncio.create_task(asyncio.to_thread(_worker))

    # main loop 에서 큐를 drain — stage1 받자마자 gate 풀어 worker 진행시킴.
    received: list[str] = []
    while True:
        stage = await asyncio.wait_for(queue.get(), timeout=5.0)
        received.append(stage)
        if stage == "stage1_missing_in":
            gate.set()
        if stage == "complete":
            break

    await worker_task
    assert received == [
        "scanning",
        "stage1_missing_in",
        "stage2_conflicts",
        "complete",
    ]


# ---------------------------------------------------------------------------
# 6c. Evidence panel + LLM 재평가 (E1-i)
# ---------------------------------------------------------------------------
def test_scan_response_includes_evidence_for_conflicts() -> None:
    """CONFLICTS_WITH 후보는 evidence dict 가 채워져야 (UI 패널 입력)."""
    app, _, _ = _make_app(
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    client = TestClient(app)
    body = {
        "repo_id": "prod",
        "rules": [_rule_payload("rule.safety", "재고 10 이상")],
        "described_in": [_described_payload("rule.safety", "doc#sec#f0")],
        "fragments": [_fragment_payload("doc#sec#f0", "재고 20 이상")],
    }
    r = client.post("/api/modeling/gaps/scan", json=body)
    assert r.status_code == 200
    payload = r.json()
    assert payload["conflicts"], "expected at least one conflict"
    ev = payload["conflicts"][0]["evidence"]
    assert ev["stage"] == "rule_ast"
    assert ev["rule_statement"] == "재고 10 이상"
    assert ev["fragment_text"] == "재고 20 이상"


def test_reevaluate_unknown_gap_returns_404() -> None:
    app, _, _ = _make_app()
    client = TestClient(app)
    r = client.post("/api/modeling/gaps/does-not-exist/reevaluate")
    assert r.status_code == 404


def test_reevaluate_missing_in_gap_returns_422() -> None:
    """MISSING_IN 은 LLM 재평가 의미 없음 → 422."""
    from datetime import datetime, timezone
    from backend.modeling.gap_detection.gap_models import GapCandidate
    from backend.modeling.manuals.manual_models import (
        GapDetectedBy, GapDirection, GapMode, GapSeverity,
    )

    app, store, _ = _make_app()
    store.upsert(
        GapCandidate(
            id="m1",
            direction=GapDirection.CODE_ONLY,
            target_fqn="x",
            counterpart_fqn=None,
            severity=GapSeverity.SOFT,
            detected_by=GapDetectedBy.HIERARCHICAL,
            gap_mode=GapMode.HIERARCHICAL,
            description="missing only",
            created_at=datetime.now(timezone.utc),
        )
    )
    client = TestClient(app)
    r = client.post("/api/modeling/gaps/m1/reevaluate")
    assert r.status_code == 422
    assert "CONFLICTS_WITH" in r.json()["detail"]


def test_reevaluate_without_comparator_returns_503() -> None:
    """Comparator 미설정 인스턴스 → 재평가 503."""
    from datetime import datetime, timezone
    from backend.modeling.gap_detection.gap_models import GapCandidate
    from backend.modeling.manuals.manual_models import (
        GapDetectedBy, GapMode, GapSeverity,
    )

    app, store, _ = _make_app()  # llm_comparator=None 기본
    store.upsert(
        GapCandidate(
            id="c1",
            direction=None,
            target_fqn="rule.x",
            counterpart_fqn="frag.y",
            severity=GapSeverity.HIGH,
            detected_by=GapDetectedBy.HIERARCHICAL,
            gap_mode=GapMode.HIERARCHICAL,
            description="rule_ast: ...",
            created_at=datetime.now(timezone.utc),
            evidence={
                "stage": "rule_ast",
                "rule_statement": "두께 240 이하",
                "fragment_text": "두께 250 이상",
            },
        )
    )
    client = TestClient(app)
    r = client.post("/api/modeling/gaps/c1/reevaluate")
    assert r.status_code == 503
    assert "comparator" in r.json()["detail"].lower()


def test_reevaluate_calls_comparator_and_updates_gap() -> None:
    """Comparator 가 새 severity 반환하면 gap 갱신, evidence.llm_reasoning 추가."""
    from datetime import datetime, timezone
    from backend.modeling.gap_detection.gap_models import GapCandidate
    from backend.modeling.manuals.manual_models import (
        GapDetectedBy, GapMode, GapSeverity,
    )

    class _StubComparator:
        def compare(self, *, rule, fragment, prior_severity, config):
            assert rule.statement == "두께 240 이하"
            assert fragment.text == "두께 250 이상"
            return GapSeverity.CRITICAL, "재무 영향 큼"

    app, store, _ = _make_app()
    # 재초기화 — comparator 주입
    gaps_api.reset()
    from fastapi import FastAPI
    from backend.modeling.gap_detection.gap_scanner import GapScanner
    from backend.modeling.gap_detection.embedding_drifter import (
        CosineDrifter,
    )
    from backend.modeling.gap_detection.gap_engine import create_gap_engine
    from backend.modeling.gap_detection.missing_in_detector import (
        MissingInDetector,
    )
    from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer
    from backend.modeling.gap_detection.gap_store import InMemoryGapStore
    from backend.modeling.manual_ingest.manual_registry import (
        InMemoryManualRegistry,
    )

    store2 = InMemoryGapStore()
    store2.upsert(
        GapCandidate(
            id="c2",
            direction=None,
            target_fqn="rule.x",
            counterpart_fqn="frag.y",
            severity=GapSeverity.HIGH,
            detected_by=GapDetectedBy.HIERARCHICAL,
            gap_mode=GapMode.HIERARCHICAL,
            description="rule_ast: ...",
            created_at=datetime.now(timezone.utc),
            evidence={
                "stage": "rule_ast",
                "rule_statement": "두께 240 이하",
                "fragment_text": "두께 250 이상",
            },
        )
    )
    embedder = _ControlledEmbedder({})
    scanner = GapScanner(
        missing_detector=MissingInDetector(gap_store=store2, clock=lambda: _NOW),
        gap_engine=create_gap_engine(
            mode=GapMode.HIERARCHICAL,
            rule_differ=RuleASTDiffer(clock=lambda: _NOW),
            drifter=CosineDrifter(embedder=embedder, clock=lambda: _NOW),
            llm_comparator=_StubComparator(),
            gap_store=store2,
            clock=lambda: _NOW,
        ),
        fragment_source=InMemoryManualRegistry(),
    )
    gaps_api.init(
        scanner=scanner,
        gap_store=store2,
        manual_registry=InMemoryManualRegistry(),
        llm_comparator=_StubComparator(),
    )

    app2 = FastAPI()
    app2.include_router(gaps_api.router)
    client = TestClient(app2)
    r = client.post("/api/modeling/gaps/c2/reevaluate")
    assert r.status_code == 200
    body = r.json()
    assert body["severity"] == "critical"
    assert body["evidence"]["llm_reasoning"] == "재무 영향 큼"
    assert body["evidence"]["llm_severity"] == "critical"
    # store 도 갱신됨
    updated = store2.get("c2")
    assert updated is not None
    assert updated.severity is GapSeverity.CRITICAL


def test_scan_stream_emits_complete_event_with_payload() -> None:
    """SSE complete 이벤트는 단순 stage 라벨이 아닌 UnifiedScanResponse JSON 을 담아야 함."""
    app, _, _ = _make_app()
    client = TestClient(app)

    with client.stream(
        "POST", "/api/modeling/gaps/scan/stream",
        json={"repo_id": "p"},
    ) as r:
        assert r.status_code == 200
        events = _parse_sse(r.iter_lines())

    complete = next((e for e in events if e["event"] == "complete"), None)
    assert complete is not None
    payload = json.loads(complete["data"])
    assert "code_only" in payload
    assert "manual_only" in payload
    assert "conflicts" in payload
    assert "errors" in payload


def test_scan_stream_propagates_scan_exception() -> None:
    """스캔 도중 예외 발생 → "error" 이벤트 emit 후 스트림 종료."""
    from backend.modeling.gap_detection.gap_scanner import (
        STAGE_MISSING_IN,
        STAGE_SCANNING,
    )

    class _BoomScanner:
        def scan(self, **kwargs):
            on_progress = kwargs["on_progress"]
            on_progress(STAGE_SCANNING)
            on_progress(STAGE_MISSING_IN)
            raise RuntimeError("boom")

    gaps_api.reset()
    app = FastAPI()
    app.include_router(gaps_api.router)
    gaps_api.init(
        scanner=_BoomScanner(),
        gap_store=InMemoryGapStore(),
        manual_registry=None,
    )

    client = TestClient(app)
    received: list[dict[str, str]] = []
    with client.stream(
        "POST", "/api/modeling/gaps/scan/stream", json={"repo_id": "p"},
    ) as r:
        assert r.status_code == 200
        events = _parse_sse(r.iter_lines())
        received.extend(events)

    names = [e["event"] for e in received]
    # "error" 이벤트가 마지막에 와야 함, complete 는 안 옴.
    assert "error" in names
    assert names[-1] == "error"
    assert "complete" not in names


# ---------------------------------------------------------------------------
# 7. Validation — empty body missing rules/described_in still OK (all default [])
# ---------------------------------------------------------------------------
def test_scan_with_minimal_body_no_errors() -> None:
    app, _, _ = _make_app()
    client = TestClient(app)
    r = client.post(
        "/api/modeling/gaps/scan",
        json={"repo_id": "prod"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["code_only"] == []
    assert payload["manual_only"] == []
    assert payload["conflicts"] == []


def test_scan_requires_repo_id() -> None:
    app, _, _ = _make_app()
    client = TestClient(app)
    r = client.post("/api/modeling/gaps/scan", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Helper — SSE parser (shared pattern with test_reverse_lookup_api)
# ---------------------------------------------------------------------------
def _parse_sse(lines) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in lines:
        line = raw if isinstance(raw, str) else raw.decode("utf-8")
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:"):].strip()
    if current:
        events.append(current)
    return events
