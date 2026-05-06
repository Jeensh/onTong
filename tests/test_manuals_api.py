"""OD-11-D2-2 : Manuals REST + SSE API 검증.

- `POST /api/modeling/manuals/upload` (multipart) : 업로드 → 파서 → dedup → graph/embed → registry
- `GET  /api/modeling/manuals` : 등록된 Manual 목록
- `POST /api/modeling/manuals/<fqn>/authoritative` : Q8=B 수동 승급 토글
- `GET  /api/modeling/manuals/upload/stream` (SSE) : 업로드 진행률 이벤트

API 모듈은 `init(pipeline, registry)` 로 싱글턴 주입받는다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api.manuals_api import init as init_manuals_api
from backend.modeling.api.manuals_api import reset as reset_manuals_api
from backend.modeling.api.manuals_api import router as manuals_router
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manual_ingest.pdf_parser import PdfParser
from backend.modeling.manual_ingest.pipeline import ManualIngestPipeline
from backend.modeling.manuals.manual_models import ManualFormat


@pytest.fixture
def app_and_registry(tmp_path: Path):
    reset_manuals_api()
    reg = InMemoryManualRegistry()
    pipe = ManualIngestPipeline(
        parsers={
            ManualFormat.MARKDOWN: MarkdownParser(),
            ManualFormat.PDF: PdfParser(),
        },
        registry=reg,
        graph_writer=None,
        embedding_store=None,
    )
    init_manuals_api(pipeline=pipe, registry=reg, repo_id="test-repo")
    app = FastAPI()
    app.include_router(manuals_router)
    yield app, reg
    reset_manuals_api()


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------
def test_upload_markdown_succeeds(app_and_registry) -> None:
    app, reg = app_and_registry
    client = TestClient(app)
    body = b"# Spec\n\nBody.\n"
    resp = client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("spec.md", body, "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "ingested"
    assert data["document"]["qualified_name"].startswith("manual.")
    assert data["document"]["format"] == "markdown"


def test_upload_duplicate_checksum_returns_skipped(app_and_registry) -> None:
    app, reg = app_and_registry
    client = TestClient(app)
    body = b"# Same\n\nSame content.\n"
    first = client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("dup.md", body, "text/markdown")},
    )
    assert first.status_code == 200
    assert first.json()["outcome"] == "ingested"

    second = client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("dup.md", body, "text/markdown")},
    )
    assert second.status_code == 200
    assert second.json()["outcome"] == "skipped"


def test_upload_force_mode_ingests_twice(app_and_registry) -> None:
    app, reg = app_and_registry
    client = TestClient(app)
    body = b"# Force\n\nSame.\n"
    client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("f.md", body, "text/markdown")},
    )
    resp = client.post(
        "/api/modeling/manuals/upload?mode=force",
        files={"file": ("f.md", body, "text/markdown")},
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "ingested"


def test_upload_unsupported_extension_returns_415(app_and_registry) -> None:
    app, _ = app_and_registry
    client = TestClient(app)
    resp = client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("x.xyz", b"???", "application/octet-stream")},
    )
    assert resp.status_code == 415


# ---------------------------------------------------------------------------
# GET /manuals
# ---------------------------------------------------------------------------
def test_list_manuals_empty(app_and_registry) -> None:
    app, _ = app_and_registry
    client = TestClient(app)
    resp = client.get("/api/modeling/manuals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_manuals_returns_uploaded(app_and_registry) -> None:
    app, _ = app_and_registry
    client = TestClient(app)
    client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("a.md", b"# A\n", "text/markdown")},
    )
    client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("b.md", b"# B\n", "text/markdown")},
    )
    resp = client.get("/api/modeling/manuals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    fqns = {item["qualified_name"] for item in data["items"]}
    assert len(fqns) == 2


# ---------------------------------------------------------------------------
# POST /{fqn}/authoritative
# ---------------------------------------------------------------------------
def test_toggle_authoritative_true(app_and_registry) -> None:
    app, reg = app_and_registry
    client = TestClient(app)
    upload = client.post(
        "/api/modeling/manuals/upload",
        files={"file": ("auth.md", b"# Auth\n", "text/markdown")},
    )
    fqn = upload.json()["document"]["qualified_name"]

    resp = client.post(
        f"/api/modeling/manuals/{fqn}/authoritative",
        json={"authoritative": True},
    )
    assert resp.status_code == 200
    assert resp.json()["authoritative"] is True


def test_toggle_authoritative_missing_returns_404(app_and_registry) -> None:
    app, _ = app_and_registry
    client = TestClient(app)
    resp = client.post(
        "/api/modeling/manuals/manual.ghost/authoritative",
        json={"authoritative": True},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------
def test_upload_stream_emits_events(app_and_registry) -> None:
    app, _ = app_and_registry
    client = TestClient(app)
    body = b"# Stream\n\nBody.\n"
    with client.stream(
        "POST",
        "/api/modeling/manuals/upload/stream",
        files={"file": ("stream.md", body, "text/markdown")},
    ) as resp:
        assert resp.status_code == 200
        text = b"".join(resp.iter_bytes()).decode("utf-8")
    # 최소 3개 이벤트 (parsing, persisting, complete) 가 섞여있어야 함
    assert "event: parsing" in text
    assert "event: complete" in text


# ---------------------------------------------------------------------------
# Init / reset lifecycle
# ---------------------------------------------------------------------------
def test_uninitialized_api_returns_503(tmp_path: Path) -> None:
    reset_manuals_api()
    app = FastAPI()
    app.include_router(manuals_router)
    client = TestClient(app)
    resp = client.get("/api/modeling/manuals")
    assert resp.status_code == 503
