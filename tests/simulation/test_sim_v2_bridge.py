"""Sprint 1 — sim_v2 bridge 통합 테스트.

backend/section3/sim_v2_bridge.py 가 다음을 만족해야:
- open_sim_v2_session() — slab-v2-handoff.db 존재 시 Session, 없으면 None
- build_stubs(method_fqn, repo_id, python_source) — W74 build_stub_namespace 래퍼
- run_in_process(...) — W72 TwinInvariantRunner 래퍼. section3 case_result shape 호환

대상 production 메서드: action.scm.product.cumulative_productivity
  → code_method_fqn 로 매핑된 Java body 가 sandbox 에서 PASS 까지 도달해야 함.
"""
from __future__ import annotations

import pytest

# pytest collect 시점에 모듈이 없으면 ImportError → 명확한 실패 메시지
from backend.section3 import sim_v2_bridge as bridge


REPO_V2 = "slab-design-real-v2"
CUM_PROD_ACTION_FQN = "action.scm.product.cumulative_productivity"


# ─── 픽스처 ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sim_session():
    """slab-v2-handoff.db 가 없으면 module skip."""
    sess = bridge.open_sim_v2_session()
    if sess is None:
        pytest.skip("data/slab-v2-handoff.db 미존재 — sim_v2 통합 테스트 불가")
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture(scope="module")
def cum_prod_body(sim_session):
    """cumulativeProductivity action 의 Java body + method_fqn 로드.

    code_method_fqn 은 actions.description 에서 파싱되므로 production_domain_loader
    의 load_actions 를 사용한다.
    """
    from sqlalchemy import text

    from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
        load_actions,
    )

    actions = load_actions(sim_session, REPO_V2)
    target = next((a for a in actions if a.fqn == CUM_PROD_ACTION_FQN), None)
    if target is None or not target.code_method_fqn:
        pytest.skip("cumulative_productivity / code_method_fqn 누락")

    row = sim_session.execute(
        text(
            "SELECT body_text FROM code_methods "
            "WHERE fqn = :f AND repo_id = :r"
        ),
        {"f": target.code_method_fqn, "r": REPO_V2},
    ).fetchone()
    if not row or not row[0]:
        pytest.skip("code_methods.body_text 누락")
    return {"method_fqn": target.code_method_fqn, "body_text": row[0]}


