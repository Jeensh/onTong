"""OD-11-E1-d (A3) — Javadoc → BusinessRule 추출기.

Slab 샘플의 한국어 Javadoc 룰 문장을 `BusinessRule` Pydantic DTO + `VALIDATES`
엣지 (`business_rule → method/class`) 로 변환. CONFLICTS_WITH gap 감지의
**코드 쪽 rule 입력**.

스펙:
- Class-level Javadoc → 모든 추출 룰이 class FQN 을 target 으로 VALIDATES.
- Method-level Javadoc → method FQN 을 target.
- Field-level Javadoc 은 v1 에서 skip (rule 의미가 약함).
- `/** ... */` Javadoc 만 처리. `/* ... */` 일반 block_comment 는 skip.
- Rule FQN = `{target_fqn}#rule{N}` (1-indexed, deterministic).
- Severity = HARD if 금지/불가/Exception/IllegalArgumentException, else SOFT.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.code_analysis.javadoc_rule_extractor import (
    JavadocRuleExtractor,
    extract_rules_from_file,
)
from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import RelationKinds
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _extract(content: str, file_path: str = "Demo.java"):
    parser = JavaParser()
    parse_result = parser.parse_file(Path(file_path), content)
    return extract_rules_from_file(file_path, content, parse_result)


# ---------------------------------------------------------------------------
# 기본 동작 — Javadoc 인식 / 비-Javadoc skip / Javadoc 부재
# ---------------------------------------------------------------------------
class TestBasic:
    def test_no_comments_yields_no_rules(self) -> None:
        src = """\
package com.x;
public class A {
    public void run() {}
}
"""
        rules, edges = _extract(src)
        assert rules == []
        assert edges == []

    def test_non_javadoc_block_comment_is_ignored(self) -> None:
        src = """\
package com.x;
/* 그냥 일반 주석. 두께 240mm 이상이어야 한다. */
public class A {
    public void run() {}
}
"""
        rules, edges = _extract(src)
        assert rules == [], "일반 /* */ 주석은 skip 해야 함"
        assert edges == []

    def test_javadoc_without_rule_keywords_yields_no_rules(self) -> None:
        # 단순 설명만 있는 Javadoc — heuristic 미매치
        src = """\
package com.x;
/**
 * 단순 설명입니다. 그냥 클래스 입니다.
 */
public class A {
    public void run() {}
}
"""
        rules, _ = _extract(src)
        assert rules == []


# ---------------------------------------------------------------------------
# Class-level Javadoc — bullet list
# ---------------------------------------------------------------------------
class TestClassLevelBullets:
    SRC = """\
package com.x;
/**
 * 설비 제약 검증기. 개별 제약별 메서드로 분리.
 *
 * 검증 대상 규칙:
 *  - slab 폭은 압연기 최대 폭 이하여야 한다.
 *  - slab 길이는 가열로 최대 길이 이하여야 한다.
 *  - slab 두께는 최소 두께 이상, 최대 두께 이하여야 한다.
 *  - slab 중량은 크레인 최대 하중을 초과할 수 없다.
 */
public class Checker {
    public void validate() {}
}
"""

    def test_extracts_four_bullet_rules(self) -> None:
        rules, edges = _extract(self.SRC)
        assert len(rules) == 4
        # 모두 class FQN 을 target 으로 VALIDATES
        targets = {e.target for e in edges}
        assert targets == {"com.x.Checker"}
        # 모든 엣지는 VALIDATES kind
        assert all(e.kind == RelationKinds.VALIDATES for e in edges)

    def test_rule_fqns_are_deterministic_and_unique(self) -> None:
        rules, _ = _extract(self.SRC)
        fqns = [r.qualified_name for r in rules]
        assert fqns == [
            "com.x.Checker#rule1",
            "com.x.Checker#rule2",
            "com.x.Checker#rule3",
            "com.x.Checker#rule4",
        ]
        # 두 번 추출해도 동일
        rules2, _ = _extract(self.SRC)
        assert [r.qualified_name for r in rules2] == fqns

    def test_statement_preserves_korean_text(self) -> None:
        rules, _ = _extract(self.SRC)
        statements = [r.statement for r in rules]
        # 핵심 토큰이 보존되어야 함 (RuleASTDiffer 의 입력)
        assert any("압연기 최대 폭" in s for s in statements)
        assert any("가열로 최대 길이" in s for s in statements)
        assert any("최소 두께 이상, 최대 두께 이하" in s for s in statements)
        assert any("크레인 최대 하중" in s for s in statements)

    def test_edge_source_matches_rule_fqn(self) -> None:
        rules, edges = _extract(self.SRC)
        edge_sources = {e.source for e in edges}
        rule_fqns = {r.qualified_name for r in rules}
        assert edge_sources == rule_fqns


# ---------------------------------------------------------------------------
# Method-level Javadoc
# ---------------------------------------------------------------------------
class TestMethodLevel:
    def test_method_level_javadoc_targets_method_fqn(self) -> None:
        src = """\
