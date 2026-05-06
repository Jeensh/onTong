"""OD-11-D2-3 : ManualFolderWatcher 검증.

폴링 기반 폴더 감시자. `scan_once()` 호출 시 폴더를 순회하며 mtime+size 스냅샷과
비교해 신규/변경 파일을 `pipeline.ingest(mode=UPDATE)` 로 보낸다. 삭제 파일은
요약에만 포함 (D3 에서 DESCRIBED_IN 그래프 삭제 처리).

Spec : `toClaude/modeling/HANDOFF.md` D2-3 + `round3-manual-gap.html` rev.2 §6-2 트리거 3종.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manual_ingest.pipeline import (
    IngestMode,
    IngestOutcome,
    ManualIngestPipeline,
)
from backend.modeling.manual_ingest.watch_folder import (
    ManualFolderWatcher,
    WatchScanResult,
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


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------
def test_scan_once_ingests_new_file(tmp_path: Path) -> None:
    pipe, reg = _make_pipeline()
    _write(tmp_path / "a.md", "# A\n\nbody\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    result = watcher.scan_once()

    assert isinstance(result, WatchScanResult)
    assert len(result.ingested) == 1
    assert result.ingested[0].outcome == IngestOutcome.INGESTED
    assert len(reg.list_all()) == 1


def test_scan_once_without_changes_is_noop(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    _write(tmp_path / "a.md", "# A\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    watcher.scan_once()   # 초기
    result = watcher.scan_once()

    # 두 번째 스캔 : 변경 없음
    assert result.ingested == []
    assert result.skipped_unchanged >= 1


def test_scan_once_detects_modified_file_and_uses_update_mode(tmp_path: Path) -> None:
    pipe, reg = _make_pipeline()
    target = _write(tmp_path / "a.md", "# A\n\noriginal\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    first = watcher.scan_once()
    assert len(first.ingested) == 1

    # mtime 갱신을 확실히 하기 위해 살짝 대기
    time.sleep(0.01)
    target.write_text("# A\n\nUPDATED different body content\n", encoding="utf-8")

    second = watcher.scan_once()
    assert len(second.ingested) == 1
    assert second.ingested[0].outcome == IngestOutcome.UPDATED


def test_scan_once_recursive_subdirectories(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    _write(tmp_path / "a.md", "# A\n")
    _write(tmp_path / "sub" / "b.md", "# B\n")
    _write(tmp_path / "sub" / "deep" / "c.md", "# C\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    result = watcher.scan_once()

    assert len(result.ingested) == 3


# ---------------------------------------------------------------------------
# 필터링
# ---------------------------------------------------------------------------
def test_scan_once_skips_unsupported_extensions(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    _write(tmp_path / "a.md", "# A\n")
    _write(tmp_path / "note.txt", "plain text")   # 지원 안 됨
    _write(tmp_path / "script.py", "print('x')")  # 지원 안 됨

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    result = watcher.scan_once()

    assert len(result.ingested) == 1
    assert result.ingested[0].document.qualified_name == "manual.a"
    # 지원 안 되는 확장자는 무시되고 경고에 포함될 수 있음
    assert all("manual." in r.document.qualified_name for r in result.ingested)


def test_scan_once_handles_parser_error_and_records_warning(tmp_path: Path) -> None:
    """파서가 등록되지 않은 포맷은 warning 으로 집계, raise 하지 않는다."""
    reg = InMemoryManualRegistry()
    pipe = ManualIngestPipeline(
        parsers={},   # 파서 없음 → MD 파일도 UnsupportedFormatError
        registry=reg,
        graph_writer=None,
        embedding_store=None,
    )
    _write(tmp_path / "a.md", "# A\n")
    _write(tmp_path / "b.md", "# B\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    result = watcher.scan_once()

    assert result.ingested == []
    assert len(result.errors) == 2
    for err in result.errors:
        assert "a.md" in err or "b.md" in err


# ---------------------------------------------------------------------------
# Baseline seeding — 시작 시 이미 있는 파일은 "처음엔 무조건 ingest" 가 기본.
# 사용자가 seed_existing=False 로 생성하면 초기 파일 무시.
# ---------------------------------------------------------------------------
def test_seed_existing_false_skips_pre_existing_files(tmp_path: Path) -> None:
    pipe, reg = _make_pipeline()
    _write(tmp_path / "old.md", "# Old\n")

    watcher = ManualFolderWatcher(
        pipeline=pipe, folder=tmp_path, repo_id="r1", seed_existing=False,
    )
    result = watcher.scan_once()

    # 기존 파일은 무시 (baseline 에 포함)
    assert result.ingested == []
    assert len(reg.list_all()) == 0

    # 이후 새 파일은 picked up
    time.sleep(0.01)
    _write(tmp_path / "new.md", "# New\n")
    result2 = watcher.scan_once()
    assert len(result2.ingested) == 1


# ---------------------------------------------------------------------------
# 삭제 추적
# ---------------------------------------------------------------------------
def test_scan_once_tracks_removed_files(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    target = _write(tmp_path / "a.md", "# A\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    watcher.scan_once()

    target.unlink()
    result = watcher.scan_once()

    assert result.ingested == []
    assert len(result.removed) == 1
    assert result.removed[0].name == "a.md"


# ---------------------------------------------------------------------------
# 폴더 없을 때
# ---------------------------------------------------------------------------
def test_scan_once_missing_folder_returns_empty_result(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    watcher = ManualFolderWatcher(
        pipeline=pipe, folder=tmp_path / "does-not-exist", repo_id="r1",
    )
    result = watcher.scan_once()
    assert result.ingested == []
    assert result.removed == []
    assert result.errors == []


def test_watcher_rejects_file_path(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    target = _write(tmp_path / "not-a-folder.md", "# X\n")
    with pytest.raises(ValueError):
        ManualFolderWatcher(pipeline=pipe, folder=target, repo_id="r1")


# ---------------------------------------------------------------------------
# 여러 파일 batching
# ---------------------------------------------------------------------------
def test_scan_once_batches_multiple_new_files(tmp_path: Path) -> None:
    pipe, reg = _make_pipeline()
    for name in ["a.md", "b.md", "c.md"]:
        _write(tmp_path / name, f"# {name}\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    result = watcher.scan_once()

    assert len(result.ingested) == 3
    assert len(reg.list_all()) == 3


def test_second_scan_with_one_changed_file_only_ingests_that_one(tmp_path: Path) -> None:
    pipe, _ = _make_pipeline()
    a = _write(tmp_path / "a.md", "# A\n")
    _write(tmp_path / "b.md", "# B\n")

    watcher = ManualFolderWatcher(pipeline=pipe, folder=tmp_path, repo_id="r1")
    first = watcher.scan_once()
    assert len(first.ingested) == 2

    time.sleep(0.01)
    a.write_text("# A\n\nchanged content here\n", encoding="utf-8")

    second = watcher.scan_once()
    assert len(second.ingested) == 1
    assert second.ingested[0].outcome == IngestOutcome.UPDATED
