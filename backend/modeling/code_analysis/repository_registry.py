"""RepositoryRegistry — repo_id 단위로 12-analyzer 결과 보관.

backend lifespan 시작 시 startup 디스크 스캔 (`sample-repos/*/.analyzed/`) 으로
이전 등록 자동 복원. 사용자가 UI 에서 신규 등록 시 register() 가 12-analyzer 실행
+ 디스크 캐시 (`<path>/.analyzed/entities.json` + `repo-meta.json`) 작성.

이 registry 는 :
    - `terms_api.propose-bindings` — repo_parse_results 대신 registry.get(...).parse_results
    - `repos_api`               — REST endpoints (P3-Backend)
    - 향후 영향도 분석 / 샌드박스 — 모두 동일 registry 참조

Spec : `toClaude/modeling/HANDOFF.md` Phase B (Workflow 개선).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Protocol, runtime_checkable

from backend.modeling.code_analysis.entity_search_index import EntitySearchIndex
from backend.modeling.code_analysis.parser_protocol import ParseResult
from backend.modeling.code_analysis.repo_parser import (
    parse_repo,
    rehydrate_from_snapshot,
    serialize_parse_results,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepositoryEntry:
    """등록된 repo 의 메타 + parse_results."""
    repo_id: str
    path: str                              # absolute path string
    files: int
    entities: int
    relations: int
    errors: list[str]
    registered_at: datetime
    parse_results: list[ParseResult]       # in-memory


@runtime_checkable
class RepositoryRegistry(Protocol):
    """Repository registry — 12-analyzer 결과 보관."""

    def register(
        self,
        repo_id: str,
        path: Path,
        *,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> RepositoryEntry: ...
    def list(self) -> list[RepositoryEntry]: ...
    def get(self, repo_id: str) -> RepositoryEntry | None: ...
    def unregister(self, repo_id: str) -> bool: ...
    def clear(self) -> None: ...


class InMemoryRepositoryRegistry:
    """In-memory dict 기반 reference 구현.

    register() 시 disk cache 도 작성 (`<path>/.analyzed/entities.json` +
    `repo-meta.json`). startup 시 `auto_discover_from_disk(scan_root)` 로
    이전 캐시들을 한 번에 rehydrate.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, RepositoryEntry] = {}
        # 5000+ class scale — search index per repo, built on register
        self._index_by_id: dict[str, EntitySearchIndex] = {}

    # ---------------------------------------------------------------- write
    def register(
        self,
        repo_id: str,
        path: Path,
        *,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> RepositoryEntry:
        if not path.is_dir():
            raise ValueError(f"path is not a directory: {path}")

        path_abs = path.resolve()
        results = parse_repo(path_abs, on_progress=on_progress)

        totals = _totals(results)
        all_errors: list[str] = []
        for pr in results:
            all_errors.extend(pr.errors)

        entry = RepositoryEntry(
            repo_id=repo_id,
            path=str(path_abs),
            files=totals["files"],
            entities=totals["entities"],
            relations=totals["relations"],
            errors=all_errors,
            registered_at=datetime.now(timezone.utc),
            parse_results=results,
        )
        self._by_id[repo_id] = entry
        self._rebuild_index(repo_id, results)

        # Disk cache (fail-soft — 캐시 실패가 등록 막지 않음).
        try:
            _write_disk_cache(path_abs, entry, results)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "RepositoryRegistry: disk cache write skipped for %s: %s",
                repo_id, exc,
            )

        return entry

    def list(self) -> list[RepositoryEntry]:
        return list(self._by_id.values())

    def get(self, repo_id: str) -> RepositoryEntry | None:
        return self._by_id.get(repo_id)

    def get_index(self, repo_id: str) -> EntitySearchIndex | None:
        """Search index — built on register, lazy-built if missing (rehydrated repos)."""
        idx = self._index_by_id.get(repo_id)
        if idx is None:
            entry = self._by_id.get(repo_id)
            if entry is None:
                return None
            self._rebuild_index(repo_id, entry.parse_results)
            idx = self._index_by_id.get(repo_id)
        return idx

    def unregister(self, repo_id: str) -> bool:
        self._index_by_id.pop(repo_id, None)
        return self._by_id.pop(repo_id, None) is not None

    def clear(self) -> None:
        self._by_id.clear()
        self._index_by_id.clear()

    def __iter__(self) -> Iterator[RepositoryEntry]:
        return iter(self._by_id.values())

    # ---------------------------------------------------------------- helpers
    def _rebuild_index(self, repo_id: str, results: Iterable[ParseResult]) -> None:
        flat = (e for pr in results for e in pr.entities)
        self._index_by_id[repo_id] = EntitySearchIndex.build(flat)


