"""Schema Layer alembic migration test — B1.2 acceptance.

acceptance:
- alembic upgrade head 성공 (8 table 생성)
- alembic downgrade -1 성공 (8 table 삭제)
- 기존 4 layer 데이터 손실 0 (additive)

Strategy: in-memory sqlite engine 에 raw migration ops 적용 — alembic config 의존 X.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "migrations" / "versions"
V5_MIGRATION = MIGRATIONS_DIR / "2026_05_13_005_v5_schema_layer.py"


def _load_migration_module() -> Any:
    spec = importlib.util.spec_from_file_location("v5_schema_layer", V5_MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeOpBinding:
    """Minimal `alembic.op` substitute — only `execute` against bound engine."""

    def __init__(self, engine: Engine):
        self._engine = engine
        self._conn = engine.connect()

    def execute(self, sql: str) -> None:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(text(stmt))

    def get_bind(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()


@pytest.fixture
def engine_with_migration():
    engine = create_engine("sqlite:///:memory:")
    mod = _load_migration_module()
    fake_op = _FakeOpBinding(engine)

    # Patch alembic.op with our fake for the duration
    import alembic.op as real_op

    saved = (real_op.execute, real_op.get_bind)
    real_op.execute = fake_op.execute
    real_op.get_bind = fake_op.get_bind
    try:
        mod.upgrade()
        fake_op.close()
        yield engine, mod
    finally:
        real_op.execute = saved[0]
        real_op.get_bind = saved[1]
        engine.dispose()


def test_revision_chain():
    mod = _load_migration_module()
    assert mod.revision == "2026_05_13_005"
    assert mod.down_revision == "2026_05_06_004"


def test_upgrade_creates_eight_tables(engine_with_migration):
    engine, _ = engine_with_migration
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
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
    assert expected.issubset(tables), f"missing: {expected - tables}"


def test_schema_tables_columns(engine_with_migration):
    engine, _ = engine_with_migration
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("schema_tables")}
    assert columns == {"fqn", "table_name", "schema_name", "description", "source", "repo_id"}


def test_schema_columns_columns(engine_with_migration):
    engine, _ = engine_with_migration
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("schema_columns")}
    assert {"fqn", "table_fqn", "column_name", "data_type", "nullable", "position", "repo_id"}.issubset(cols)


def test_schema_migrations_unique_constraint(engine_with_migration):
    engine, _ = engine_with_migration
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO schema_migrations (system, version, sha256, applied_at, repo_id) "
            "VALUES ('banking', 'v1', 'abc', '2026-05-13T01:00:00Z', 'banking')"
        ))
        conn.commit()

        # Duplicate (system, version, repo_id) should fail
        with pytest.raises(Exception):
            conn.execute(text(
                "INSERT INTO schema_migrations (system, version, sha256, applied_at, repo_id) "
                "VALUES ('banking', 'v1', 'other-hash', '2026-05-13T02:00:00Z', 'banking')"
            ))
            conn.commit()


def test_schema_table_composite_pk_repo_id_isolation(engine_with_migration):
    engine, _ = engine_with_migration
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO schema_tables (fqn, table_name, repo_id) "
            "VALUES ('public.orders', 'orders', 'broadleaf')"
        ))
        conn.execute(text(
            "INSERT INTO schema_tables (fqn, table_name, repo_id) "
            "VALUES ('public.orders', 'orders', 'banking')"
        ))
        conn.commit()

        result = conn.execute(text(
            "SELECT repo_id FROM schema_tables WHERE fqn='public.orders' ORDER BY repo_id"
        )).fetchall()
        assert [row[0] for row in result] == ["banking", "broadleaf"]


def test_downgrade_drops_all_tables(engine_with_migration):
    engine, mod = engine_with_migration

    # Apply downgrade with our fake op
    fake_op = _FakeOpBinding(engine)
    import alembic.op as real_op

    saved_execute = real_op.execute
    real_op.execute = fake_op.execute
    try:
        mod.downgrade()
        fake_op.close()
    finally:
        real_op.execute = saved_execute

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    schema_tables = {t for t in tables if t.startswith("schema_")}
    assert schema_tables == set(), f"unexpected schema_* leftover: {schema_tables}"
