"""C2 e2e — Java sample (Order/StandardOrder/RushOrder/Trackable) → adapter → role classify → store."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_layer.adapter import adapt_parse_results
from backend.modeling.code_layer.callsite_analyzer import analyze_call_sites
from backend.modeling.code_layer.role_classifier import classify_roles
from backend.modeling.code_layer.schema import (
    CallAnalysisSource,
    CodeTypeKind,
    CodeTypeRole,
    MethodRole,
)
from backend.modeling.code_layer.store import CodeLayerStore


JAVA_SAMPLES = {
    "Trackable.java": """
package com.scm;
public interface Trackable {
    String getTrackingNo();
}
""",
    "Order.java": """
package com.scm;
public abstract class Order implements Trackable {
    protected String orderNo;
    public abstract ValidationResult validate();
    public String getOrderNo() { return orderNo; }
    @Override
    public String getTrackingNo() { return "T-" + orderNo; }
}
""",
    "StandardOrder.java": """
package com.scm;
public class StandardOrder extends Order {
    @Override
    public ValidationResult validate() {
        return ValidationResult.ok();
    }
}
""",
    "RushOrder.java": """
package com.scm;
public class RushOrder extends Order {
    private int priorityLevel;
    @Override
    public ValidationResult validate() {
        if (priorityLevel < 1) return ValidationResult.fail("우선도");
        return ValidationResult.ok();
    }
}
""",
}


@pytest.fixture
def java_repo(tmp_path):
    for name, src in JAVA_SAMPLES.items():
        (tmp_path / name).write_text(src.strip() + "\n")
    return tmp_path


@pytest.fixture
def fresh_db(monkeypatch):
    from backend.modeling.code_layer.orm import CodeTypeRow  # noqa: F401
    from backend.modeling.persistence.database import (
        Base, get_engine, reset_engine_for_tests,
    )
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("ONTONG_DB_PATH", path)
    reset_engine_for_tests()
    Base.metadata.create_all(bind=get_engine())
    yield path
    reset_engine_for_tests()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestE2E:
    def test_full_pipeline(self, java_repo, fresh_db):
        # 1. Parse
        parser = JavaParser()
        results = [parser.parse_file(fp, fp.read_text())
                   for fp in sorted(java_repo.glob("*.java"))]
        assert len(results) == 4

        # 2. Adapt
        types = adapt_parse_results(results, repo_id="sample")
        assert len(types) == 4

        # 3. Role classify
        types = classify_roles(types)
        order = next(t for t in types if t.simple_name == "Order")
        rush = next(t for t in types if t.simple_name == "RushOrder")
        trackable = next(t for t in types if t.simple_name == "Trackable")

        assert order.kind == CodeTypeKind.ABSTRACT_CLASS
        assert order.is_abstract is True
        assert order.role == CodeTypeRole.DOMAIN
        assert rush.extends == "com.scm.Order"
        assert rush.role == CodeTypeRole.DOMAIN
        assert trackable.kind == CodeTypeKind.INTERFACE
        assert trackable.is_abstract is True
        assert trackable.role == CodeTypeRole.DOMAIN

        # @Override 검출
        rush_validate = next(m for m in rush.methods if m.name == "validate")
        assert rush_validate.is_override is True
        assert rush_validate.role == MethodRole.BUSINESS

        # field 보존
        assert any(f.name == "priorityLevel" for f in rush.fields)

        # implements 보존
        assert "com.scm.Trackable" in order.implements

        # 4. Store
        store = CodeLayerStore()
        store.upsert_types(repo_id="sample", code_types=types)
        all_back = store.list_types(repo_id="sample")
        assert len(all_back) == 4

        # 5. CallSiteAnalyzer
        seeds = [
            ("com.scm.Service.run", "validate", "Order", 10),     # 모호 (StandardOrder + RushOrder)
            ("com.scm.Service.run", "getTrackingNo", "Trackable", 12),  # impl 1개 (Order) → 확정
            ("com.scm.Service.run", "getOrderNo", "Order", 14),   # override 없음 → 자체
        ]
        sites = analyze_call_sites(types, seeds=seeds, repo_id="sample")
        assert len(sites) == 3

        validate_site = next(s for s in sites if s.callee_simple_name == "validate")
        assert validate_site.analysis_source == CallAnalysisSource.STATIC_UNRESOLVED
        assert validate_site.needs_user_confirm is True
        assert len(validate_site.possible_runtime_types) >= 2  # 두 subtype 후보

        tracking_site = next(s for s in sites if s.callee_simple_name == "getTrackingNo")
        assert tracking_site.analysis_source == CallAnalysisSource.SINGLE_IMPL
        assert tracking_site.confidence == 1.0
        assert tracking_site.possible_runtime_types[0].code_type_fqn == "com.scm.Order"

        order_no_site = next(s for s in sites if s.callee_simple_name == "getOrderNo")
        assert order_no_site.analysis_source == CallAnalysisSource.SINGLE_IMPL
        assert order_no_site.confidence == 1.0

        # CallSite store roundtrip
        store.upsert_call_sites(repo_id="sample", call_sites=sites)
        ambig = store.list_ambiguous_call_sites(repo_id="sample")
        assert len(ambig) == 1
        assert ambig[0].callee_simple_name == "validate"