package com.x;
public class M {
    /**
     * 두께는 180mm 이상 240mm 이하여야 한다.
     */
    public void check() {}
}
"""
        rules, edges = _extract(src)
        assert len(rules) == 1
        assert edges[0].target == "com.x.M.check"
        assert edges[0].source == "com.x.M.check#rule1"
        assert edges[0].kind == RelationKinds.VALIDATES

    def test_multiple_sentences_in_one_javadoc(self) -> None:
        src = """\
package com.x;
public class M {
    /**
     * 두께는 240mm 이하여야 한다. 폭은 2400mm 이하여야 한다.
     */
    public void check() {}
}
"""
        rules, _ = _extract(src)
        # 두 룰성 문장이 분리되어야 함 (사실 진술은 휴리스틱이 reject 하므로
        # 두 문장 모두에 룰 키워드 포함)
        assert len(rules) == 2

    def test_factual_statement_without_rule_keyword_is_filtered(self) -> None:
        # "X 는 2400mm 이다" 는 정의/사실이지 규칙이 아님 — heuristic 이 reject 해야.
        src = """\
package com.x;
public class M {
    /** 압연기 최대 폭은 2400mm 이다. */
    public void info() {}
}
"""
        rules, _ = _extract(src)
        assert rules == []

    def test_method_without_javadoc_is_skipped(self) -> None:
        src = """\
package com.x;
public class M {
    /**
     * 두께는 240mm 이하여야 한다.
     */
    public void a() {}

    public void b() {}
}
"""
        rules, edges = _extract(src)
        assert len(rules) == 1
        assert edges[0].target == "com.x.M.a"


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------
class TestSeverity:
    def test_prohibition_keyword_is_hard(self) -> None:
        src = """\
package com.x;
public class M {
    /** 음수 두께는 허용되지 않으며 IllegalArgumentException 을 던진다. */
    public void check() {}
}
"""
        rules, _ = _extract(src)
        assert len(rules) == 1
        assert rules[0].severity is RuleSeverity.HARD

    def test_geupgi_keyword_is_hard(self) -> None:
        src = """\
package com.x;
public class M {
    /** 두께 250mm 초과는 금지된다. */
    public void check() {}
}
"""
        rules, _ = _extract(src)
        assert len(rules) == 1
        assert rules[0].severity is RuleSeverity.HARD

    def test_comparator_only_is_soft(self) -> None:
        src = """\
package com.x;
public class M {
    /** 두께는 180mm 이상이어야 한다. */
    public void check() {}
}
"""
        rules, _ = _extract(src)
        assert len(rules) == 1
        assert rules[0].severity is RuleSeverity.SOFT


# ---------------------------------------------------------------------------
# 메타데이터 (source, terms_ref, confirmed)
# ---------------------------------------------------------------------------
class TestMetadata:
    def test_source_records_target_fqn_and_javadoc_origin(self) -> None:
        src = """\
package com.x;
public class M {
    /** 두께는 240mm 이하여야 한다. */
    public void check() {}
}
"""
        rules, _ = _extract(src)
        # source 는 "javadoc:{target_fqn}" 형식 — 출처 추적 가능
        assert rules[0].source.startswith("javadoc:")
        assert "com.x.M.check" in rules[0].source

    def test_confirmed_default_false(self) -> None:
        src = """\
