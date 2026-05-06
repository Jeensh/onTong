"""Tests for backend/modeling/ontology/loader.py YAML I/O."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.modeling.ontology.loader import dump_ontology, load_ontology
from backend.modeling.ontology.schema import (
    Formula,
    IOPort,
    Ontology,
    OntologyHeader,
    Process,
    Rule,
    Term,
    ValueType,
)
from backend.modeling.ontology.validator import OntologyValidationError

SAMPLE_YAML = Path(__file__).resolve().parent.parent / "ontologies" / "safety_stock_v1.yaml"
SCOR_YAML = Path(__file__).resolve().parent.parent / "ontologies" / "scor_isa95_v1.yaml"

# OD-11 (2026-04-25) : `ontologies/` 디렉토리 폐기 — OD-7/8 "manual-first → YAML ontology"
# 접근 자체가 abandoned. 본 fixture 두 yaml 은 2026-04-25 cleanup 에서 제거.
# 본 모듈의 처음 두 테스트는 그 yaml 에 의존 → 영구 skip.
# 나머지 테스트 (round-trip / non-mapping reject / validate skip) 는 인라인 fixture 라 정상.
_DEPRECATED = pytest.mark.skip(
    reason="OD-7/8 era yaml templates removed in 2026-04-25 cleanup; OD-11 abandons ontology-first"
)


@_DEPRECATED
def test_load_sample_safety_stock_v1() -> None:
    """Sample ontology checked into the repo must validate."""
    ont = load_ontology(SAMPLE_YAML)
    assert ont.ontology.id == "safety-stock-v1"
    proc_ids = {p.id for p in ont.processes}
    assert "SafetyStockCalculation" in proc_ids
    assert "ReorderPointCalculation" in proc_ids
    assert ont.code_bindings["SafetyStockCalculation"].implementations


@_DEPRECATED
def test_load_scor_isa95_template() -> None:
    """SCOR + ISA-95 default template must validate and match legacy node counts."""
    ont = load_ontology(SCOR_YAML)
    assert ont.ontology.id == "scor-isa95-v1"
    assert len(ont.processes) == 26
    assert len(ont.entities) == 7
    assert len(ont.roles) == 5
    assert len(ont.relations) == 16
    kinds = {r.kind for r in ont.relations}
    assert kinds == {"uses", "produces", "responsible_for"}
    # SCOR Level 1
    top_level = [p for p in ont.processes if p.parent_id is None]
    assert {p.id for p in top_level} == {
        "SCOR/Plan", "SCOR/Source", "SCOR/Make", "SCOR/Deliver", "SCOR/Return",
    }


def test_roundtrip_dump_and_load(tmp_path: Path) -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="rt-test"),
        processes=[
            Process(
                id="P",
                name="P",
                inputs=[IOPort(id="a", name="A", type=ValueType.FLOAT)],
                outputs=[IOPort(id="b", name="B", type=ValueType.FLOAT)],
                formula=Formula(expression="a + 1"),
                rules=[Rule(id="R", condition="a > 0", action_type="warning", action_message="ok")],
            )
        ],
        terms=[Term(canonical="A", aliases=["a"], refers_to="P.inputs.a")],
    )
    path = tmp_path / "rt.yaml"
    dump_ontology(ont, path)
    reloaded = load_ontology(path)
    assert reloaded == ont


def test_load_rejects_non_mapping_root(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_ontology(path)


def test_load_validates_by_default(tmp_path: Path) -> None:
    # Build bad YAML: duplicate process ids.
    bad = {
        "ontology": {"id": "bad"},
        "processes": [
            {
                "id": "P",
                "name": "P",
                "inputs": [{"id": "a", "name": "A", "type": "float"}],
                "outputs": [{"id": "c", "name": "C", "type": "float"}],
            },
            {
                "id": "P",
                "name": "P",
                "inputs": [{"id": "a", "name": "A", "type": "float"}],
                "outputs": [{"id": "c", "name": "C", "type": "float"}],
            },
        ],
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")
    with pytest.raises(OntologyValidationError):
        load_ontology(path)


def test_load_skip_validation(tmp_path: Path) -> None:
    """validate=False allows loading structurally-correct-but-semantically-bad YAML."""
    bad = {
        "ontology": {"id": "bad"},
        "processes": [
            {
                "id": "P",
                "name": "P",
                "inputs": [{"id": "a", "name": "A", "type": "float"}],
                "outputs": [{"id": "c", "name": "C", "type": "float"}],
                "depends_on": ["GhostProcess"],
            }
        ],
    }
    path = tmp_path / "partial.yaml"
    path.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")
    ont = load_ontology(path, validate=False)
    assert ont.processes[0].depends_on == ["GhostProcess"]
