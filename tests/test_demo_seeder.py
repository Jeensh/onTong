"""Demo seeder + demo_api smoke tests.

Goal — verify
  - reset_demo_data wipes everything (incl. user-added terms/manuals).
  - is_demo_loaded heuristic returns False on cold start, True after load.
  - demo_api endpoints respond.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.modeling.api import demo_api
from backend.modeling.demo.seeder import (
    DEMO_REPO_ID,
    DEMO_TERM_FQNS,
    is_demo_loaded,
    reset_demo_data,
    seed_demo_data,
)
from backend.modeling.gap_detection.gap_store import InMemoryGapStore
from backend.modeling.gap_detection.rule_registry import (
    InMemoryRuleRegistry,
    seed_rules_from_repo,
)
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manual_ingest.pipeline import ManualIngestPipeline
from backend.modeling.manuals.manual_models import ManualFormat
from backend.modeling.mapping.business_term_registry import (
    InMemoryBusinessTermRegistry,
)
from backend.modeling.mapping.concept_store import InMemoryConceptBindingStore
from backend.modeling.mapping.mapping_models import (
    BusinessTerm,
    BusinessTermSource,
)


@pytest.fixture
def project_root() -> Path:
    """Real workspace root — the seeder reads sample-repos/ from here."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def make_pipeline():
    def _factory(registry: InMemoryManualRegistry) -> ManualIngestPipeline:
        return ManualIngestPipeline(
            parsers={ManualFormat.MARKDOWN: MarkdownParser()},
            registry=registry,
            graph_writer=None,
            embedding_store=None,
        )
    return _factory


def test_is_demo_loaded_false_on_cold_start():
    term_registry = InMemoryBusinessTermRegistry()
    assert is_demo_loaded(term_registry=term_registry) is False


def test_seed_demo_data_populates_terms_and_manuals(project_root, make_pipeline):
    manual_registry = InMemoryManualRegistry()
    pipeline = make_pipeline(manual_registry)
    rule_registry = InMemoryRuleRegistry()
    term_registry = InMemoryBusinessTermRegistry()

    # Pre-condition: empty
    assert len(manual_registry.list_all()) == 0
    assert len(list(term_registry.repos())) == 0

    result, bindings, embedder = seed_demo_data(
        project_root=project_root,
        manual_pipeline=pipeline,
        manual_registry=manual_registry,
        rule_registry=rule_registry,
        term_registry=term_registry,
    )

    # Post: 2 demo terms registered
    assert result.terms_added == 2
    assert is_demo_loaded(term_registry=term_registry) is True
    for fqn in DEMO_TERM_FQNS:
        assert term_registry.get(DEMO_REPO_ID, fqn) is not None

    # Manuals — sample-repos 가 실제 디스크에 있을 때만 가능. 없으면 0.
    if (project_root / "sample-repos/slab-design-real/toClaude/sd-tables.md").is_file():
        assert result.manuals_loaded >= 1
        assert len(manual_registry.list_all()) >= 1


def test_reset_demo_data_wipes_user_input(project_root, make_pipeline):
    """Reset should wipe everything — demo seeds + user-added terms."""
    manual_registry = InMemoryManualRegistry()
    pipeline = make_pipeline(manual_registry)
    rule_registry = InMemoryRuleRegistry()
    term_registry = InMemoryBusinessTermRegistry()
    binding_store = InMemoryConceptBindingStore()
    gap_store = InMemoryGapStore()

    # Add a user-created term that is NOT a demo term.
    term_registry.put("user-repo", BusinessTerm(
        qualified_name="term.사용자_커스텀",
        canonical_label="사용자 커스텀 용어",
        aliases=[],
        domain="custom",
        description="reset 후 사라져야 함",
        source=BusinessTermSource.MANUAL,
        confirmed=True,
        created_at=datetime.now(timezone.utc),
    ))

    result = reset_demo_data(
        manual_registry=manual_registry,
        term_registry=term_registry,
        binding_store=binding_store,
        gap_store=gap_store,
    )

    assert result.bindings_cleared is True
    # User term gone.
    assert term_registry.get("user-repo", "term.사용자_커스텀") is None
    assert is_demo_loaded(term_registry=term_registry) is False


def test_demo_api_status_load_reset_flow(project_root, make_pipeline):
    """End-to-end via FastAPI TestClient — status → load → status → reset → status."""
    from fastapi import FastAPI

    manual_registry = InMemoryManualRegistry()
    pipeline = make_pipeline(manual_registry)
    rule_registry = InMemoryRuleRegistry()
    term_registry = InMemoryBusinessTermRegistry()
    binding_store = InMemoryConceptBindingStore()
    gap_store = InMemoryGapStore()

    # Seed rules from the demo repo so auto-link has something to chew on.
    sample_repo = project_root / "sample-repos/slab-design-real"
    if sample_repo.is_dir():
        seed_rules_from_repo(sample_repo, DEMO_REPO_ID, rule_registry)

    demo_api.reset()  # clear any prior wiring
    demo_api.init(
        project_root=project_root,
        manual_pipeline=pipeline,
        manual_registry=manual_registry,
        rule_registry=rule_registry,
        term_registry=term_registry,
        binding_store=binding_store,
        gap_store=gap_store,
        post_change_hook=None,
    )

    app = FastAPI()
    app.include_router(demo_api.router)
    client = TestClient(app)

    # 1) Status — cold
    r = client.get("/api/modeling/demo/status")
    assert r.status_code == 200
    assert r.json()["loaded"] is False

    # 2) Load
    r = client.post("/api/modeling/demo/load")
    assert r.status_code == 200
    body = r.json()
    assert body["terms_added"] == 2

    # 3) Status — loaded
    r = client.get("/api/modeling/demo/status")
    assert r.json()["loaded"] is True
    assert r.json()["term_count"] >= 2

    # 4) Reset
    r = client.post("/api/modeling/demo/reset")
    assert r.status_code == 200
    assert r.json()["bindings_cleared"] is True

    # 5) Status — back to cold
    r = client.get("/api/modeling/demo/status")
    assert r.json()["loaded"] is False
    assert r.json()["term_count"] == 0
