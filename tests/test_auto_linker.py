"""Auto-linker tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.auto_linker import (
    AutoLinkResult,
    auto_link_rules_to_fragments,
    cosine,
)
from backend.modeling.gap_detection.embedding_drifter import HashingTextEmbedder
from backend.modeling.manuals.manual_models import (
    ManualFragment, ManualFragmentKind,
)
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


def _rule(fqn: str, statement: str) -> BusinessRule:
    return BusinessRule(
        qualified_name=fqn, statement=statement, target_fqn="t",
        severity=RuleSeverity.HARD, source=f"javadoc:{fqn}",
        source_fqn=fqn,
        confirmed=False, created_at=datetime.now(timezone.utc),
    )


def _frag(fqn: str, sec_fqn: str, text: str, order: int = 0) -> ManualFragment:
    return ManualFragment(
        qualified_name=fqn, section_fqn=sec_fqn,
        kind=ManualFragmentKind.TEXT, text=text, order_index=order,
        created_at=datetime.now(timezone.utc),
    )


def test_cosine_orthogonal_returns_zero():
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)


def test_cosine_identical_returns_one():
    assert cosine([1, 1], [1, 1]) == pytest.approx(1.0)


def test_empty_inputs_return_no_bindings():
    e = HashingTextEmbedder()
    r = auto_link_rules_to_fragments([], [], e)
    assert r.bindings == []
    assert r.total_pairs_evaluated == 0


class TestAutoLink:
    def test_top_k_limit_per_rule(self):
        e = HashingTextEmbedder()
        rule = _rule("rule.x", "slab 길이 하한 계산")
        frags = [_frag(f"frag.{i}", "sec.1", f"slab 길이 하한 변형 {i}", i) for i in range(5)]
        r = auto_link_rules_to_fragments([rule], frags, e, top_k=2, min_confidence=0.0)
        assert len(r.bindings) == 2

    def test_threshold_filters(self):
        e = HashingTextEmbedder()
        rule = _rule("rule.x", "abc def ghi")
        # 완전히 다른 텍스트 → 낮은 유사도 → threshold 미달
        frags = [_frag("frag.1", "sec.1", "xyz mnp qrs")]
        r = auto_link_rules_to_fragments([rule], frags, e, top_k=3, min_confidence=0.99)
        assert r.bindings == []
        assert r.skipped_below_threshold >= 1

    def test_identical_text_yields_high_confidence(self):
        e = HashingTextEmbedder()
        rule = _rule("rule.x", "slab 길이 하한 = max(...)")
        frag = _frag("frag.1", "sec.1", "slab 길이 하한 = max(...)")
        r = auto_link_rules_to_fragments([rule], [frag], e, top_k=1, min_confidence=0.5)
        assert len(r.bindings) == 1
        binding = r.bindings[0]
        assert binding.source_fqn == "rule.x"
        assert binding.target_fqn == "frag.1"
        assert binding.confidence >= 0.95
        assert binding.source == "embedding"

    def test_target_kind_is_fragment(self):
        e = HashingTextEmbedder()
        rule = _rule("rule.x", "abc")
        frag = _frag("frag.1", "sec.1", "abc")
        r = auto_link_rules_to_fragments([rule], [frag], e, top_k=1, min_confidence=0.0)
        assert r.bindings[0].target_kind.value == "manual_fragment"

    def test_pairs_evaluated_count(self):
        e = HashingTextEmbedder()
        rules = [_rule(f"r.{i}", f"text {i}") for i in range(3)]
        frags = [_frag(f"f.{i}", "sec.1", f"text {i}", i) for i in range(4)]
        r = auto_link_rules_to_fragments(rules, frags, e, top_k=2, min_confidence=0.0)
        assert r.total_pairs_evaluated == 12  # 3 × 4


# ---------------------------------------------------------------------------
# 통합 — auto_linker + gap_scanner → conflicts 발견 (end-to-end)
# ---------------------------------------------------------------------------
class TestAutoLinkerGapScannerIntegration:
    """auto_linker 가 만든 DescribedInBinding 을 gap_scanner 에 넣으면 conflicts 가 잡힘."""

    def test_auto_linked_bindings_yield_conflicts(self):
        from backend.modeling.gap_detection.gap_engine import create_gap_engine
        from backend.modeling.gap_detection.gap_scanner import GapScanner
        from backend.modeling.gap_detection.gap_store import InMemoryGapStore
        from backend.modeling.gap_detection.missing_in_detector import (
            MissingInDetector,
        )
        from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer
        from backend.modeling.gap_detection.embedding_drifter import (
            CosineDrifter,
        )
        from backend.modeling.gap_detection.gap_models import ScanConfig
        from backend.modeling.manuals.manual_models import GapMode

        # 시나리오 : 코드 룰 = "값 ≥ 10", 매뉴얼 = "값 = 7.5" → numeric 불일치
        rule = _rule("rule.threshold", "값 ≥ 10")
        frag = _frag("frag.std.0", "sec.std", "값은 7.5 이상이어야 함")
        # auto-link → 의미 비슷 → DescribedInBinding 생성
        e = HashingTextEmbedder()
        link_result = auto_link_rules_to_fragments(
            [rule], [frag], e, top_k=1, min_confidence=0.0,
        )
        assert len(link_result.bindings) == 1

        # gap_scanner 에 넣어서 conflicts 탐지 가능 여부 확인
        store = InMemoryGapStore()
        scanner = GapScanner(
            missing_detector=MissingInDetector(gap_store=store),
            gap_engine=create_gap_engine(
                mode=GapMode.HIERARCHICAL,
                rule_differ=RuleASTDiffer(),
                drifter=CosineDrifter(embedder=HashingTextEmbedder()),
                gap_store=store,
            ),
        )
        config = ScanConfig(
            repo_id="repo", gap_mode=GapMode.HIERARCHICAL,
            include_unconfirmed_terms=True,
        )
        result = scanner.scan(
            config=config,
            business_terms=[],
            business_rules=[rule],
            described_in=link_result.bindings,
            fragments=[frag],
        )
        # rule_ast 단계에서 numeric/comparator/unit 차이 잡힘
        # (정확한 conflict count 는 RuleASTDiffer 구현에 따라 다름; 1건 이상이면 통합 OK)
        assert len(result.conflicts) >= 1


# ---------------------------------------------------------------------------
# Structured Manual directive — fragment.attributes.rule 이 우선
# ---------------------------------------------------------------------------
class TestStructuredDirective:
    def test_directive_resolved_with_confidence_1_and_source_manual_directive(self):
        from backend.modeling.gap_detection.embedding_drifter import HashingTextEmbedder
        from backend.modeling.manuals.manual_models import ManualFragment, ManualFragmentKind
        from datetime import datetime, timezone
        rule = _rule("rule.X", "원본 룰 statement (전혀 다른 글자)")
        frag = ManualFragment(
            qualified_name="frag.x", section_fqn="sec.x",
            kind=ManualFragmentKind.TEXT, text="아예 무관한 텍스트",
            order_index=0, attributes={"rule": "rule.X"},
            created_at=datetime.now(timezone.utc),
        )
        r = auto_link_rules_to_fragments([rule], [frag], HashingTextEmbedder())
        assert len(r.bindings) == 1
        assert r.bindings[0].source == "manual_directive"
        assert r.bindings[0].confidence == 1.0
        assert r.bindings[0].target_fqn == "frag.x"

    def test_directive_skips_embedding_pass_for_that_rule(self):
        from backend.modeling.gap_detection.embedding_drifter import HashingTextEmbedder
        from backend.modeling.manuals.manual_models import ManualFragment, ManualFragmentKind
        from datetime import datetime, timezone
        rule = _rule("rule.A", "ABC")
        frag1 = ManualFragment(
            qualified_name="f.1", section_fqn="s.1",
            kind=ManualFragmentKind.TEXT, text="random",
            order_index=0, attributes={"rule": "rule.A"},
            created_at=datetime.now(timezone.utc),
        )
        frag2 = ManualFragment(
            qualified_name="f.2", section_fqn="s.1",
            kind=ManualFragmentKind.TEXT, text="ABC ABC",
            order_index=1, attributes={},
            created_at=datetime.now(timezone.utc),
        )
        r = auto_link_rules_to_fragments(
            [rule], [frag1, frag2], HashingTextEmbedder(),
            top_k=3, min_confidence=0.0,
        )
        assert all(b.target_fqn == "f.1" for b in r.bindings)
        assert all(b.source == "manual_directive" for b in r.bindings)
        assert r.total_pairs_evaluated == 0

    def test_unmatched_directive_falls_back_to_embedding(self):
        from backend.modeling.gap_detection.embedding_drifter import HashingTextEmbedder
        from backend.modeling.manuals.manual_models import ManualFragment, ManualFragmentKind
        from datetime import datetime, timezone
        rule = _rule("rule.X", "abc")
        frag = ManualFragment(
            qualified_name="f.0", section_fqn="s.0",
            kind=ManualFragmentKind.TEXT, text="abc abc",
            order_index=0, attributes={"rule": "rule.OTHER"},
            created_at=datetime.now(timezone.utc),
        )
        r = auto_link_rules_to_fragments(
            [rule], [frag], HashingTextEmbedder(),
            top_k=1, min_confidence=0.0,
        )
        assert r.total_pairs_evaluated == 1
        if r.bindings:
            assert r.bindings[0].source == "embedding"
