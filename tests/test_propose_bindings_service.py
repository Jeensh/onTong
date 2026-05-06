"""P2.3 — ProposeBindingsService.

12-analyzer parse_results × BusinessTermRegistry → ConceptBindingProposal 후보 list.
TermResolver 4-stage chain 활용 (exact / alias / embedding / llm) — 시나리오 1 의
6 PRODUCT_TYPE_CD 변종이 모두 "품종코드" 로 매칭되어야 함.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.code_analysis.parser_protocol import CodeEntity, ParseResult
from backend.modeling.mapping.business_term_registry import (
    InMemoryBusinessTermRegistry,
)
from backend.modeling.mapping.concept_store import InMemoryConceptBindingStore
from backend.modeling.mapping.mapping_models import (
    BindingScope,
    BindingSource,
    BusinessTerm,
    BusinessTermSource,
    ProposalStatus,
)
from backend.modeling.mapping.propose_bindings_service import (
    ProposeBindingsService,
    ProposeBindingsResult,
)


def _term(
    fqn: str,
    canonical: str,
    aliases: list[str],
) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=fqn,
        canonical_label=canonical,
        aliases=aliases,
        domain="test",
        source=BusinessTermSource.MANUAL,
        created_at=datetime.now(timezone.utc),
    )


def _class_entity(fqn: str, name: str, jpa_columns_meta: dict) -> CodeEntity:
    return CodeEntity(
        kind="class",
        qualified_name=fqn,
        name=name,
        file_path=f"{name}.java",
        line_start=1,
        line_end=10,
        attributes={
            "jpa_table": name.lower(),
            "jpa_columns_meta": jpa_columns_meta,
        },
    )


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------
class TestBasicProposal:
    def setup_method(self) -> None:
        self.term_reg = InMemoryBusinessTermRegistry()
        self.store = InMemoryConceptBindingStore()
        self.service = ProposeBindingsService(
            term_registry=self.term_reg,
            binding_store=self.store,
        )

    def test_no_terms_returns_empty(self) -> None:
        cls = _class_entity("com.x.A", "A", {"f1": {"name_lower": "f1"}})
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")
        result = self.service.propose("repo", [pr])
        assert result.total_proposed == 0
        assert "no_terms" in (result.warnings or [])

    def test_no_jpa_classes_returns_empty(self) -> None:
        self.term_reg.put("repo", _term("term.x", "X", ["x"]))
        # Class without jpa_columns_meta
        cls = CodeEntity(
            kind="class", qualified_name="com.x.A", name="A",
            file_path="A.java", line_start=1, line_end=10,
        )
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")
        result = self.service.propose("repo", [pr])
        assert result.total_proposed == 0


# ---------------------------------------------------------------------------
# Alias 매칭 — column name 직접 vs 접미사 stripped
# ---------------------------------------------------------------------------
class TestAliasMatching:
    def test_exact_column_name_alias_match(self) -> None:
        term_reg = InMemoryBusinessTermRegistry()
        # alias 에 column name 그대로 (lowercase)
        term_reg.put("repo", _term(
            "term.품종코드", "품종코드",
            ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        ))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)

        cls = _class_entity("com.x.OrderOmJpo", "OrderOmJpo", {
            "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "is_id": False, "length": 4},
        })
        pr = ParseResult(entities=[cls], relations=[], file_path="OrderOmJpo.java", language="Java")
        result = service.propose("repo", [pr])
        assert result.total_proposed == 1
        proposals = list(store.list_proposals(repo_id="repo"))
        assert len(proposals) == 1
        assert proposals[0].binding.term_fqn == "term.품종코드"
        assert proposals[0].binding.code_fqn == "com.x.OrderOmJpo.productTypeCd"

    def test_suffix_stripped_alias_match(self) -> None:
        # alias 는 base "product_type" 만, column 은 "PRODUCT_TYPE_CD" — _cd 자동 strip
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term(
            "term.품종코드", "품종코드",
            ["product_type", "product_name", "prod_kind"],  # _cd 없음
        ))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)

        cls = _class_entity("com.x.A", "A", {
            "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "is_id": False},
        })
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")
        result = service.propose("repo", [pr])
        assert result.total_proposed == 1


# ---------------------------------------------------------------------------
# 시나리오 1 시뮬레이션 — 6 PRODUCT_TYPE_CD 변종 모두 매칭
# ---------------------------------------------------------------------------
class TestScenario1Simulation:
    def test_6_columns_all_match_품종코드(self) -> None:
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("slab", _term(
            "term.품종코드", "품종코드",
            # 사용자 답변 답변 그대로 + column name 변종 모두
            ["품종", "품명", "product_type", "product_name", "prod_kind",
             "product_type_cd", "product_name_cd", "prod_kind_cd"],
        ))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)

        # 6 변종 — 4 PRODUCT_TYPE_CD + 1 PRODUCT_NAME_CD + 1 PROD_KIND_CD
        classes = [
            _class_entity("com.x.OrderOm", "OrderOm", {
                "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "length": 4, "is_id": False},
            }),
            _class_entity("com.x.CastSpec", "CastSpec", {
                "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "length": 4, "is_id": True},
            }),
            _class_entity("com.x.HrSpec", "HrSpec", {
                "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "length": 4, "is_id": True},
            }),
            _class_entity("com.x.EdgingGroup", "EdgingGroup", {
                "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "length": 4, "is_id": False},
            }),
            _class_entity("com.x.CustomerStd", "CustomerStd", {
                "productNameCd": {"name": "PRODUCT_NAME_CD", "name_lower": "product_name_cd", "length": 3, "is_id": False},
            }),
            _class_entity("com.x.SdProductivityStd", "SdProductivityStd", {
                "prodKindCd": {"name": "PROD_KIND_CD", "name_lower": "prod_kind_cd", "length": 4, "is_id": True},
            }),
        ]
        prs = [
            ParseResult(entities=[c], relations=[], file_path=c.file_path, language="Java")
            for c in classes
        ]
        result = service.propose("slab", prs)
        # 6 컬럼 모두 매칭 → 6 proposals
        assert result.total_proposed == 6
        proposals = list(store.list_proposals(repo_id="slab"))
        assert len(proposals) == 6
        # 모두 같은 term_fqn
        terms = {p.binding.term_fqn for p in proposals}
        assert terms == {"term.품종코드"}
        # code_fqn 모두 다름
        codes = {p.binding.code_fqn for p in proposals}
        assert len(codes) == 6
        # 모두 PROPOSED 상태
        statuses = {p.status for p in proposals}
        assert statuses == {ProposalStatus.PROPOSED}


# ---------------------------------------------------------------------------
# Idempotent — 두 번 propose 해도 중복 X
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_re_propose_same_repo_no_duplicates(self) -> None:
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type"]))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)
        cls = _class_entity("com.x.A", "A", {
            "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "is_id": False},
        })
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")
        service.propose("repo", [pr])
        service.propose("repo", [pr])
        proposals = list(store.list_proposals(repo_id="repo"))
        assert len(proposals) == 1  # idempotent — 같은 (term, code) 면 단일 proposal

    def test_re_propose_preserves_user_decision(self) -> None:
        """사용자가 confirm/reject 한 매핑은 재 propose 시 보존돼야 함 (회귀 방지)."""
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type"]))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)
        cls = _class_entity("com.x.A", "A", {
            "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "is_id": False},
        })
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")

        # 1차 propose → 1 PROPOSED
        r1 = service.propose("repo", [pr])
        assert r1.new == 1 and r1.refreshed == 0 and r1.total_preserved == 0
        proposals = list(store.list_proposals(repo_id="repo"))
        assert len(proposals) == 1
        pid = proposals[0].id

        # 사용자 confirm
        store.confirm(pid, by="user")
        assert store.get_proposal(pid).status.value == "confirmed"

        # 2차 propose → 같은 매핑이지만 status 보존
        r2 = service.propose("repo", [pr])
        assert r2.new == 0
        assert r2.refreshed == 0
        assert r2.total_preserved == 1
        # 결정 그대로 — 이게 핵심
        kept = store.get_proposal(pid)
        assert kept.status.value == "confirmed"
        assert kept.decided_by == "user"

    def test_re_propose_refreshes_proposed_metadata(self) -> None:
        """결정 안 된 PROPOSED 는 binding meta (예: proposed_at) 가 갱신됨."""
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type"]))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)
        cls = _class_entity("com.x.A", "A", {
            "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "is_id": False},
        })
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")
        r1 = service.propose("repo", [pr])
        assert r1.new == 1
        r2 = service.propose("repo", [pr])
        assert r2.new == 0 and r2.refreshed == 1 and r2.total_preserved == 0


# ---------------------------------------------------------------------------
# Source / scope 분류
# ---------------------------------------------------------------------------
class TestSourceAndScope:
    def test_alias_match_records_source_correctly(self) -> None:
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type_cd"]))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)
        cls = _class_entity("com.x.A", "A", {
            "productTypeCd": {"name": "PRODUCT_TYPE_CD", "name_lower": "product_type_cd", "is_id": False},
        })
        pr = ParseResult(entities=[cls], relations=[], file_path="A.java", language="Java")
        service.propose("repo", [pr])
        proposals = list(store.list_proposals(repo_id="repo"))
        # Alias 매칭이므로 BindingSource.NAME_MATCH 또는 alias-equivalent
        assert proposals[0].binding.source in {
            BindingSource.NAME_MATCH, BindingSource.MANUAL
        }


# ---------------------------------------------------------------------------
# Slab 데모 실증 — 실제 entities.json 로
# ---------------------------------------------------------------------------
class TestSlabDemoEndToEnd:
    def test_real_demo_yields_at_least_6_품종코드_proposals(self) -> None:
        snap_path = Path("sample-repos/slab-design-real/.analyzed/entities.json")
        if not snap_path.exists():
            pytest.skip("Slab demo snapshot missing")
        import json
        snap = json.loads(snap_path.read_text())

        # snapshot → ParseResult list 재구성
        from dataclasses import replace as dataclass_replace
        prs = []
        for fp, fe in snap["files"].items():
            entities = []
            for e_dict in fe["entities"]:
                # CodeEntity 재구성 (kind=class only, others skipped — 우리는 class.attributes 만 봄)
                if e_dict["kind"] != "class":
                    continue
                entities.append(CodeEntity(
                    kind="class",
                    qualified_name=e_dict["qualified_name"],
                    name=e_dict["name"],
                    file_path=fp,
                    line_start=e_dict.get("line_start", 1),
                    line_end=e_dict.get("line_end", 1),
                    attributes=e_dict.get("attributes") or {},
                ))
            if entities:
                prs.append(ParseResult(
                    entities=entities, relations=[],
                    file_path=fp, language="Java",
                ))

        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("slab-design-real", _term(
            "term.품종코드", "품종코드",
            ["품종", "품명", "product_type", "product_name", "prod_kind",
             "product_type_cd", "product_name_cd", "prod_kind_cd"],
        ))
        term_reg.put("slab-design-real", _term(
            "term.열연공장코드", "열연공장코드",
            ["열연", "hr_plant", "hr_cd", "hr_plant_cd"],
        ))

        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)
        result = service.propose("slab-design-real", prs)

        # 시나리오 1: 6 PRODUCT_TYPE_CD 변종 모두 매칭
        품종_props = [
            p for p in store.list_proposals(repo_id="slab-design-real")
            if p.binding.term_fqn == "term.품종코드"
        ]
        assert len(품종_props) == 6, (
            f"Expected 6 품종코드 proposals; got {len(품종_props)}"
        )

        # 시나리오 2: 3 HR_PLANT_CD/HR_CD 매칭
        열연_props = [
            p for p in store.list_proposals(repo_id="slab-design-real")
            if p.binding.term_fqn == "term.열연공장코드"
        ]
        assert len(열연_props) == 3, (
            f"Expected 3 열연공장코드 proposals; got {len(열연_props)}"
        )


# ---------------------------------------------------------------------------
# P3.1 — all_fields 모드 + ContextBundler (2026-04-26)
# ---------------------------------------------------------------------------
class TestAllFieldsMode:
    """non-JPA FIELD entity 도 매칭 후보로 잡는지."""

    def test_non_jpa_field_picked_in_all_fields_mode(self) -> None:
        from backend.modeling.code_analysis.parser_protocol import EntityKinds
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type", "product_type_cd"]))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)

        # JPA 메타 없는 plain class + plain field
        cls = CodeEntity(
            kind=EntityKinds.CLASS, qualified_name="com.x.PlainCalc", name="PlainCalc",
            file_path="x.java", line_start=1, line_end=10, parent=None, attributes={},
        )
        fld = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.PlainCalc.productType",
            name="productType", file_path="x.java",
            line_start=2, line_end=2, parent="com.x.PlainCalc", attributes={"java_type": "String"},
        )
        pr = ParseResult(entities=[cls, fld], relations=[], file_path="x.java", language="Java")

        # jpa_only — 안 잡힘
        r1 = service.propose("repo", [pr], mode="jpa_only")
        assert r1.total_proposed == 0

        # all_fields — 잡힘 (PARTIAL scope)
        store2 = InMemoryConceptBindingStore()
        service2 = ProposeBindingsService(term_registry=term_reg, binding_store=store2)
        r2 = service2.propose("repo", [pr], mode="all_fields")
        assert r2.total_proposed == 1
        proposals = list(store2.list_proposals(repo_id="repo"))
        assert proposals[0].binding.scope.value == "partial"  # non-JPA 는 PARTIAL

    def test_opaque_field_count_reported(self) -> None:
        from backend.modeling.code_analysis.parser_protocol import EntityKinds
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type"]))
        store = InMemoryConceptBindingStore()
        service = ProposeBindingsService(term_registry=term_reg, binding_store=store)

        cls = CodeEntity(
            kind=EntityKinds.CLASS, qualified_name="com.x.HrCalc", name="HrCalc",
            file_path="x.java", line_start=1, line_end=10, parent=None, attributes={},
        )
        opaque = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.HrCalc.a1",
            name="a1", file_path="x.java",
            line_start=2, line_end=2, parent="com.x.HrCalc", attributes={},
        )
        meaningful = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.HrCalc.productType",
            name="productType", file_path="x.java",
            line_start=3, line_end=3, parent="com.x.HrCalc", attributes={},
        )
        pr = ParseResult(entities=[cls, opaque, meaningful], relations=[], file_path="x.java", language="Java")

        r = service.propose("repo", [pr], mode="all_fields")
        # opaque 1개 + meaningful 1개 → opaque 카운트 1
        assert r.total_opaque_inspected == 1
        # meaningful 1개만 매칭 (opaque 는 LLM 없이 못 잡음)
        assert r.total_proposed == 1


# ---------------------------------------------------------------------------
# P3.2 — LLM stage with bundle context (2026-04-26)
# ---------------------------------------------------------------------------
class _StubLLM:
    """LLMResolver 흉내 — 마지막 받은 query 기록 + 고정 답변."""
    def __init__(self, answer_for_opaque: str | None = None) -> None:
        self.answer_for_opaque = answer_for_opaque
        self.calls: list[str] = []
    def propose(self, query: str, available_terms):
        self.calls.append(query)
        if self.answer_for_opaque is None:
            return None
        from backend.modeling.query.term_resolver import LLMProposal
        return LLMProposal(
            term_fqn=self.answer_for_opaque, confidence=0.75,
            reasoning="stub",
        )


class TestLLMStageWithContext:
    """opaque 필드는 LLM stage 가 enriched query 로 호출돼야 함."""

    def test_meaningful_name_does_not_call_llm(self) -> None:
        from backend.modeling.code_analysis.parser_protocol import EntityKinds
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.x", "X", ["product_type", "product_type_cd"]))
        store = InMemoryConceptBindingStore()
        llm = _StubLLM()
        service = ProposeBindingsService(
            term_registry=term_reg, binding_store=store, llm_resolver=llm,
        )
        cls = CodeEntity(
            kind=EntityKinds.CLASS, qualified_name="com.x.A", name="A",
            file_path="x.java", line_start=1, line_end=10, parent=None, attributes={},
        )
        fld = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.A.productType",
            name="productType", file_path="x.java",
            line_start=2, line_end=2, parent="com.x.A", attributes={},
        )
        pr = ParseResult(entities=[cls, fld], relations=[], file_path="x.java", language="Java")
        service.propose("repo", [pr], mode="all_fields")
        # alias 매칭으로 잡혔어야 — LLM 호출 0
        assert llm.calls == []

    def test_opaque_field_calls_llm_with_enriched_context(self) -> None:
        from backend.modeling.code_analysis.parser_protocol import EntityKinds
        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("repo", _term("term.품종코드", "품종코드", ["product_type"]))
        store = InMemoryConceptBindingStore()
        llm = _StubLLM(answer_for_opaque="term.품종코드")
        service = ProposeBindingsService(
            term_registry=term_reg, binding_store=store, llm_resolver=llm,
        )
        cls = CodeEntity(
            kind=EntityKinds.CLASS,
            qualified_name="com.x.ProductTypeCalculator",
            name="ProductTypeCalculator",
            file_path="x.java", line_start=1, line_end=20, parent=None, attributes={},
        )
        opaque = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.ProductTypeCalculator.a1",
            name="a1", file_path="x.java",
            line_start=5, line_end=5, parent="com.x.ProductTypeCalculator", attributes={},
        )
        pr = ParseResult(entities=[cls, opaque], relations=[], file_path="x.java", language="Java")
        result = service.propose("repo", [pr], mode="all_fields")

        # name-based queries 시도 후 LLM enriched query 한 번 더 — 총 N+1 calls
        assert len(llm.calls) >= 1
        # enriched query 에 클래스명이 포함됐는지 (llm_prompt_context 출력)
        enriched_call = llm.calls[-1]
        assert "ProductTypeCalculator" in enriched_call

        # LLM 매칭 성공 → proposal 생성
        assert result.total_proposed == 1
        proposals = list(store.list_proposals(repo_id="repo"))
        assert len(proposals) == 1
        assert proposals[0].binding.term_fqn == "term.품종코드"
        # source = LLM
        assert proposals[0].binding.source.value == "llm"
        # scope = PARTIAL (비-JPA + LLM 매칭이므로)
        assert proposals[0].binding.scope.value == "partial"
