"""W4.1 smoke test — main.py 가 sim_v2 schema_layer 를 등록한 후 import 가능."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect

from backend.modeling.persistence.database import Base


def test_schema_layer_in_metadata():
    """schema_layer.orm import 후 8 table 이 Base.metadata 에 등록됨."""
    import backend.sim_v2.core.ontology.schema_layer.orm  # noqa: F401

    schema_tables = {
        name for name in Base.metadata.tables.keys() if name.startswith("schema_")
    }
    expected = {
        "schema_tables",
        "schema_columns",
        "schema_constraints",
        "schema_indexes",
        "schema_views",
        "schema_migrations",
        "schema_code_mappings",
        "schema_domain_mappings",
    }
    assert expected.issubset(schema_tables), f"missing: {expected - schema_tables}"


def test_create_all_picks_up_schema_layer():
    """create_all 이 in-memory engine 에 8 schema_* 테이블 생성."""
    import backend.sim_v2.core.ontology.schema_layer.orm  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    schema_tables = {t for t in tables if t.startswith("schema_")}
    assert len(schema_tables) == 8


def test_main_py_includes_schema_layer_import():
    """Regression: main.py 가 schema_layer.orm import 를 포함해야 함."""
    from pathlib import Path

    main_py = Path(__file__).resolve().parents[3] / "main.py"
    content = main_py.read_text(encoding="utf-8")
    assert "backend.sim_v2.core.ontology.schema_layer" in content, (
        "main.py must import sim_v2 schema_layer for bootstrap to pick up tables"
    )
