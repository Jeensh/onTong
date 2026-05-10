"""artifact 디스크 저장 (spec 05 §6.2) 검증.

이전 (3c-C): in-memory dict 만
현재 (3d-E5): in-memory + 디스크 (`{artifact_root}/{run_id}/{kind}.{ext}`)

graceful — 디스크 write 실패 시 in-memory 유지. read 는 in-memory 우선 + 디스크 fallback.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ─── 1. store_artifact 가 디스크 파일 생성 ────────────────────────


def test_store_artifact_writes_to_disk(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    store.store_artifact("run-1", "generated_python", "def run(): pass\n")

    expected = tmp_path / "run-1" / "generated_python.py"
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == "def run(): pass\n"


def test_store_artifact_creates_run_directory(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    store.store_artifact("run-2", "trace", '{"frame": 1}\n{"frame": 2}\n')
    assert (tmp_path / "run-2").is_dir()
    assert (tmp_path / "run-2" / "trace.jsonl").exists()


def test_store_artifact_extension_per_kind(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    cases = [
        ("generated_python", "py"),
        ("jvm_log", "log"),
        ("trace", "jsonl"),
        ("input_fixture", "json"),
        ("output_dump", "json"),
    ]
    for kind, ext in cases:
        store.store_artifact("run-x", kind, "content")
        assert (tmp_path / "run-x" / f"{kind}.{ext}").exists()


# ─── 2. get_artifact — 디스크 fallback ────────────────────────────


def test_get_artifact_in_memory_first(tmp_path):
    """in-memory 가 있으면 디스크 fetch 안 함."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    store.store_artifact("run-1", "trace", "in-memory content")
    # 디스크는 in-memory 와 다른 값으로 직접 덮어씀
    (tmp_path / "run-1" / "trace.jsonl").write_text("disk content")

    assert store.get_artifact("run-1", "trace") == "in-memory content"


def test_get_artifact_disk_fallback_when_memory_empty(tmp_path):
    """in-memory 비었을 때 디스크에서 read."""
    from backend.simulation.api.run_handle import RunHandleStore

    # 디스크에 직접 파일 생성 (다른 process / 재시작 후 시뮬)
    run_dir = tmp_path / "run-recovered"
    run_dir.mkdir()
    (run_dir / "generated_python.py").write_text("def run(): return 'recovered'\n")

    store = RunHandleStore(artifact_root=tmp_path)
    # in-memory 에 없음 → 디스크 fallback
    content = store.get_artifact("run-recovered", "generated_python")
    assert content == "def run(): return 'recovered'\n"


def test_get_artifact_returns_none_when_neither_exists(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    assert store.get_artifact("run-missing", "trace") is None


# ─── 3. list_artifact_kinds 가 디스크 파일도 포함 ─────────────────


def test_list_artifact_kinds_includes_disk_files(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    # 디스크에만 있는 파일들
    run_dir = tmp_path / "run-disk-only"
    run_dir.mkdir()
    (run_dir / "trace.jsonl").write_text("...")
    (run_dir / "generated_python.py").write_text("...")

    store = RunHandleStore(artifact_root=tmp_path)
    kinds = store.list_artifact_kinds("run-disk-only")
    assert "trace" in kinds
    assert "generated_python" in kinds


def test_list_artifact_kinds_combines_memory_and_disk(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    # in-memory
    store.store_artifact("run-mix", "trace", "x")  # 디스크에도 저장됨
    # 디스크만 (다른 kind)
    (tmp_path / "run-mix" / "input_fixture.json").write_text('{"a": 1}')

    kinds = store.list_artifact_kinds("run-mix")
    assert "trace" in kinds
    assert "input_fixture" in kinds


# ─── 4. artifact_path — file path 반환 ────────────────────────────


def test_artifact_path_returns_existing_file(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    store.store_artifact("run-1", "generated_python", "x")

    p = store.artifact_path("run-1", "generated_python")
    assert p is not None
    assert p.exists()
    assert p.suffix == ".py"


def test_artifact_path_none_for_missing(tmp_path):
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore(artifact_root=tmp_path)
    assert store.artifact_path("run-missing", "trace") is None


# ─── 5. ONTONG_ARTIFACT_ROOT 환경변수 적용 ───────────────────────


def test_artifact_root_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_ARTIFACT_ROOT", str(tmp_path / "via_env"))
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()  # artifact_root 인자 없음 → env 사용
    store.store_artifact("r1", "trace", "via env")

    assert (tmp_path / "via_env" / "r1" / "trace.jsonl").exists()


# ─── 6. graceful — 디스크 write 실패해도 in-memory 동작 ──────────


def test_disk_write_failure_does_not_break_in_memory(tmp_path):
    """artifact_root 가 read-only 라도 in-memory 는 동작."""
    import os

    # tmp_path 를 read-only 로 (FAT 파일시스템 등)
    bad_root = tmp_path / "ro"
    bad_root.mkdir()
    os.chmod(bad_root, 0o444)
    try:
        from backend.simulation.api.run_handle import RunHandleStore

        store = RunHandleStore(artifact_root=bad_root)
        store.store_artifact("r", "trace", "memory-only")

        # in-memory 는 살아있음
        assert store.get_artifact("r", "trace") == "memory-only"
    finally:
        os.chmod(bad_root, 0o755)  # cleanup
