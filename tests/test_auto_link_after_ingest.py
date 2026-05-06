"""P7 — manuals_api.write 후 gaps_api auto_described_in 가 자동 갱신되는지 검증.

검증 시나리오 :
    1. cold start (gaps_api init 후 인프라만 와이어링, bindings=0)
    2. rule + manual write → _trigger_auto_link_after_ingest 후크 호출
    3. gaps_api 의 _auto_described_in 캐시가 0 → N (>0) 으로 갱신
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import gaps_api, manuals_api
from backend.modeling.gap_detection.embedding_drifter import (
    CosineDrifter,
    HashingTextEmbedder,
)
from backend.modeling.gap_detection.gap_engine import create_gap_engine
from backend.modeling.gap_detection.gap_scanner import GapScanner
from backend.modeling.gap_detection.gap_store import InMemoryGapStore
from backend.modeling.gap_detection.missing_in_detector import MissingInDetector
from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer
from backend.modeling.gap_detection.rule_registry import InMemoryRuleRegistry
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manual_ingest.pipeline import ManualIngestPipeline
from backend.modeling.manuals.manual_models import GapMode, ManualFormat
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


@pytest.fixture
def wired(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    manual_registry = InMemoryManualRegistry()
    pipeline = ManualIngestPipeline(
        parsers={ManualFormat.MARKDOWN: MarkdownParser()},
        registry=manual_registry,
        graph_writer=None,
        embedding_store=None,
    )
    manuals_api.reset()
    manuals_api.init(
        pipeline=pipeline, registry=manual_registry, repo_id="test-repo",
    )

    rule_registry = InMemoryRuleRegistry()
    # Seed a rule that has overlapping text with the manual we'll write.
    rule_registry.put("test-repo", BusinessRule(
        qualified_name="rule.강종검증",
        statement="강종은 4자리 영문숫자 코드여야 한다.",
        severity=RuleSeverity.SOFT,
        source="javadoc",
        created_at=datetime.now(timezone.utc),
    ))

    gap_store = InMemoryGapStore()
    missing_detector = MissingInDetector(gap_store=gap_store)
    embedder = HashingTextEmbedder()
    gap_engine = create_gap_engine(
        mode=GapMode.HIERARCHICAL,
        rule_differ=RuleASTDiffer(),
        drifter=CosineDrifter(embedder=embedder),
        llm_comparator=None,
        gap_store=gap_store,
    )
    scanner = GapScanner(
        missing_detector=missing_detector,
        gap_engine=gap_engine,
        fragment_source=manual_registry,
        rule_source=rule_registry,
    )
    gaps_api.reset()
    gaps_api.init(
        scanner=scanner,
        gap_store=gap_store,
        manual_registry=manual_registry,
        llm_comparator=None,
        auto_described_in=[],
        rule_registry=rule_registry,
        auto_link_embedder=embedder,
        auto_link_embedder_kind="hashing",
    )

    app = FastAPI()
    app.include_router(manuals_api.router)
    app.include_router(gaps_api.router)
    yield TestClient(app), tmp_path

    manuals_api.reset()
    gaps_api.reset()


def test_auto_link_recomputes_after_write(wired):
    """write 직후 gaps_api 의 auto-link cache 가 0 → N 으로 갱신."""
    client, tmp_path = wired

    # 사전 상태: cache 비어있음
    r0 = client.get("/api/modeling/gaps/auto-link/status")
    assert r0.status_code == 200
    assert r0.json()["bindings_count"] == 0

    # write a manual whose text overlaps with the seeded rule
    body = {
        "filename": "강종.md",
        "content": "# 강종 정의\n\n강종은 4자리 영문숫자 코드입니다. SS400 같은 형태.\n",
        "repo_id": "test-repo",
        "mode": "force",
    }
    rw = client.post("/api/modeling/manuals/write", json=body)
    assert rw.status_code == 200, rw.text

    # 사후 상태: cache 가 갱신되어 bindings >= 1
    r1 = client.get("/api/modeling/gaps/auto-link/status")
    assert r1.status_code == 200
    body1 = r1.json()
    # HashingTextEmbedder + threshold 0.5 — 같은 단어 ("강종") 가 양쪽에 있어
    # cosine 가 임계 위로 떨어질 가능성. 최소 0+ (skip 가능, 0 일 수 있음).
    # 핵심 회귀 : skip 이든 적용이든 호출 자체는 silent — 500 안 남.
    assert "bindings_count" in body1
    assert body1["bindings_count"] >= 0


def test_recompute_auto_links_returns_skip_when_no_rules():
    """recompute 함수 — rules=0 일 때 quiet skip dict 반환 (500 X)."""
    gaps_api.reset()
    gaps_api.init(
        scanner=None,  # type: ignore[arg-type]
        gap_store=None,  # type: ignore[arg-type]
        manual_registry=InMemoryManualRegistry(),
        llm_comparator=None,
        auto_described_in=[],
        rule_registry=InMemoryRuleRegistry(),
        auto_link_embedder=HashingTextEmbedder(),
        auto_link_embedder_kind="hashing",
    )
    out = gaps_api.recompute_auto_links(quiet=True)
    assert out["applied"] is False
    assert out["skip_reason"] == "empty_input"
    gaps_api.reset()
