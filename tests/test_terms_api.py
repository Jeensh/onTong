"""P2.5 — terms_api end-to-end test (시나리오 1 자동 매핑).

REST 흐름 :
  1. POST /api/modeling/terms — BusinessTerm 등록
  2. POST /api/modeling/terms/propose-bindings — 자동 후보 생성
  3. GET  /api/modeling/bindings?status=proposed — 후보 검토
  4. POST /api/modeling/bindings/{id}/confirm — 사용자 승인
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import terms_api
from backend.modeling.code_analysis.parser_protocol import CodeEntity, ParseResult
from backend.modeling.mapping.business_term_registry import (
    InMemoryBusinessTermRegistry,
)
from backend.modeling.mapping.concept_store import InMemoryConceptBindingStore
from backend.modeling.mapping.propose_bindings_service import (
    ProposeBindingsService,
)


def _class(fqn: str, table: str, java_field: str, col_name: str) -> CodeEntity:
    return CodeEntity(
        kind="class", qualified_name=fqn, name=fqn.split(".")[-1],
        file_path=f"{fqn}.java", line_start=1, line_end=10,
        attributes={
            "jpa_table": table,
            "jpa_columns_meta": {
                java_field: {"name": col_name, "name_lower": col_name.lower(),
                             "is_id": False, "length": 4},
            },
        },
    )


def _make_app(repo_id: str = "slab-design-real"):
    term_reg = InMemoryBusinessTermRegistry()
    store = InMemoryConceptBindingStore()
    svc = ProposeBindingsService(term_registry=term_reg, binding_store=store)

    # 시뮬레이션 — 6 PRODUCT_TYPE_CD 변종
    classes = [
        _class("com.x.OrderOmJpo", "order_om", "productTypeCd", "PRODUCT_TYPE_CD"),
        _class("com.x.CastSpecJpo", "cast_spec", "productTypeCd", "PRODUCT_TYPE_CD"),
        _class("com.x.HrSpecJpo", "hr_spec", "productTypeCd", "PRODUCT_TYPE_CD"),
        _class("com.x.EdgingGroupJpo", "edging_group", "productTypeCd", "PRODUCT_TYPE_CD"),
        _class("com.x.CustomerStdJpo", "customer_std", "productNameCd", "PRODUCT_NAME_CD"),
        _class("com.x.SdProductivityStdJpo", "sd_productivity_std", "prodKindCd", "PROD_KIND_CD"),
    ]
    prs = [ParseResult(entities=[c], relations=[], file_path=c.file_path, language="Java")
           for c in classes]

    terms_api.reset()
    terms_api.init(
        term_registry=term_reg, binding_store=store,
        propose_service=svc, repo_parse_results={repo_id: prs},
    )
    app = FastAPI()
    app.include_router(terms_api.router)
    return app, term_reg, store


# ---------------------------------------------------------------------------
# 503 if not initialized
# ---------------------------------------------------------------------------
def test_unconfigured_returns_503() -> None:
    terms_api.reset()
    app = FastAPI(); app.include_router(terms_api.router)
    client = TestClient(app)
    r = client.get("/api/modeling/terms?repo_id=x")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# 시나리오 1 풀 흐름
# ---------------------------------------------------------------------------
class TestScenario1Flow:
    def setup_method(self) -> None:
        self.app, _, _ = _make_app()
        self.client = TestClient(self.app)

    def test_step1_register_term(self) -> None:
        r = self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["품종", "품명", "product_type", "product_name", "prod_kind",
                        "product_type_cd", "product_name_cd", "prod_kind_cd"],
            "domain": "slab-design",
        })
        assert r.status_code == 200
        assert r.json()["canonical_label"] == "품종코드"

    def test_step2_list_terms(self) -> None:
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })
        r = self.client.get("/api/modeling/terms?repo_id=slab-design-real")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_step3_propose_bindings_finds_6(self) -> None:
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })
        r = self.client.post("/api/modeling/terms/propose-bindings",
                             json={"repo_id": "slab-design-real"})
        assert r.status_code == 200
        assert r.json()["total_proposed"] == 6

    def test_step4_list_proposed_bindings(self) -> None:
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })
        self.client.post("/api/modeling/terms/propose-bindings",
                         json={"repo_id": "slab-design-real"})
        r = self.client.get("/api/modeling/bindings?repo_id=slab-design-real&status=proposed")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 6
        # 모두 "품종코드" term 으로
        terms = {item["term_fqn"] for item in r.json()["items"]}
        assert terms == {"term.품종코드"}

    def test_step5_confirm_one_binding(self) -> None:
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })
        self.client.post("/api/modeling/terms/propose-bindings",
                         json={"repo_id": "slab-design-real"})
        list_r = self.client.get("/api/modeling/bindings?repo_id=slab-design-real")
        first_id = list_r.json()["items"][0]["id"]

        confirm_r = self.client.post(f"/api/modeling/bindings/{first_id}/confirm")
        assert confirm_r.status_code == 200
        assert confirm_r.json()["status"] == "confirmed"

        # confirmed 만 list
        only_confirmed = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real&status=confirmed"
        )
        assert len(only_confirmed.json()["items"]) == 1

    def test_step6_reject_one_binding(self) -> None:
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })
        self.client.post("/api/modeling/terms/propose-bindings",
                         json={"repo_id": "slab-design-real"})
        first_id = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real"
        ).json()["items"][0]["id"]
        r = self.client.post(f"/api/modeling/bindings/{first_id}/reject")
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# 에러 처리
# ---------------------------------------------------------------------------
class TestErrors:
    def setup_method(self) -> None:
        self.app, _, _ = _make_app()
        self.client = TestClient(self.app)

    def test_propose_unknown_repo_returns_404(self) -> None:
        r = self.client.post("/api/modeling/terms/propose-bindings",
                             json={"repo_id": "ghost-repo"})
        assert r.status_code == 404

    def test_confirm_unknown_proposal_returns_404(self) -> None:
        r = self.client.post("/api/modeling/bindings/missing/confirm")
        assert r.status_code == 404

    def test_reject_unknown_proposal_returns_404(self) -> None:
        r = self.client.post("/api/modeling/bindings/missing/reject")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Term 수정 / 삭제 (2026-04-26)
# ---------------------------------------------------------------------------
class TestUpdateTerm:
    def setup_method(self) -> None:
        self.app, _, _ = _make_app()
        self.client = TestClient(self.app)
        # 1 term 등록
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.강종코드",
            "canonical_label": "강종코드",
            "aliases": ["강종"],
            "domain": "slab-design",
            "description": "초기 등록",
        })

    def test_update_replaces_aliases_and_label(self) -> None:
        r = self.client.put(
            "/api/modeling/terms/slab-design-real/term.강종코드",
            json={
                "canonical_label": "강종 (수정)",
                "aliases": ["강종", "grade", "grade_cd"],
                "domain": "slab-design",
                "description": "수정됨",
            },
        )
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["canonical_label"] == "강종 (수정)"
        assert "grade_cd" in body["aliases"]
        assert body["description"] == "수정됨"

    def test_update_unknown_returns_404(self) -> None:
        r = self.client.put(
            "/api/modeling/terms/slab-design-real/term.없음",
            json={
                "canonical_label": "x",
                "aliases": [],
                "domain": "",
                "description": "",
            },
        )
        assert r.status_code == 404


class TestDeleteTerm:
    def setup_method(self) -> None:
        self.app, _, _ = _make_app()
        self.client = TestClient(self.app)
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.삭제대상",
            "canonical_label": "삭제대상",
            "aliases": ["product_type"],   # slab demo 와 매치되도록
            "domain": "slab-design",
            "description": "",
        })

    def test_delete_removes_term_and_proposals(self) -> None:
        # propose 실행 → proposal 다수 생성됐을 것
        self.client.post("/api/modeling/terms/propose-bindings",
                         json={"repo_id": "slab-design-real"})
        before = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real"
        ).json()["items"]
        before_for_term = [b for b in before if b["term_fqn"] == "term.삭제대상"]
        # 매칭이 1건 이상 있어야 의미 있는 테스트
        assert len(before_for_term) >= 1

        r = self.client.delete("/api/modeling/terms/slab-design-real/term.삭제대상")
        assert r.status_code == 200
        body = r.json()
        assert body["removed"] is True
        assert body["proposals_removed"] == len(before_for_term)

        # term 사라졌는지
        terms = self.client.get(
            "/api/modeling/terms?repo_id=slab-design-real"
        ).json()["items"]
        assert all(t["qualified_name"] != "term.삭제대상" for t in terms)

        # proposal 도 사라졌는지
        after = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real"
        ).json()["items"]
        assert all(b["term_fqn"] != "term.삭제대상" for b in after)

    def test_delete_unknown_returns_404(self) -> None:
        r = self.client.delete("/api/modeling/terms/slab-design-real/term.없음")
        assert r.status_code == 404


class TestProposeResultBreakdown:
    """Re-propose 응답이 new/refreshed/preserved 로 분리됨 (2026-04-26 회귀 방지)."""

    def setup_method(self) -> None:
        self.app, _, _ = _make_app()
        self.client = TestClient(self.app)
        # 매핑이 잡히도록 term 등록 (alias 가 PRODUCT_TYPE_CD 매치)
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })

    def test_first_propose_all_new_then_refresh(self) -> None:
        r1 = self.client.post("/api/modeling/terms/propose-bindings",
                              json={"repo_id": "slab-design-real"})
        assert r1.status_code == 200, r1.json()
        body1 = r1.json()
        assert body1["new"] >= 1
        assert body1["refreshed"] == 0
        assert body1["total_preserved"] == 0

        # 2nd propose 직후 (아무 confirm 없음) → 모두 refreshed
        r2 = self.client.post("/api/modeling/terms/propose-bindings",
                              json={"repo_id": "slab-design-real"})
        body2 = r2.json()
        assert body2["new"] == 0
        assert body2["refreshed"] == body1["new"]
        assert body2["total_preserved"] == 0

    def test_propose_after_confirm_preserves(self) -> None:
        self.client.post("/api/modeling/terms/propose-bindings",
                         json={"repo_id": "slab-design-real"})
        first = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real"
        ).json()["items"][0]
        self.client.post(f"/api/modeling/bindings/{first['id']}/confirm")

        r = self.client.post("/api/modeling/terms/propose-bindings",
                             json={"repo_id": "slab-design-real"})
        body = r.json()
        assert body["total_preserved"] >= 1

        # confirmed 상태가 살아있는지
        bindings = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real"
        ).json()["items"]
        kept = next(b for b in bindings if b["id"] == first["id"])
        assert kept["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Evidence endpoint (2026-04-26) — "왜 이 매칭?" 패널 데이터
# ---------------------------------------------------------------------------
class TestEvidenceEndpoint:
    def setup_method(self) -> None:
        self.app, _, _ = _make_app()
        self.client = TestClient(self.app)
        self.client.post("/api/modeling/terms", json={
            "repo_id": "slab-design-real",
            "qualified_name": "term.품종코드",
            "canonical_label": "품종코드",
            "aliases": ["product_type_cd", "product_name_cd", "prod_kind_cd"],
        })
        self.client.post("/api/modeling/terms/propose-bindings",
                         json={"repo_id": "slab-design-real"})

    def test_evidence_returns_bundle_fields(self) -> None:
        first_id = self.client.get(
            "/api/modeling/bindings?repo_id=slab-design-real"
        ).json()["items"][0]["id"]
        r = self.client.get(f"/api/modeling/bindings/{first_id}/evidence")
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["proposal_id"] == first_id
        assert body["term_fqn"] == "term.품종코드"
        # name-match 매칭이라 rationale 에 "이름 매칭" 포함
        assert "이름" in body["rationale"] or "alias" in body["rationale"]
        assert body["is_jpa_column"] is True
        assert body["enclosing_class_name"]  # 클래스명 채워짐
        assert isinstance(body["candidate_queries"], list)
        assert len(body["candidate_queries"]) >= 1
        assert "필드" in body["llm_prompt_context"]

    def test_evidence_unknown_returns_404(self) -> None:
        r = self.client.get("/api/modeling/bindings/missing/evidence")
        assert r.status_code == 404
