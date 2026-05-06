"""OD-11-D2-3 : `POST /api/modeling/manuals/git-hook` 엔드포인트 검증.

JSON 바디 : `{repo_root, added: [...], modified: [...], removed: [...]}`
응답 : `{ingested: [...], skipped: [...], removed: [...], errors: [...]}`.

Uninitialized API 는 503.
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
from backend.modeling.manual_ingest.pipeline import ManualIngestPipeline
from backend.modeling.manuals.manual_models import ManualFormat


@pytest.fixture
def app_and_reg(tmp_path: Path):
    reset_manuals_api()
    reg = InMemoryManualRegistry()
    pipe = ManualIngestPipeline(
        parsers={ManualFormat.MARKDOWN: MarkdownParser()},
        registry=reg,
        graph_writer=None,
        embedding_store=None,
    )
    init_manuals_api(pipeline=pipe, registry=reg, repo_id="test-repo")
    app = FastAPI()
    app.include_router(manuals_router)
    yield app, reg, tmp_path
    reset_manuals_api()


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_git_hook_processes_added_files(app_and_reg) -> None:
    app, reg, tmp = app_and_reg
    client = TestClient(app)
    target = _write(tmp, "docs/a.md", "# A\n\nHello.\n")

    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={
            "repo_root": str(tmp),
            "added": [str(target)],
            "modified": [],
            "removed": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ingested"]) == 1
    assert data["ingested"][0]["outcome"] == "ingested"
    assert data["ingested"][0]["document"]["qualified_name"] == "manual.a"


def test_git_hook_modified_uses_update_mode(app_and_reg) -> None:
    app, _, tmp = app_and_reg
    client = TestClient(app)
    target = _write(tmp, "doc.md", "# Doc v1\n")

    # 1차
    client.post(
        "/api/modeling/manuals/git-hook",
        json={
            "repo_root": str(tmp),
            "added": [str(target)],
            "modified": [],
            "removed": [],
        },
    )

    # 파일 변경 후 modified 로 재통지
    target.write_text("# Doc v2\n\nChanged.\n", encoding="utf-8")
    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={
            "repo_root": str(tmp),
            "added": [],
            "modified": [str(target)],
            "removed": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ingested"]) == 1
    assert data["ingested"][0]["outcome"] == "updated"


def test_git_hook_unsupported_extension_goes_to_skipped(app_and_reg) -> None:
    app, _, tmp = app_and_reg
    client = TestClient(app)
    weird = _write(tmp, "note.txt", "plain")

    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={
            "repo_root": str(tmp),
            "added": [str(weird)],
            "modified": [],
            "removed": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested"] == []
    assert len(data["skipped"]) == 1


def test_git_hook_empty_payload_returns_empty_summary(app_and_reg) -> None:
    app, _, tmp = app_and_reg
    client = TestClient(app)
    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={"repo_root": str(tmp), "added": [], "modified": [], "removed": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"ingested": [], "skipped": [], "removed": [], "errors": []}


def test_git_hook_uninitialized_returns_503(tmp_path: Path) -> None:
    reset_manuals_api()
    app = FastAPI()
    app.include_router(manuals_router)
    client = TestClient(app)
    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={"repo_root": str(tmp_path), "added": [], "modified": [], "removed": []},
    )
    assert resp.status_code == 503


def test_git_hook_missing_repo_root_returns_400(app_and_reg) -> None:
    app, _, _ = app_and_reg
    client = TestClient(app)
    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={"added": ["a.md"]},
    )
    assert resp.status_code == 400


def test_git_hook_removed_files_in_response(app_and_reg) -> None:
    app, _, tmp = app_and_reg
    client = TestClient(app)
    resp = client.post(
        "/api/modeling/manuals/git-hook",
        json={
            "repo_root": str(tmp),
            "added": [],
            "modified": [],
            "removed": [str(tmp / "gone.md")],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["removed"]) == 1
    assert "gone.md" in data["removed"][0]
