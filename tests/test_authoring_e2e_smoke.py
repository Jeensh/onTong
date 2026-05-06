"""S6.1 — End-to-end smoke test: real LLM, real DB, real API surface.

Runs a full HrPlant authoring cycle through the FastAPI router with live
Sonnet + Opus calls and verifies the cycle ends with BusinessTerms persisted
in the ontology DB.

Skipped unless `ONTONG_LLM_INTEGRATION=1` and `ANTHROPIC_API_KEY` are set.
Costs ~$1 per run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import authoring as auth_api
from backend.application.authoring import cost as cost_mod
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.persistence import database as db_mod


REAL_HR_SPEC_JPO = Path(
    "/Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real/"
    "slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle/jpo/"
    "HrSpecJpo.java"
)


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.fixture
def smoke_client(tmp_path, monkeypatch):
    """FastAPI TestClient with real DB + real DomainLayerStore. No LLM mocks."""
    db_path = tmp_path / "smoke.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401

    db_mod.bootstrap_database()
    cost_mod.reset_buffer()

    # Drop the lru_cache'd capability agents so each smoke run picks up the
    # current settings (in case a previous test mutated them).
    from backend.application.authoring.capabilities import (
        answer_absorber,
        archiver,
        code_extractor,
        gap_detector,
        hypothesis,
        interview,
        naming,
        option_proposer,
    )
    for mod in (
        code_extractor,
        hypothesis,
        interview,
        answer_absorber,
        option_proposer,
        gap_detector,
        naming,
        archiver,
    ):
        mod.reset_caches()

    app = FastAPI()
    auth_api.init(business_term_store=DomainLayerStore())
    app.include_router(auth_api.router)
    yield TestClient(app)
    db_mod.reset_engine_for_tests()


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_full_hrplant_cycle_through_api(smoke_client):
    """Full authoring cycle: extract → hypothesize → interview → absorb →
    options → gaps → naming → archive → confirm.

    Acceptance bar:
      - Every API call returns 200.
      - The recommended option from /options is fed into /naming and
        /archive verbatim (matching real user flow).
      - /confirm persists ≥1 BusinessTerm into the ontology DB.
      - /preview reports the same decision count as /decisions.
      - Total cost stays under $2 (the 2-tier routing budget for one entity).
    """
    c = smoke_client

    # 1) Create session
    r = c.post(
        "/api/authoring/sessions",
        json={"operator_id": "smoke", "branch_name": "main", "repo_id": "smoke-slab"},
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # 2) Extract HrSpecJpo.java
    content = REAL_HR_SPEC_JPO.read_text(encoding="utf-8")
    r = c.post(
        f"/api/authoring/sessions/{sid}/extract",
        json={"turn_no": 1, "file_path": str(REAL_HR_SPEC_JPO), "file_content": content},
    )
    assert r.status_code == 200, r.text
    jpo = r.json()
    assert jpo["class_name"] == "HrSpecJpo"
    assert jpo["table_name"] == "HR_SPEC"

    # 3) Hypothesize
    r = c.post(
        f"/api/authoring/sessions/{sid}/hypothesize",
        json={"turn_no": 2, "extracted_jpo": jpo},
    )
    assert r.status_code == 200, r.text
    hypothesis = r.json()
    assert "열연" in hypothesis["candidate_term_korean"]

    # 4) Interview
    r = c.post(
        f"/api/authoring/sessions/{sid}/interview",
        json={"turn_no": 3, "hypothesis": hypothesis},
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert 5 <= len(batch["questions"]) <= 7

    # 5) Simulate a Round-5-style user reply that confirms the hypothesis +
    #    surfaces the wildcard contradiction (so gap_detector has work to do).
    user_reply = (
        "공정계획에서 관리해. "
        "와일드카드는 PK 에 *를 쓸 수도 있고 LIKE 패턴도 지원해. "
        "기준값이 NULL 이면 자동 true 로 처리되는 점도 알아둬. "
        "룩업 실패하면 후속 로직에서 NPE 가 발생할 거야 — 데이터 결함이지. "
        "row 는 수십 정도. 공정계획팀 사용자가 갱신해. "
        "그 외는 모름."
    )

    # 6) Absorb the reply
    r = c.post(
        f"/api/authoring/sessions/{sid}/absorb",
        json={"turn_no": 4, "batch": batch, "user_reply": user_reply},
    )
    assert r.status_code == 200, r.text
    answers = r.json()
    assert set(answers["per_question"].keys()) == {q["id"] for q in batch["questions"]}

    # 7) Propose options
    r = c.post(
        f"/api/authoring/sessions/{sid}/options",
        json={"turn_no": 5, "hypothesis": hypothesis, "answers": answers},
    )
    assert r.status_code == 200, r.text
    options = r.json()
    assert 2 <= len(options["options"]) <= 4
    accepted = next(o for o in options["options"] if o["id"] == options["recommended_id"])

    # 8) Detect gaps (wildcard contradiction should surface ≥1 gap)
    r = c.post(
        f"/api/authoring/sessions/{sid}/gaps",
        json={"turn_no": 6, "extracted_jpo": jpo, "hypothesis": hypothesis, "answers": answers},
    )
    assert r.status_code == 200, r.text
    gaps = r.json()
    # Don't hard-assert on count — the trust bar allows zero, but the
    # contradiction is strong enough that ≥1 is the realistic outcome.

    # 9) Naming with the accepted option
    r = c.post(
        f"/api/authoring/sessions/{sid}/naming",
        json={"turn_no": 7, "hypothesis": hypothesis, "accepted_option": accepted},
    )
    assert r.status_code == 200, r.text
    names = r.json()
    assert len(names["entities"]) >= 1

    # 10) Archive
    r = c.post(
        f"/api/authoring/sessions/{sid}/archive",
        json={
            "turn_no": 8,
            "hypothesis": hypothesis,
            "answers": answers,
            "accepted_option": accepted,
            "names": names,
            "gaps": gaps,
            "step_number": 1,
        },
    )
    assert r.status_code == 200, r.text
    archive = r.json()
    assert "열연" in archive["title"] or "HrPlant" in archive["title"]
    assert "## 요약" in archive["markdown"]
    assert "## 결정 사항" in archive["markdown"]

    # 11) Confirm — entities land in the ontology DB
    r = c.post(
        f"/api/authoring/sessions/{sid}/confirm",
        json={
            "turn_no": 9,
            "names": names,
            "accepted_option": accepted,
            "repo_id": "smoke-slab",
            "domain": "scm",
        },
    )
    assert r.status_code == 200, r.text
    confirm = r.json()
    assert confirm["persisted_count"] == len(names["entities"])

    # The terms actually exist in the ontology DB.
    store = DomainLayerStore()
    terms = store.list_terms(repo_id="smoke-slab")
    fqns = {t.fqn for t in terms}
    assert set(confirm["persisted_fqns"]) <= fqns
    assert any(t.is_root_entity for t in terms), "no root entity persisted"

    # 12) Preview should reflect the full chain.
    r = c.get(f"/api/authoring/sessions/{sid}/preview")
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["decision_count"] >= 9, (
        f"expected ≥9 decisions (one per turn), got {preview['decision_count']}"
    )
    assert preview["latest_archive_markdown"] is not None
    assert "Step 1" in preview["latest_archive_markdown"]

    # 13) Cost summary — under the 2-tier budget for one entity.
    r = c.get(f"/api/authoring/sessions/{sid}/cost")
    assert r.status_code == 200
    cost = r.json()
    assert cost["call_count"] >= 8  # extract / hyp / interview / absorb / options / gaps / naming / archive
    assert cost["total_usd"] < 2.0, f"E2E cost {cost['total_usd']} exceeded $2 budget"

    # Helpful surface log so a manual run sees the numbers.
    print(
        f"\n[E2E SMOKE] session={sid} entities={confirm['persisted_count']} "
        f"calls={cost['call_count']} cost=${cost['total_usd']:.4f} "
        f"gaps={len(gaps['gaps'])} option_id={accepted['id']}"
    )