package com.x;
/** 두께는 240mm 이하여야 한다. */
public class M {}
"""
        rules, _ = _extract(src)
        assert rules[0].confirmed is False

    def test_terms_ref_is_empty_by_default(self) -> None:
        # term 매칭은 C3 TermResolver 영역. 추출기는 빈 list 만 둠.
        src = """\
package com.x;
/** 두께는 240mm 이하여야 한다. */
public class M {}
"""
        rules, _ = _extract(src)
        assert rules[0].terms_ref == []


# ---------------------------------------------------------------------------
# Slab 실증 — 진짜 sample-repos 파일을 그대로 파싱
# ---------------------------------------------------------------------------
class TestSlabSample:
    def setup_method(self) -> None:
        self.root = Path("sample-repos/slab-design-engine/src/main/java")

    def _extract(self, rel: str):
        path = self.root / rel
        if not path.exists():
            pytest.skip(f"slab sample missing: {rel}")
        return _extract(path.read_text(), str(path))

    def test_constraint_checker_class_javadoc_extracts_four_rules(self) -> None:
        rules, edges = self._extract(
            "com/ontong/slab/constraint/EquipmentConstraintChecker.java"
        )
        # class-level bullet list 4 개
        class_targets = [
            e for e in edges
            if e.target.endswith("EquipmentConstraintChecker")
        ]
        assert len(class_targets) >= 4
        statements = [r.statement for r in rules]
        # 4 룰 핵심 토큰 확인
        assert any("압연기" in s and "이하" in s for s in statements)
        assert any("가열로" in s and "이하" in s for s in statements)
        assert any("두께" in s and "이상" in s and "이하" in s for s in statements)
        assert any("크레인" in s and "초과" in s for s in statements)

    def test_constraint_checker_method_javadocs_emit_rules(self) -> None:
        rules, edges = self._extract(
            "com/ontong/slab/constraint/EquipmentConstraintChecker.java"
        )
        targets = {e.target for e in edges}
        # 적어도 하나의 check* method 가 VALIDATES target 이어야 함
        method_targets = {t for t in targets if ".check" in t and not t.endswith("Checker")}
        assert len(method_targets) >= 1

    def test_weight_maximizer_class_javadoc_objective_function(self) -> None:
        rules, edges = self._extract(
            "com/ontong/slab/optimizer/WeightMaximizer.java"
        )
        # 목적식 다수 줄이 있으니 최소 1 룰 이상은 추출되어야 함
        assert len(rules) >= 1
        # 클래스 또는 메서드 FQN target 모두 허용
        assert all(
            e.target.startswith("com.ontong.slab.optimizer.WeightMaximizer")
            for e in edges
        )

    def test_slab_volume_javadoc_skipped_or_extracted(self) -> None:
        # Slab.volumeM3 / weightKg 의 Javadoc 은 단순 설명에 가깝지만,
        # "체적 = ...", "중량 = ..." 등 등식 형태가 있어 룰로 잡힐 수도.
        # 구체 갯수보다는 "에러 없이 동작" 만 검증.
        rules, edges = self._extract("com/ontong/slab/domain/Slab.java")
        # rule 객체 개수와 엣지 개수가 일치
        assert len(rules) == len(edges)
        # 모든 엣지는 valid VALIDATES
        assert all(e.kind == RelationKinds.VALIDATES for e in edges)


# ---------------------------------------------------------------------------
# Class-level extractor (instance API)
# ---------------------------------------------------------------------------
class TestExtractorClassAPI:
    def test_extractor_class_has_extract_method(self) -> None:
        ext = JavadocRuleExtractor()
        assert callable(ext.extract)

    def test_extractor_returns_pydantic_business_rule(self) -> None:
        ext = JavadocRuleExtractor()
        src = """\
package com.x;
/** 두께는 240mm 이하여야 한다. */
public class M {}
"""
        parser = JavaParser()
        pr = parser.parse_file(Path("M.java"), src)
        rules, _ = ext.extract("M.java", src, pr)
        assert len(rules) == 1
        assert isinstance(rules[0], BusinessRule)
        # frozen 모델 확인 — 의도적 변조 차단
        with pytest.raises((TypeError, ValueError)):
            rules[0].statement = "다른값"  # type: ignore[misc]
