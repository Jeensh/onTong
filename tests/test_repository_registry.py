"""RepositoryRegistry tests — register / list / get / unregister + disk cache + auto_discover.

Slab repo 사용 시 tmp_path 로 사본 복사 후 register — sample-repos 의 디스크 캐시
오염 방지 (실제 backend 가 사용하는 .analyzed/repo-meta.json 보호).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.code_analysis.repository_registry import (
    InMemoryRepositoryRegistry,
    RepositoryEntry,
    RepositoryRegistry,
    auto_discover_from_disk,
)


SLAB_REPO = Path("sample-repos/slab-design-real")


def _slab_or_skip(tmp_path: Path | None = None) -> Path:
    """Return Slab repo path. If tmp_path given, copy to isolated dir to avoid
    polluting `sample-repos/.../.analyzed/`."""
    if not SLAB_REPO.is_dir():
        pytest.skip("Slab demo missing")
    if tmp_path is None:
        return SLAB_REPO
    dst = tmp_path / "slab-design-real"
    # 빠른 사본 — .analyzed/ 디렉토리는 제외 (테스트가 새로 생성)
    shutil.copytree(
        SLAB_REPO, dst,
        ignore=shutil.ignore_patterns(".analyzed", "target"),
    )
    return dst


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_in_memory_conforms_to_protocol() -> None:
    assert isinstance(InMemoryRepositoryRegistry(), RepositoryRegistry)


# ---------------------------------------------------------------------------
# register / list / get / unregister
# ---------------------------------------------------------------------------
class TestBasicCrud:
    def test_register_returns_entry_with_correct_meta(self, tmp_path: Path) -> None:
        repo = _slab_or_skip(tmp_path)
        reg = InMemoryRepositoryRegistry()
        entry = reg.register("slab-design-real", repo)
        assert entry.repo_id == "slab-design-real"
        assert entry.path == str(repo.resolve())
        assert entry.files >= 100  # 122 currently
        assert entry.entities >= 1700
        assert entry.relations >= 3000
        assert entry.errors == []  # 0 errors expected
        assert isinstance(entry.registered_at, datetime)
        assert len(entry.parse_results) == entry.files

    def test_get_returns_entry(self, tmp_path: Path) -> None:
        repo = _slab_or_skip(tmp_path)
        reg = InMemoryRepositoryRegistry()
        reg.register("slab-design-real", repo)
        assert reg.get("slab-design-real") is not None
        assert reg.get("ghost") is None

    def test_list_returns_all_entries(self, tmp_path: Path) -> None:
        repo = _slab_or_skip(tmp_path)
        reg = InMemoryRepositoryRegistry()
        reg.register("slab-design-real", repo)
        # 두 번째 등록은 임시 빈 디렉토리
        empty = tmp_path / "empty-java"
        empty.mkdir()
        reg.register("empty", empty)
        listed = reg.list()
        assert {e.repo_id for e in listed} == {"slab-design-real", "empty"}

    def test_unregister_removes(self, tmp_path: Path) -> None:
        repo = _slab_or_skip(tmp_path)
        reg = InMemoryRepositoryRegistry()
        reg.register("slab-design-real", repo)
        assert reg.unregister("slab-design-real") is True
        assert reg.get("slab-design-real") is None
        assert reg.unregister("ghost") is False  # no-op when missing

    def test_register_invalid_path_raises(self, tmp_path: Path) -> None:
        reg = InMemoryRepositoryRegistry()
        with pytest.raises(ValueError):
            reg.register("bad", tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# JPA 메타 cross-file enrich (리저전 보장 — propose-bindings 입력)
# ---------------------------------------------------------------------------
class TestJpaEnrichment:
    def test_jpa_columns_meta_present_on_jpo_class(self, tmp_path: Path) -> None:
        repo = _slab_or_skip(tmp_path)
        reg = InMemoryRepositoryRegistry()
        entry = reg.register("slab-test", repo)
        # HrSpecJpo 의 productTypeCd length=4 가 있어야 propose-bindings 가 동작
        found = False
        for pr in entry.parse_results:
            for e in pr.entities:
                if e.kind == "class" and e.name == "HrSpecJpo":
                    cols = (e.attributes or {}).get("jpa_columns_meta") or {}
                    if "productTypeCd" in cols:
                        assert cols["productTypeCd"]["length"] == 4
                        found = True
                        break
        assert found, "HrSpecJpo.productTypeCd length=4 not found after enrich"


# ---------------------------------------------------------------------------
# Disk cache — register 시 entities.json + repo-meta.json 작성
# ---------------------------------------------------------------------------
class TestDiskCache:
    def test_register_writes_disk_cache(self, tmp_path: Path) -> None:
        # 임시 repo 구조 — 1 java file
        java_dir = tmp_path / "x" / "src"
        java_dir.mkdir(parents=True)
        (java_dir / "A.java").write_text(
            "package com.x; public class A { private int n = 5; }",
            encoding="utf-8",
        )

        reg = InMemoryRepositoryRegistry()
        entry = reg.register("tinyrepo", tmp_path / "x")

        cache = tmp_path / "x" / ".analyzed"
        assert (cache / "entities.json").exists()
        assert (cache / "repo-meta.json").exists()

        meta = json.loads((cache / "repo-meta.json").read_text())
        assert meta["repo_id"] == "tinyrepo"
        assert meta["files"] == entry.files
        assert meta["entities"] == entry.entities

        snap = json.loads((cache / "entities.json").read_text())
        assert "files" in snap and "metadata" in snap
        assert snap["metadata"]["repo_id"] == "tinyrepo"


# ---------------------------------------------------------------------------
# auto_discover_from_disk — startup 자동 복원
# ---------------------------------------------------------------------------
class TestAutoDiscover:
    def test_round_trip_via_disk_cache(self, tmp_path: Path) -> None:
        # 1. register → 디스크 캐시 작성
        java_dir = tmp_path / "rA" / "src"
        java_dir.mkdir(parents=True)
        (java_dir / "A.java").write_text(
            "package com.x; public class A { private int n = 5; }",
            encoding="utf-8",
        )
        reg1 = InMemoryRepositoryRegistry()
        original = reg1.register("repoA", tmp_path / "rA")

        # 2. 새 registry 생성 + auto_discover (startup 시뮬)
        reg2 = InMemoryRepositoryRegistry()
        discovered = auto_discover_from_disk(reg2, [tmp_path])
        assert len(discovered) == 1
        recovered = reg2.get("repoA")
        assert recovered is not None
        assert recovered.repo_id == original.repo_id
        assert recovered.files == original.files
        assert recovered.entities == original.entities

    def test_skip_missing_entities_json(self, tmp_path: Path) -> None:
        # repo-meta.json 만 있고 entities.json 없으면 skip + 경고
        cache = tmp_path / "broken" / ".analyzed"
        cache.mkdir(parents=True)
        (cache / "repo-meta.json").write_text(json.dumps({
            "repo_id": "broken",
            "path": str(tmp_path / "broken"),
            "files": 0, "entities": 0, "relations": 0,
            "errors_count": 0,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }))
        reg = InMemoryRepositoryRegistry()
        discovered = auto_discover_from_disk(reg, [tmp_path])
        assert discovered == []

    def test_corrupted_meta_does_not_crash(self, tmp_path: Path) -> None:
        cache = tmp_path / "rotten" / ".analyzed"
        cache.mkdir(parents=True)
        (cache / "repo-meta.json").write_text("not json {{{")
        reg = InMemoryRepositoryRegistry()
        discovered = auto_discover_from_disk(reg, [tmp_path])
        assert discovered == []  # graceful


# ---------------------------------------------------------------------------
# on_progress callback — SSE 입력
# ---------------------------------------------------------------------------
class TestProgressCallback:
    def test_callback_fires_for_each_stage(self, tmp_path: Path) -> None:
        java_dir = tmp_path / "p" / "src"
        java_dir.mkdir(parents=True)
        for i in range(3):
            (java_dir / f"A{i}.java").write_text(
                f"package com.x; public class A{i} {{ }}",
                encoding="utf-8",
            )

        events: list[tuple[str, int, int]] = []
        def cb(stage: str, done: int, total: int) -> None:
            events.append((stage, done, total))

        reg = InMemoryRepositoryRegistry()
        reg.register("p", tmp_path / "p", on_progress=cb)

        stages = [e[0] for e in events]
        assert "discovering" in stages
        assert "parsing" in stages
        assert "enriching" in stages
        assert stages[-1] == "complete"
