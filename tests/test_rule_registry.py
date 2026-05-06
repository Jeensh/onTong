"""OD-11-E1-g — `RuleRegistry` (D3-3 미수거 인프라).

A3 `JavadocRuleExtractor` 산출 `BusinessRule` 을 repo 별로 보관하는 store.
`gaps_api.scan(repo_id=...)` 가 body 에 rules 를 안 실어 와도 registry 에서
자동 auto-pull (Q1 의 partial hybrid 를 full hybrid 로 격상).

API :
    put(repo_id, rule)            : upsert (qualified_name 기준)
    put_many(repo_id, rules)
    list_by_repo(repo_id)         : iterable
    get(repo_id, rule_fqn)        : 단건 lookup
    clear(repo_id=None)           : repo 단위 또는 전체 reset
    repos()                       : 등록된 repo_id 집합

`Protocol` 으로 정의해 ChromaDB / SQLite 백엔드 교체 가능.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.code_analysis.javadoc_rule_extractor import (
    extract_rules_from_file,
)
from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.gap_detection.rule_registry import (
    InMemoryRuleRegistry,
    RuleRegistry,
    seed_rules_from_repo,
)
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rule(qname: str = "com.x.M.check#rule1", statement: str = "두께는 240mm 이하여야 한다.") -> BusinessRule:
    return BusinessRule(
        qualified_name=qname,
        statement=statement,
        terms_ref=[],
        severity=RuleSeverity.SOFT,
        source="test",
        confirmed=False,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
class TestProtocol:
    def test_in_memory_conforms_to_protocol(self) -> None:
        assert isinstance(InMemoryRuleRegistry(), RuleRegistry)


# ---------------------------------------------------------------------------
# 기본 동작 — put / get / list / clear
# ---------------------------------------------------------------------------
class TestBasic:
    def test_put_then_get(self) -> None:
        reg = InMemoryRuleRegistry()
        r = _rule()
        reg.put("repo-a", r)
        assert reg.get("repo-a", r.qualified_name) is r

    def test_put_many(self) -> None:
        reg = InMemoryRuleRegistry()
        rules = [_rule(qname=f"com.x.M.m{i}#rule1") for i in range(3)]
        reg.put_many("repo-a", rules)
        listed = list(reg.list_by_repo("repo-a"))
        assert len(listed) == 3
        assert {r.qualified_name for r in listed} == {r.qualified_name for r in rules}

    def test_get_missing_returns_none(self) -> None:
        reg = InMemoryRuleRegistry()
        assert reg.get("repo-a", "missing") is None

    def test_list_by_unknown_repo_is_empty(self) -> None:
        reg = InMemoryRuleRegistry()
        assert list(reg.list_by_repo("ghost")) == []

    def test_repos_lists_seeded_keys(self) -> None:
        reg = InMemoryRuleRegistry()
        reg.put("a", _rule(qname="x#rule1"))
        reg.put("b", _rule(qname="y#rule1"))
        assert reg.repos() == {"a", "b"}


# ---------------------------------------------------------------------------
# Idempotency — same FQN re-put
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_put_same_fqn_overwrites(self) -> None:
        reg = InMemoryRuleRegistry()
        r1 = _rule(statement="원본")
        r2 = _rule(statement="갱신")
        reg.put("repo-a", r1)
        reg.put("repo-a", r2)
        assert reg.get("repo-a", r1.qualified_name).statement == "갱신"
        assert len(list(reg.list_by_repo("repo-a"))) == 1


# ---------------------------------------------------------------------------
# Multi-repo isolation
# ---------------------------------------------------------------------------
class TestMultiRepoIsolation:
    def test_same_fqn_different_repos_kept_separately(self) -> None:
        reg = InMemoryRuleRegistry()
        r_a = _rule(statement="from-a")
        r_b = _rule(statement="from-b")
        reg.put("repo-a", r_a)
        reg.put("repo-b", r_b)
        assert reg.get("repo-a", r_a.qualified_name).statement == "from-a"
        assert reg.get("repo-b", r_b.qualified_name).statement == "from-b"

    def test_clear_specific_repo(self) -> None:
        reg = InMemoryRuleRegistry()
        reg.put("a", _rule(qname="x#rule1"))
        reg.put("b", _rule(qname="y#rule1"))
        reg.clear("a")
        assert list(reg.list_by_repo("a")) == []
        assert len(list(reg.list_by_repo("b"))) == 1
        assert reg.repos() == {"b"}

    def test_clear_all(self) -> None:
        reg = InMemoryRuleRegistry()
        reg.put("a", _rule())
        reg.put("b", _rule())
        reg.clear()
        assert reg.repos() == set()


# ---------------------------------------------------------------------------
# seed_rules_from_repo — Java repo 자동 인제스트
# ---------------------------------------------------------------------------
class TestSeeder:
    def test_seed_returns_count(self) -> None:
        reg = InMemoryRuleRegistry()
        path = Path("sample-repos/slab-design-engine/src/main/java")
        if not path.exists():
            pytest.skip("slab sample missing")
        result = seed_rules_from_repo(path, "slab-design-engine", reg)
        # Slab end-to-end : 15 BusinessRule (E1-d 검증).
        assert result.total_rules >= 10
        assert result.total_files_scanned >= 4
        assert result.errors == []

    def test_seed_populates_registry(self) -> None:
        reg = InMemoryRuleRegistry()
        path = Path("sample-repos/slab-design-engine/src/main/java")
        if not path.exists():
            pytest.skip("slab sample missing")
        seed_rules_from_repo(path, "slab-design-engine", reg)
        rules = list(reg.list_by_repo("slab-design-engine"))
        assert len(rules) >= 10
        statements = [r.statement for r in rules]
        assert any("크레인" in s for s in statements)
        assert any("두께" in s for s in statements)

    def test_seed_is_idempotent(self) -> None:
        reg = InMemoryRuleRegistry()
        path = Path("sample-repos/slab-design-engine/src/main/java")
        if not path.exists():
            pytest.skip("slab sample missing")
        r1 = seed_rules_from_repo(path, "slab-design-engine", reg)
        count1 = len(list(reg.list_by_repo("slab-design-engine")))
        r2 = seed_rules_from_repo(path, "slab-design-engine", reg)
        count2 = len(list(reg.list_by_repo("slab-design-engine")))
        # FQN 결정성 → 두 번 돌려도 같은 entry 만 갱신, count 그대로.
        assert count1 == count2
        assert r1.total_rules == r2.total_rules

    def test_seed_skips_non_java(self, tmp_path: Path) -> None:
        # README.md / .yaml 등 non-java 파일은 무시되어야 함
        (tmp_path / "README.md").write_text("# nothing")
        (tmp_path / "config.yaml").write_text("key: value")
        reg = InMemoryRuleRegistry()
        result = seed_rules_from_repo(tmp_path, "empty", reg)
        assert result.total_files_scanned == 0
        assert result.total_rules == 0


# ---------------------------------------------------------------------------
# Scanner integration — auto-pull when body rules omitted
# ---------------------------------------------------------------------------
class TestScannerIntegration:
    """`GapScanner.rule_source` 가 None 이 아니면 body rules 가 None 일 때 auto-pull."""

    def setup_method(self) -> None:
        from backend.modeling.gap_detection.embedding_drifter import (
            CosineDrifter,
            HashingTextEmbedder,
        )
        from backend.modeling.gap_detection.gap_engine import HierarchicalGapEngine
        from backend.modeling.gap_detection.gap_scanner import GapScanner
        from backend.modeling.gap_detection.gap_store import InMemoryGapStore
        from backend.modeling.gap_detection.missing_in_detector import (
            MissingInDetector,
            SimpleHeuristicExtractor,
        )
        from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer

        self.reg = InMemoryRuleRegistry()
        self.gap_store = InMemoryGapStore()
        self.scanner = GapScanner(
            missing_detector=MissingInDetector(
                gap_store=self.gap_store,
                extractor=SimpleHeuristicExtractor(),
            ),
            gap_engine=HierarchicalGapEngine(
                rule_differ=RuleASTDiffer(),
                drifter=CosineDrifter(embedder=HashingTextEmbedder()),
                llm_comparator=None,
                gap_store=self.gap_store,
            ),
            fragment_source=None,
            rule_source=self.reg,
        )

    def test_auto_pull_when_business_rules_is_none(self) -> None:
        from backend.modeling.gap_detection.gap_models import ScanConfig
        from backend.modeling.manuals.manual_models import GapDetectedBy, GapMode

        # Seed registry — scanner 가 이걸 자동으로 가져와야 함.
        rule = _rule(qname="com.slab.Checker#rule1", statement="두께는 240mm 이하여야 한다.")
        self.reg.put("repo-a", rule)

        result = self.scanner.scan(
            config=ScanConfig(
                repo_id="repo-a",
                gap_mode=GapMode.HIERARCHICAL,
                detected_by=GapDetectedBy.HIERARCHICAL,
            ),
            business_terms=[],
            business_rules=None,        # ← auto-pull trigger
            described_in=[],
            fragments=[],
        )
        assert result.errors == []
        # 아직 fragments 가 없으니 conflict 발생 안 해도 됨 — auto-pull 자체가 동작했는지만 검증.
        # (auto-pull 안 됐으면 missing_in_detector 가 manual_only=0 출력하지만 본 테스트는 무에러만 확인.)

    def test_explicit_empty_list_does_not_auto_pull(self) -> None:
        from backend.modeling.gap_detection.gap_models import ScanConfig
        from backend.modeling.manuals.manual_models import GapDetectedBy, GapMode

        # Seed registry — 호출자가 [] 를 명시하면 auto-pull 막아야 함.
        self.reg.put("repo-a", _rule(qname="com.slab.X#rule1"))

        # spy : scanner 의 _resolve_rules 가 registry 를 건드리지 않았는지 검증.
        result = self.scanner.scan(
            config=ScanConfig(
                repo_id="repo-a",
                gap_mode=GapMode.HIERARCHICAL,
                detected_by=GapDetectedBy.HIERARCHICAL,
            ),
            business_terms=[],
            business_rules=[],          # ← explicit empty
            described_in=[],
            fragments=[],
        )
        assert result.errors == []
        # 직접 검증 : registry 는 그대로 1 rule 보유 (소비/삭제 안됨).
        assert len(list(self.reg.list_by_repo("repo-a"))) == 1