@pytest.fixture(scope="module")
def cum_prod_python(cum_prod_body):
    """body_text → sim_v2 JavaToPythonTranslator (W75 idiom 자동 적용)."""
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser

    from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

    wrapped = f"public class C {{ {cum_prod_body['body_text']} }}"
    tree = Parser(Language(tsjava.language())).parse(wrapped.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body_n = next((x for x in c.children if x.type == "class_body"), None)
            if body_n is None:
                pytest.skip("class_body 파싱 실패")
            for m in body_n.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    if method is None:
        pytest.skip("method_declaration 파싱 실패")

    result = JavaToPythonTranslator().translate(method, indent=0)
    src = result.python_source
    first = src.splitlines()[0]
    assert first.startswith("def ")
    fn = first[4:].split("(", 1)[0].strip()
    return {"source": src, "function_name": fn}


# ─── 테스트 ──────────────────────────────────────────────────────────


def test_bridge_module_importable():
    """모듈이 import 되며 핵심 심볼이 노출되어야."""
    assert hasattr(bridge, "open_sim_v2_session")
    assert hasattr(bridge, "build_stubs")
    assert hasattr(bridge, "run_in_process")


def test_open_session_returns_session_or_none():
    """DB 가 있으면 Session, 없으면 None — 절대 raise 하지 말 것."""
    sess = bridge.open_sim_v2_session()
    # 환경에 따라 둘 다 valid
    if sess is not None:
        sess.close()


def test_build_stubs_for_cumulative_productivity(sim_session, cum_prod_body, cum_prod_python):
    """build_stubs 가 cumulativeProductivity 에 대해 stub 을 자동 derive 해야.

    UC40 실측: 23 stubs derive — 최소 1개는 나와야 회귀 아님.
    """
    stubs = bridge.build_stubs(
        sim_session,
        method_fqn=cum_prod_body["method_fqn"],
        repo_id=REPO_V2,
        python_source=cum_prod_python["source"],
    )
    assert isinstance(stubs, dict)
    assert len(stubs) >= 1, f"build_stubs 가 0 entry → W74 회귀: {stubs!r}"


def test_run_in_process_minimal_function():
    """stub 없는 단순 함수 — section3 case shape 으로 결과 반환."""
    src = "def add(a, b):\n    return a + b\n"
    cases = [
        {"case_id": "c1", "case_type": "boundary",
         "input": {"a": 1, "b": 2}, "expected_output": None},
        {"case_id": "c2", "case_type": "boundary",
         "input": {"a": 10, "b": 20}, "expected_output": None},
    ]
    results = bridge.run_in_process(
        python_source=src,
        function_name="add",
        param_names=["a", "b"],
        cases=cases,
        declared_return="int",
    )
    assert len(results) == 2
    for r in results:
        # section3 case_result shape 보존
        assert "case_id" in r
        assert "case_type" in r
        assert "input" in r
        assert "execution" in r
        assert "invariant_status" in r
        # 단순 add 는 PASS 여야
        assert r["invariant_status"] == "PASS", r
        assert r["execution"]["ok"] is True


def test_run_in_process_with_stub_namespace():
    """stub_namespace 가 함수 globals 에 주입되어야."""
    src = "def use_const():\n    return DEFAULT_VALUE\n"
    cases = [{"case_id": "c1", "case_type": "boundary", "input": {}, "expected_output": None}]
    results = bridge.run_in_process(
        python_source=src,
        function_name="use_const",
        param_names=[],
        cases=cases,
        stub_namespace={"DEFAULT_VALUE": 42},
        declared_return="int",
    )
    assert len(results) == 1
    assert results[0]["invariant_status"] == "PASS", results[0]


def test_run_in_process_failure_classification():
    """실패 시 invariant_status 가 FAIL_* 또는 ERROR 로 분류되어야."""
    src = "def boom(x):\n    raise RuntimeError('intentional')\n"
    cases = [{"case_id": "c1", "case_type": "boundary",
              "input": {"x": 1}, "expected_output": None}]
    # allowed_exceptions 가 비어 있으면 FAIL_UNEXPECTED_THROW
    results = bridge.run_in_process(
        python_source=src,
        function_name="boom",
        param_names=["x"],
        cases=cases,
        declared_return="void",
        allowed_exceptions=(),
    )
    assert len(results) == 1
    assert results[0]["invariant_status"] != "PASS"
    assert results[0]["execution"]["ok"] is False


# ─── Sprint 2 — baseline ─────────────────────────────────────────────


def test_load_baseline_map_missing_file_returns_empty(tmp_path, monkeypatch):
    """baseline 파일 없으면 빈 dict — 절대 raise 하지 말 것."""
    monkeypatch.chdir(tmp_path)
    result = bridge.load_baseline_map("does.not.exist(int)")
    assert result == {}


def test_load_baseline_map_reads_json(tmp_path, monkeypatch):
    """data/baselines/{safe_fqn}.json 을 읽어 dict[tuple, expected] 반환."""
    monkeypatch.chdir(tmp_path)
    fqn = "com.x.Foo.bar(int,String)"
    safe = fqn.replace(".", "_").replace("(", "_").replace(")", "_").replace(",", "_")
    bl_dir = tmp_path / "data" / "baselines"
    bl_dir.mkdir(parents=True)
    (bl_dir / f"{safe}.json").write_text(
        '[{"args": [1, "x"], "expected": 42}]', encoding="utf-8"
    )
    result = bridge.load_baseline_map(fqn)
    assert result == {(1, "x"): 42}


def test_run_fixtures_with_baseline_matches():
    """baseline 부착 → output_match=True 인 case 가 surface 되어야."""
    from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorFixture

    src = "def add(self, a, b):\n    return a + b\n"
    fixtures = [
        BehaviorFixture(
            fixture_id="add#0",
            python_source=src,
            function_name="add",
            input_args=(None, 1, 2),
            input_kwargs={},
            expected_output=None,
        ),
        BehaviorFixture(
            fixture_id="add#1",
            python_source=src,
            function_name="add",
            input_args=(None, 5, 5),
            input_kwargs={},
            expected_output=None,
        ),
    ]
    baseline = {(None, 1, 2): 3, (None, 5, 5): 10}
    results = bridge.run_fixtures_with_baseline(
        fixtures,
        function_name="add",
        baseline_map=baseline,
    )
    assert len(results) == 2
    for r in results:
        # baseline 부착되었으므로 expected/actual 모두 채워짐
        assert r["expected_value"] is not None
        assert r["actual_value"] is not None
        assert r["output_match"] is True
        assert r["invariant_status"] == "PASS"


def test_find_action_candidates_via_term(sim_session):
    """Sprint 4 — KoreanTermResolver hit 한 term 으로 actions.declared_on_term 매칭."""
    cands = bridge.find_action_candidates(
        sim_session, "주문 검증", REPO_V2, top_n=3,
    )
    assert len(cands) >= 1, "주문 검증 → '정합성_검증' 등 action 후보 surface 되어야"
    # 후보 dict 필수 키
    c0 = cands[0]
    for k in ("fqn", "label", "score", "matched_via"):
        assert k in c0


def test_find_action_candidates_via_like_match(sim_session):
    """Sprint 4 — KoreanTermResolver miss 시 LIKE 매치 fallback."""
    cands = bridge.find_action_candidates(
        sim_session, "productivity", REPO_V2, top_n=3,
    )
    fqns = [c["fqn"] for c in cands]
    assert "action.scm.product.cumulative_productivity" in fqns


def test_quick_diagnose_action_cumulative_productivity(sim_session):
    """Sprint 3 — quick_diagnose_action 가 W71→W74→W72 진단 요약을 반환."""
    actions = []
    try:
        from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
            load_actions,
        )
        actions = load_actions(sim_session, REPO_V2)
    except Exception:
        pytest.skip("load_actions 실패")
    target = next(
        (a for a in actions if a.fqn == "action.scm.product.cumulative_productivity"),
        None,
    )
    if target is None:
        pytest.skip("cumulative_productivity action 누락")
    diag = bridge.quick_diagnose_action(sim_session, target)
    assert "passing" in diag
    assert "fixtures" in diag
    assert "stubs" in diag
    assert diag["fixtures"] >= 1


def test_run_fixtures_with_baseline_mismatch():
    """expected ≠ actual 이면 output_match=False, status PASS 아님."""
    from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorFixture

    src = "def add(self, a, b):\n    return a + b\n"
    fixtures = [
        BehaviorFixture(
            fixture_id="add#0",
            python_source=src,
            function_name="add",
            input_args=(None, 1, 2),
            input_kwargs={},
            expected_output=None,
        ),
    ]
    baseline = {(None, 1, 2): 999}  # 실제는 3 인데 999 라고 주장
    results = bridge.run_fixtures_with_baseline(
        fixtures,
        function_name="add",
        baseline_map=baseline,
    )
    assert len(results) == 1
    assert results[0]["expected_value"] == 999
    assert results[0]["actual_value"] == 3
    assert results[0]["output_match"] is False
    assert results[0]["invariant_status"] != "PASS"
