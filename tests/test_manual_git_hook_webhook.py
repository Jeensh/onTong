"""OD-11-D2-3 : git post-receive webhook 페이로드 처리 검증.

`parse_git_webhook_payload()` 은 일반화된 JSON 포맷
(`{repo_root, added: [...], modified: [...], removed: [...]}`) 을 받아
`GitHookRequest` 로 변환. `ingest_changed_files()` 는 added+modified 파일을
`pipeline.ingest(mode=UPDATE)` 로 전달하고, removed 는 요약에만 포함한다.
지원되지 않는 확장자는 `errors` 에 집계 (raise 없이 스킵).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.modeling.manual_ingest.git_hook_webhook import (
    GitHookRequest,
    GitHookResponse,
    ingest_changed_files,
    parse_git_webhook_payload,
)
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manual_ingest.pipeline import (
    IngestOutcome,
    ManualIngestPipeline,
)
from backend.modeling.manuals.manual_models import ManualFormat


def _make_pipeline() -> tuple[ManualIngestPipeline, InMemoryManualRegistry]:
    reg = InMemoryManualRegistry()
    pipe = ManualIngestPipeline(
        parsers={ManualFormat.MARKDOWN: MarkdownParser()},
        registry=reg,
        graph_writer=None,
        embedding_store=None,
    )
    return pipe, reg


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------
def test_parse_payload_basic(tmp_path: Path) -> None:
    payload = {
        "repo_root": str(tmp_path),
        "added": ["manuals/a.md"],
        "modified": ["manuals/b.md"],
        "removed": ["manuals/c.md"],
    }
    req = parse_git_webhook_payload(payload)
    assert isinstance(req, GitHookRequest)
    assert req.repo_root == Path(tmp_path).resolve()
    assert [p.name for p in req.added] == ["a.md"]
    assert [p.name for p in req.modified] == ["b.md"]
    assert [p.name for p in req.removed] == ["c.md"]


def test_parse_payload_missing_fields_default_empty(tmp_path: Path) -> None:
    payload = {"repo_root": str(tmp_path)}
    req = parse_git_webhook_payload(payload)
    assert req.added == []
    assert req.modified == []
    assert req.removed == []


def test_parse_payload_absolute_paths_preserved(tmp_path: Path) -> None:
    abs_path = str(tmp_path / "some.md")
    payload = {
        "repo_root": str(tmp_path),
        "added": [abs_path],
    }
    req = parse_git_webhook_payload(payload)
    assert req.added[0] == Path(abs_path).resolve()


def test_parse_payload_missing_repo_root_raises() -> None:
    with pytest.raises(ValueError):
        parse_git_webhook_payload({"added": ["a.md"]})


# ---------------------------------------------------------------------------
# Ingest flow
# ---------------------------------------------------------------------------
def test_ingest_changed_files_processes_added(tmp_path: Path) -> None:
    pipe, reg = _make_pipeline()
    target = tmp_path / "manuals" / "a.md"
    target.parent.mkdir(parents=True)
    target.write_text("# A\n", encoding="utf-8")

    req = GitHookRequest(
        repo_root=tmp_path.resolve(),
        added=[target.resolve()],
        modified=[],
        removed=[],
    )
    resp = ingest_changed_files(req, pipeline=pipe, repo_id="r1")

    assert isinstance(resp, GitHookResponse)
    assert len(resp.ingested) == 1
    assert resp.ingested[0].outcome == IngestOutcome.INGESTED
    assert len(reg.list_all()) == 1


def test_ingest_changed_files_uses_update_mode_for_modified(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    target = tmp_path / "doc.md"
    target.write_text("# Doc v1\n", encoding="utf-8")

    # 1차 ingest
    req1 = GitHookRequest(
        repo_root=tmp_path.resolve(),
        added=[target.resolve()],
        modified=[],
        removed=[],
    )
    ingest_changed_files(req1, pipeline=pipe, repo_id="r1")

    # 파일 변경 후 modified 로 재통지
    target.write_text("# Doc v2\n\nupdated body content here\n", encoding="utf-8")
    req2 = GitHookRequest(
        repo_root=tmp_path.resolve(),
        added=[],
        modified=[target.resolve()],
        removed=[],
    )
    resp = ingest_changed_files(req2, pipeline=pipe, repo_id="r1")

    assert len(resp.ingested) == 1
    assert resp.ingested[0].outcome == IngestOutcome.UPDATED


def test_ingest_changed_files_removed_collected_not_deleted(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    # removed 파일은 존재할 필요 없음 — git hook 은 삭제 알림 전용
    req = GitHookRequest(
        repo_root=tmp_path.resolve(),
        added=[],
        modified=[],
        removed=[tmp_path / "gone.md"],
    )
    resp = ingest_changed_files(req, pipeline=pipe, repo_id="r1")

    assert resp.ingested == []
    assert [p.name for p in resp.removed] == ["gone.md"]


def test_ingest_changed_files_unsupported_extension_skipped(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    a_md = tmp_path / "a.md"
    a_md.write_text("# A\n", encoding="utf-8")
    unsupported = tmp_path / "note.txt"
    unsupported.write_text("plain", encoding="utf-8")

    req = GitHookRequest(
        repo_root=tmp_path.resolve(),
        added=[a_md.resolve(), unsupported.resolve()],
        modified=[],
        removed=[],
    )
    resp = ingest_changed_files(req, pipeline=pipe, repo_id="r1")

    assert len(resp.ingested) == 1
    assert resp.ingested[0].document.qualified_name == "manual.a"
    assert len(resp.skipped) == 1
    assert resp.skipped[0].name == "note.txt"


def test_ingest_changed_files_empty_noop(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    req = GitHookRequest(
        repo_root=tmp_path.resolve(), added=[], modified=[], removed=[],
    )
    resp = ingest_changed_files(req, pipeline=pipe, repo_id="r1")
    assert resp.ingested == []
    assert resp.removed == []
    assert resp.skipped == []


def test_ingest_changed_files_missing_path_recorded_as_error(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    ghost = tmp_path / "ghost.md"   # 존재하지 않음

    req = GitHookRequest(
        repo_root=tmp_path.resolve(),
        added=[ghost],
        modified=[],
        removed=[],
    )
    resp = ingest_changed_files(req, pipeline=pipe, repo_id="r1")

    assert resp.ingested == []
    assert len(resp.errors) == 1
    assert "ghost.md" in resp.errors[0]


# ---------------------------------------------------------------------------
# Path escape 방어 : repo_root 밖 경로 거부
# ---------------------------------------------------------------------------
def test_ingest_changed_files_rejects_path_outside_repo_root(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    try:
        req = GitHookRequest(
            repo_root=tmp_path.resolve(),
            added=[outside.resolve()],
            modified=[],
            removed=[],
        )
        resp = ingest_changed_files(req, pipeline=pipe, repo_id="r1")
        assert resp.ingested == []
        assert len(resp.errors) == 1
        assert "outside" in resp.errors[0].lower() or "repo_root" in resp.errors[0].lower()
    finally:
        outside.unlink(missing_ok=True)