# ---------------------------------------------------------------- disk cache
_META_FILENAME = "repo-meta.json"
_ENTITIES_FILENAME = "entities.json"


def _totals(results: Iterable[ParseResult]) -> dict[str, int]:
    t = {"files": 0, "entities": 0, "relations": 0, "errors": 0}
    for pr in results:
        t["files"] += 1
        t["entities"] += len(pr.entities)
        t["relations"] += len(pr.relations)
        t["errors"] += len(pr.errors)
    return t


def _write_disk_cache(
    path_abs: Path, entry: RepositoryEntry, results: Iterable[ParseResult],
) -> None:
    cache_dir = path_abs / ".analyzed"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # entities.json — 호환 dump_entities_snapshot.py 형식
    snapshot = serialize_parse_results(results, path_abs)
    snapshot["metadata"] = {
        "repo_id": entry.repo_id,
        "repo_path": entry.path,
        "generated_at": entry.registered_at.isoformat(),
        "totals": snapshot.get("totals") or {},
    }
    (cache_dir / _ENTITIES_FILENAME).write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # repo-meta.json — registry 가 startup 시 빠르게 스캔할 가벼운 메타.
    meta = {
        "repo_id": entry.repo_id,
        "path": entry.path,
        "files": entry.files,
        "entities": entry.entities,
        "relations": entry.relations,
        "errors_count": len(entry.errors),
        "registered_at": entry.registered_at.isoformat(),
    }
    (cache_dir / _META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def auto_discover_from_disk(
    registry: InMemoryRepositoryRegistry,
    scan_roots: Iterable[Path],
) -> list[RepositoryEntry]:
    """Scan `scan_roots` for `<repo>/.analyzed/entities.json` and rehydrate.

    Two precedence levels :
      1. `repo-meta.json` 존재 → 거기서 repo_id / path 읽음 (정식 register 산출)
      2. `entities.json` 만 → metadata.repo_id / metadata.repo_path fallback
                              (구버전 dump_entities_snapshot.py 산출)

    Returns the entries that were rehydrated. Skips invalid (logs warning).
    """
    discovered: list[RepositoryEntry] = []
    for root in scan_roots:
        if not root.is_dir():
            continue
        for entities_path in sorted(root.glob("*/.analyzed/entities.json")):
            meta_path = entities_path.parent / _META_FILENAME
            try:
                snapshot = json.loads(entities_path.read_text(encoding="utf-8"))
                snap_meta = snapshot.get("metadata") or {}

                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    repo_id = meta["repo_id"]
                    repo_path = Path(meta["path"])
                    registered_at = _parse_iso(meta.get("registered_at"))
                else:
                    # Fallback : entities.json 의 metadata 사용.
                    repo_id = snap_meta.get("repo_id")
                    raw_path = snap_meta.get("repo_path")
                    if not repo_id or not raw_path:
                        logger.warning(
                            "auto_discover: %s lacks repo_id/repo_path — skip",
                            entities_path,
                        )
                        continue
                    repo_path = Path(raw_path)
                    registered_at = _parse_iso(snap_meta.get("generated_at"))

                results = rehydrate_from_snapshot(snapshot, repo_path)
                totals = _totals(results)
                all_errors: list[str] = []
                for pr in results:
                    all_errors.extend(pr.errors)
                entry = RepositoryEntry(
                    repo_id=repo_id,
                    path=str(repo_path),
                    files=totals["files"],
                    entities=totals["entities"],
                    relations=totals["relations"],
                    errors=all_errors,
                    registered_at=registered_at,
                    parse_results=results,
                )
                registry._by_id[entry.repo_id] = entry  # noqa: SLF001 — internal
                discovered.append(entry)
                logger.info(
                    "auto_discover: %s rehydrated (%d files, %d entities)",
                    entry.repo_id, entry.files, entry.entities,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "auto_discover: failed to rehydrate %s — %s",
                    entities_path, exc,
                )
    return discovered


def _parse_iso(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)


__all__ = (
    "RepositoryEntry",
    "RepositoryRegistry",
    "InMemoryRepositoryRegistry",
    "auto_discover_from_disk",
)
