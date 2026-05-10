"""Phase 6-B — SQLite 영구 저장소 + 시나리오 라이브러리 + lineage 검증.

격리: pytest tmp_path 별 db 사용 (default db 미오염).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.simulation.sandbox import registry
from backend.simulation.storage import db as db_mod
from backend.simulation.storage import runs as runs_store
from backend.simulation.storage import scenarios as scn_store


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "sim_test.db"
    db_mod.init_schema(db_path)
    return db_path


# ─── Scenario CRUD ──────────────────────────────────────────────────


class TestScenarioCRUD:
    def test_upsert_and_list(self, temp_db: Path):
        s = scn_store.Scenario(
            id="", name="HR 0.92", step_id="pipeline_full",
            inputs={"rules": {"hr": "0.92"}},
            tags=["productivity", "rule-change"],
        )
        saved = scn_store.upsert_scenario(s, db_path=temp_db)
        assert saved.id.startswith("scn-")
        assert saved.created_at is not None

        items = scn_store.list_scenarios(db_path=temp_db)
        assert len(items) == 1
        assert items[0].name == "HR 0.92"

    def test_filter_by_step_id(self, temp_db: Path):
        scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="A", step_id="pipeline_full", inputs={}), db_path=temp_db)
        scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="B", step_id="thickness", inputs={}), db_path=temp_db)
        results = scn_store.list_scenarios(step_id="thickness", db_path=temp_db)
        assert len(results) == 1
        assert results[0].name == "B"

    def test_filter_by_tag(self, temp_db: Path):
        scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="A", step_id="pipeline_full",
            tags=["edging"], inputs={}), db_path=temp_db)
        scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="B", step_id="pipeline_full",
            tags=["productivity"], inputs={}), db_path=temp_db)
        results = scn_store.list_scenarios(tag="edging", db_path=temp_db)
        assert len(results) == 1
        assert results[0].name == "A"

    def test_update_preserves_created_at(self, temp_db: Path):
        s = scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="orig", step_id="thickness", inputs={}), db_path=temp_db)
        original_created = s.created_at
        s.name = "updated"
        s.created_at = original_created  # don't reset
        scn_store.upsert_scenario(s, db_path=temp_db)
        re = scn_store.get_scenario(s.id, db_path=temp_db)
        assert re.name == "updated"
        assert re.created_at == original_created

    def test_delete(self, temp_db: Path):
        s = scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="A", step_id="thickness", inputs={}), db_path=temp_db)
        assert scn_store.delete_scenario(s.id, db_path=temp_db) is True
        assert scn_store.get_scenario(s.id, db_path=temp_db) is None
        # 두 번째 삭제는 false
        assert scn_store.delete_scenario(s.id, db_path=temp_db) is False


# ─── YAML seed loading ──────────────────────────────────────────────


class TestSeedLoading:
    def test_load_default_seeds(self, temp_db: Path):
        n = scn_store.load_yaml_seeds(db_path=temp_db)
        assert n >= 5  # rule_changes.yaml has multiple
        items = scn_store.list_scenarios(db_path=temp_db)
        assert len(items) >= 5
        # source = 'yaml' 표시 확인
        assert all(s.source == "yaml" for s in items)

    def test_seed_idempotent(self, temp_db: Path):
        scn_store.load_yaml_seeds(db_path=temp_db)
        first_count = len(scn_store.list_scenarios(db_path=temp_db))
        scn_store.load_yaml_seeds(db_path=temp_db)  # 두 번 로드
        second_count = len(scn_store.list_scenarios(db_path=temp_db))
        assert first_count == second_count  # upsert → 중복 없음


# ─── Run logging + baseline ─────────────────────────────────────────


class TestRunLogging:
    def test_log_and_retrieve(self, temp_db: Path):
        outputs = registry.run_step("thickness", {"order": {}})
        run = runs_store.log_run(
            step_id="thickness", inputs={"order": {}}, outputs=outputs,
            elapsed_ms=12, db_path=temp_db,
        )
        assert run.id.startswith("run-")
        assert run.stage == "ok" or run.stage is None or "slab" in (outputs or {})

        fetched = runs_store.get_run(run.id, db_path=temp_db)
        assert fetched is not None
        assert fetched.outputs == outputs

    def test_list_filters(self, temp_db: Path):
        runs_store.log_run(step_id="thickness", inputs={}, outputs={}, db_path=temp_db)
        runs_store.log_run(step_id="validator", inputs={}, outputs={}, db_path=temp_db)
        all_runs = runs_store.list_runs(db_path=temp_db)
        assert len(all_runs) == 2
        only_thick = runs_store.list_runs(step_id="thickness", db_path=temp_db)
        assert len(only_thick) == 1

    def test_baseline_register(self, temp_db: Path):
        scn = scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="t", step_id="thickness", inputs={}), db_path=temp_db)
        run = runs_store.log_run(
            step_id="thickness", inputs={}, outputs={},
            scenario_id=scn.id, db_path=temp_db,
        )
        assert runs_store.register_baseline(run.id, scenario_id=scn.id, db_path=temp_db) is True
        baseline = runs_store.get_baseline(scn.id, db_path=temp_db)
        assert baseline is not None
        assert baseline.id == run.id
        assert baseline.is_baseline is True

    def test_baseline_replaces_previous(self, temp_db: Path):
        scn = scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="t", step_id="thickness", inputs={}), db_path=temp_db)
        r1 = runs_store.log_run(step_id="thickness", inputs={}, outputs={},
                                scenario_id=scn.id, db_path=temp_db)
        r2 = runs_store.log_run(step_id="thickness", inputs={}, outputs={},
                                scenario_id=scn.id, db_path=temp_db)
        runs_store.register_baseline(r1.id, scenario_id=scn.id, db_path=temp_db)
        runs_store.register_baseline(r2.id, scenario_id=scn.id, db_path=temp_db)
        # r1 의 baseline 해제, r2 만 baseline
        baselines = runs_store.list_runs(only_baseline=True, db_path=temp_db)
        assert len(baselines) == 1
        assert baselines[0].id == r2.id


# ─── Lineage ─────────────────────────────────────────────────────────


class TestLineage:
    def test_supersedes_chain(self, temp_db: Path):
        r1 = runs_store.log_run(step_id="thickness", inputs={}, outputs={},
                                db_path=temp_db)
        r2 = runs_store.log_run(step_id="thickness", inputs={}, outputs={},
                                parent_run_id=r1.id, db_path=temp_db)
        # r1 의 downstream 에 r2 가 있어야 함
        l1 = runs_store.get_lineage(r1.id, db_path=temp_db)
        assert any(d["run_id"] == r2.id and d["relation"] == "supersedes" for d in l1["downstream"])
        # r2 의 upstream 에 r1
        l2 = runs_store.get_lineage(r2.id, db_path=temp_db)
        assert any(u["run_id"] == r1.id for u in l2["upstream"])


# ─── Regression diff ────────────────────────────────────────────────


class TestRegressionDiff:
    def test_no_diff_when_outputs_equal(self, temp_db: Path):
        r1 = runs_store.log_run(step_id="thickness", inputs={},
                                outputs={"slab": {"slabThickness": "220"}}, db_path=temp_db)
        r2 = runs_store.log_run(step_id="thickness", inputs={},
                                outputs={"slab": {"slabThickness": "220"}}, db_path=temp_db)
        diff = runs_store.regression_diff(r1.id, r2.id, db_path=temp_db)
        assert diff["summary"]["diff_count"] == 0

    def test_thickness_change_detected(self, temp_db: Path):
        r1 = runs_store.log_run(step_id="thickness", inputs={},
                                outputs={"slab": {"slabThickness": "220"}}, db_path=temp_db)
        r2 = runs_store.log_run(step_id="thickness", inputs={},
                                outputs={"slab": {"slabThickness": "250"}}, db_path=temp_db)
        diff = runs_store.regression_diff(r1.id, r2.id, db_path=temp_db)
        assert diff["summary"]["diff_count"] == 1
        f = diff["summary"]["field_diffs"][0]
        assert f["path"] == "slab.slabThickness"
        assert f["before"] == "220"
        assert f["after"] == "250"

    def test_regression_creates_lineage(self, temp_db: Path):
        r1 = runs_store.log_run(step_id="t", inputs={}, outputs={"x": 1}, db_path=temp_db)
        r2 = runs_store.log_run(step_id="t", inputs={}, outputs={"x": 2}, db_path=temp_db)
        runs_store.regression_diff(r1.id, r2.id, db_path=temp_db)
        l1 = runs_store.get_lineage(r1.id, db_path=temp_db)
        assert any(d["run_id"] == r2.id and d["relation"] == "regression_of"
                   for d in l1["downstream"])


# ─── End-to-end: scenario → run → baseline → regression ─────────────


class TestE2EWorkflow:
    def test_seed_run_baseline_regression(self, temp_db: Path):
        # 1. seed 로딩
        scn_store.load_yaml_seeds(db_path=temp_db)

        # 2. baseline scenario 실행
        baseline_scn = scn_store.get_scenario("scn-thickness-A001", db_path=temp_db)
        assert baseline_scn is not None
        outputs = registry.run_step(baseline_scn.step_id, baseline_scn.inputs)
        baseline_run = runs_store.log_run(
            step_id=baseline_scn.step_id, inputs=baseline_scn.inputs,
            outputs=outputs, scenario_id=baseline_scn.id, db_path=temp_db,
        )
        runs_store.register_baseline(baseline_run.id, scenario_id=baseline_scn.id, db_path=temp_db)

        # 3. 변경된 inputs 로 candidate 실행
        modified_inputs = {"order": {"productTypeCd": "B002"}}
        cand_outputs = registry.run_step("thickness", modified_inputs)
        cand_run = runs_store.log_run(
            step_id="thickness", inputs=modified_inputs, outputs=cand_outputs,
            scenario_id=baseline_scn.id, parent_run_id=baseline_run.id, db_path=temp_db,
        )

        # 4. regression diff
        diff = runs_store.regression_diff(baseline_run.id, cand_run.id, db_path=temp_db)
        # B002 → 250mm vs A001 → 220mm
        assert diff["summary"]["diff_count"] >= 1
        thickness_diff = next(
            (f for f in diff["summary"]["field_diffs"] if f["path"].endswith("slabThickness")),
            None,
        )
        assert thickness_diff is not None
        assert thickness_diff["before"] == "220"
        assert thickness_diff["after"] == "250"

        # 5. lineage chain 확인 — baseline_run 다운스트림에 cand_run 두 관계 (supersedes + regression_of)
        l = runs_store.get_lineage(baseline_run.id, db_path=temp_db)
        relations = {d["relation"] for d in l["downstream"] if d["run_id"] == cand_run.id}
        assert "supersedes" in relations
        assert "regression_of" in relations
