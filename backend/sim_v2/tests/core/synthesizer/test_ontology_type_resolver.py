"""OntologyTypeResolver — Section 2 Code Layer integration tests — W9.1."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.code_layer.orm import CodeFieldRow, CodeMethodRow, CodeTypeRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        CodeMethodRow.__table__,
    ])
    with Session(engine) as s:
        yield s


@pytest.fixture
def populated_session(session: Session):
    """Seed: SDSlabEntity + SDOrderEntity classes with BigDecimal getters/setters."""
    rows = [
        CodeTypeRow(
            fqn="com.example.slabdesign.SDSlabEntity",
            simple_name="SDSlabEntity",
            package="com.example.slabdesign",
            kind="CLASS",
            role="entity",
            repo_id="slab-design-v2",
        ),
        CodeTypeRow(
            fqn="com.example.slabdesign.SDOrderEntity",
            simple_name="SDOrderEntity",
            package="com.example.slabdesign",
            kind="CLASS",
            role="entity",
            repo_id="slab-design-v2",
        ),
        CodeMethodRow(
            fqn="com.example.slabdesign.SDSlabEntity#getSecondWgtHigh",
            name="getSecondWgtHigh",
            parent_type_fqn="com.example.slabdesign.SDSlabEntity",
            return_type="java.math.BigDecimal",
            repo_id="slab-design-v2",
        ),
        CodeMethodRow(
            fqn="com.example.slabdesign.SDOrderEntity#getOrderWgtHigh",
            name="getOrderWgtHigh",
            parent_type_fqn="com.example.slabdesign.SDOrderEntity",
            return_type="java.math.BigDecimal",
            repo_id="slab-design-v2",
        ),
        CodeMethodRow(
            fqn="com.example.slabdesign.SDOrderEntity#getProductivity",
            name="getProductivity",
            parent_type_fqn="com.example.slabdesign.SDOrderEntity",
            return_type="java.math.BigDecimal",
            repo_id="slab-design-v2",
        ),
        CodeMethodRow(
            fqn="com.example.slabdesign.SDSlabEntity#setMaxSplitCountUpper",
            name="setMaxSplitCountUpper",
            parent_type_fqn="com.example.slabdesign.SDSlabEntity",
            return_type="void",
            repo_id="slab-design-v2",
        ),
        CodeFieldRow(
            type_fqn="com.example.slabdesign.SDSlabEntity",
            name="secondWgtHigh",
            type="java.math.BigDecimal",
        ),
    ]
    session.add_all(rows)
    session.commit()
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Method return type
# ─────────────────────────────────────────────────────────────────────────────


def test_method_return_type_exact_fqn(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    result = r.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity",
        "getSecondWgtHigh",
    )
    assert result == "java.math.BigDecimal"


def test_method_return_type_simple_name_fallback(populated_session: Session):
    """Unqualified `SDSlabEntity` — should match via LIKE %.SDSlabEntity."""
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    result = r.resolve_method_return_type("SDSlabEntity", "getSecondWgtHigh")
    assert result == "java.math.BigDecimal"


def test_method_return_type_void(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    result = r.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity",
        "setMaxSplitCountUpper",
    )
    assert result == "void"


def test_method_unknown_class_returns_none(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    assert r.resolve_method_return_type("com.example.Unknown", "foo") is None


def test_method_unknown_method_returns_none(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    assert r.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity",
        "unknownMethod",
    ) is None


def test_method_wrong_repo_returns_none(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "other-repo")
    assert r.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity",
        "getSecondWgtHigh",
    ) is None


def test_method_none_receiver_returns_none(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    assert r.resolve_method_return_type(None, "getSecondWgtHigh") is None


def test_method_empty_method_name_returns_none(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    assert r.resolve_method_return_type("com.example.slabdesign.SDSlabEntity", "") is None


# ─────────────────────────────────────────────────────────────────────────────
# Field type
# ─────────────────────────────────────────────────────────────────────────────


def test_field_type_exact_fqn(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    result = r.resolve_field_type(
        "com.example.slabdesign.SDSlabEntity",
        "secondWgtHigh",
    )
    assert result == "java.math.BigDecimal"


def test_field_type_simple_name_fallback(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    result = r.resolve_field_type("SDSlabEntity", "secondWgtHigh")
    assert result == "java.math.BigDecimal"


def test_field_unknown_returns_none(populated_session: Session):
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    assert r.resolve_field_type(
        "com.example.slabdesign.SDSlabEntity",
        "unknownField",
    ) is None


# ─────────────────────────────────────────────────────────────────────────────
# Caching
# ─────────────────────────────────────────────────────────────────────────────


def test_method_cache_hits(populated_session: Session):
    """Second call must not re-query (cache hit). Verified by deleting row after first call."""
    r = OntologyTypeResolver(populated_session, "slab-design-v2")
    first = r.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity", "getSecondWgtHigh",
    )
    assert first == "java.math.BigDecimal"

    # Drop the row — would now return None from DB, but cache returns BigDecimal.
    populated_session.execute(
        CodeMethodRow.__table__.delete().where(
            CodeMethodRow.fqn == "com.example.slabdesign.SDSlabEntity#getSecondWgtHigh"
        )
    )
    populated_session.commit()

    second = r.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity", "getSecondWgtHigh",
    )
    assert second == "java.math.BigDecimal"  # served from cache


# ─────────────────────────────────────────────────────────────────────────────
# Composite — chain Ontology + BigDecimalAware
# ─────────────────────────────────────────────────────────────────────────────


def test_composite_ontology_plus_bigdecimal(populated_session: Session):
    """Composite of OntologyResolver + BigDecimalAware covers both v2 entities AND BigDecimal."""
    from backend.sim_v2.core.synthesizer.type_resolver import (
        BigDecimalAwareResolver,
        CompositeTypeResolver,
    )

    composite = CompositeTypeResolver([
        OntologyTypeResolver(populated_session, "slab-design-v2"),
        BigDecimalAwareResolver(),
    ])

    # Plugin-specific method
    assert composite.resolve_method_return_type(
        "com.example.slabdesign.SDSlabEntity", "getSecondWgtHigh",
    ) == "java.math.BigDecimal"

    # Std BigDecimal method
    assert composite.resolve_method_return_type(
        "java.math.BigDecimal", "add",
    ) == "java.math.BigDecimal"

    # BigDecimal's compareTo → int
    assert composite.resolve_method_return_type(
        "java.math.BigDecimal", "compareTo",
    ) == "int"
