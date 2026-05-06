"""POST /api/modeling/manuals/write — in-app markdown 에디터 저장 + 인제스트.

검증 :
    1. 정상 write → 디스크 .md 생성 + 매뉴얼 등록 + ontong directive 흡수.
    2. filename 검증 — 경로 traversal, 확장자 누락 등.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import manuals_api
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manual_ingest.pipeline import ManualIngestPipeline
from backend.modeling.manuals.manual_models import ManualFormat


@pytest.fixture
def wired_app(tmp_path, monkeypatch):
    """FastAPI app with manuals_api wired to a tmp data dir."""
    monkeypatch.chdir(tmp_path)
    registry = InMemoryManualRegistry()
    pipeline = ManualIngestPipeline(
        parsers={ManualFormat.MARKDOWN: MarkdownParser()},
        registry=registry,
        graph_writer=None,
        embedding_store=None,
    )
    manuals_api.reset()
    manuals_api.init(pipeline=pipeline, registry=registry, repo_id="test-repo")

    app = FastAPI()
    app.include_router(manuals_api.router)
    yield TestClient(app), tmp_path, registry
    manuals_api.reset()


def test_write_creates_file_and_ingests(wired_app):
    client, tmp_path, registry = wired_app
    body = {
        "filename": "demo.md",
        "content": "# Demo\n\n<!-- ontong: term=term.강종 -->\n강종은 4자리 코드.\n",
        "repo_id": "test-repo",
        "mode": "force",
    }
    r = client.post("/api/modeling/manuals/write", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["outcome"] in ("ingested", "updated")
    assert data["document"]["title"] == "Demo"
    saved = Path(data["saved_path"])
    assert saved.is_file()
    assert saved.read_text(encoding="utf-8").startswith("# Demo")
    # registry 에 등록됐나?
    assert any(d.title == "Demo" for d in registry.list_all())


def test_write_rejects_path_traversal(wired_app):
    client, *_ = wired_app
    bad = {"filename": "../escape.md", "content": "x", "repo_id": "test-repo"}
    r = client.post("/api/modeling/manuals/write", json=bad)
    assert r.status_code == 400


def test_write_rejects_slash_in_filename(wired_app):
    client, *_ = wired_app
    bad = {"filename": "subdir/file.md", "content": "x", "repo_id": "test-repo"}
    r = client.post("/api/modeling/manuals/write", json=bad)
    assert r.status_code == 400


def test_write_appends_md_extension_if_missing(wired_app):
    client, *_ = wired_app
    body = {"filename": "no_ext", "content": "# T\n", "repo_id": "test-repo"}
    r = client.post("/api/modeling/manuals/write", json=body)
    assert r.status_code == 200
    assert r.json()["saved_path"].endswith(".md")
