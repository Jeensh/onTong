"""OD-11-E1-j (A1) — JavaParser 11-analyzer 결과를 JSON 스냅샷으로 덤프.

데모 코드 도착 전후 비교 + 회귀 / 디버깅 자료 + 외부 도구 (jq, diff 등) 입력용.

Usage
-----
    cd /Users/donghae/workspace/ai/onTong
    .venv/bin/python scripts/dump_entities_snapshot.py \\
        --repo sample-repos/slab-design-engine/src/main/java \\
        --out  sample-repos/slab-design-engine/.analyzed/entities.json \\
        --repo-id slab-design-engine

기본값으로 인자 생략 시 Slab 샘플에 대해 동작.

Schema
------
    {
      "metadata": {
        "repo_id": "slab-design-engine",
        "repo_path": "sample-repos/.../java",   # 절대 경로
        "generated_at": "2026-04-25T...Z",
        "analyzers": [...],                      # 11종 이름
        "totals": {"files": 11, "entities": 95, "relations": 177, "errors": 0}
      },
      "files": {
        "<relative-file-path>": {
          "language": "Java",
          "errors": [...],
          "entities": [{"kind", "qualified_name", "name", "line_start",
                        "line_end", "modifiers", "parent", "attributes"}],
          "relations": [{"kind", "source", "target", "line", "attributes"}]
        }
      }
    }

파일 경로는 `--repo` 디렉토리 기준 상대 경로 (다른 머신에서도 안정적).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.modeling.code_analysis.java_parser import JavaParser  # noqa: E402
from backend.modeling.code_analysis.spring import (  # noqa: E402
    AopAnalyzer,
    BeanUtilsAnalyzer,
    ConfigPropertiesAnalyzer,
    DIAnalyzer,
    EventsAnalyzer,
    HttpAnalyzer,
    JpaAnalyzer,
    MapStructAnalyzer,
    NativeSqlAnalyzer,
    ProfileAnalyzer,
    ReflectionAnalyzer,
    ScheduledAnalyzer,
)


def _build_parser() -> tuple[JavaParser, list[str]]:
    """12-analyzer 일괄 구성 — B5-7 (JPA) 까지의 최신 셋."""
    analyzers = [
        DIAnalyzer(),
        AopAnalyzer(),
        HttpAnalyzer(),
        EventsAnalyzer(),
        ScheduledAnalyzer(),
        ProfileAnalyzer(),
        ReflectionAnalyzer(),
        MapStructAnalyzer(),
        BeanUtilsAnalyzer(),
        NativeSqlAnalyzer(),
        ConfigPropertiesAnalyzer(),
        JpaAnalyzer(),
    ]
    names = [type(a).__name__ for a in analyzers]
    return JavaParser(spring_analyzers=analyzers), names


def _serialize_entity(e: object) -> dict:
    d = asdict(e)
    return d


def _serialize_relation(r: object) -> dict:
    d = asdict(r)
    return d


def dump_snapshot(repo_path: Path, repo_id: str) -> dict:
    """Walk all `.java` files under `repo_path` and return the snapshot dict.

    Runs CrossFileEnricher (B6-4) after per-file parse — wires `JpaAnnotationExtractor`
    so JPA `@Entity` / `@Table` / `@Column` (length/precision/scale/IdClass) metadata
    surfaces on class CodeEntity attributes (jpa_table, jpa_columns_meta, jpa_id_*).
    Critical for 시나리오 1 (column length impact).
    """
    from backend.modeling.code_analysis.cross_file_enricher import enrich_repo

    parser, analyzer_names = _build_parser()

    parse_results = []
    repo_path_for_relpath = repo_path

    for fp in sorted(repo_path.rglob("*.java")):
        text = fp.read_text(encoding="utf-8")
        result = parser.parse_file(fp, text)
        parse_results.append((fp, result))

    # Build class/field index + run JpaAnnotationExtractor on every @Entity class.
    from backend.modeling.code_analysis.cross_file_enricher import build_indices

    flat_results = [r for _, r in parse_results]
    class_index, field_index = build_indices(flat_results)
    enrich_repo(flat_results, class_index, field_index)

    files_section: dict[str, dict] = {}
    totals = {"files": 0, "entities": 0, "relations": 0, "errors": 0}
    for fp, result in parse_results:
        rel_path = str(fp.relative_to(repo_path_for_relpath))
        files_section[rel_path] = {
            "language": result.language,
            "errors": list(result.errors),
            "entities": [_serialize_entity(e) for e in result.entities],
            "relations": [_serialize_relation(r) for r in result.relations],
        }
        totals["files"] += 1
        totals["entities"] += len(result.entities)
        totals["relations"] += len(result.relations)
        totals["errors"] += len(result.errors)

    return {
        "metadata": {
            "repo_id": repo_id,
            "repo_path": str(repo_path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analyzers": analyzer_names,
            "totals": totals,
        },
        "files": files_section,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--repo",
        type=Path,
        default=Path("sample-repos/slab-design-engine/src/main/java"),
        help="Java source root directory (recursive .java walk).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("sample-repos/slab-design-engine/.analyzed/entities.json"),
        help="Output JSON path. Parent dirs auto-created.",
    )
    p.add_argument(
        "--repo-id",
        default="slab-design-engine",
        help="Logical repo id stored in metadata (no path normalization).",
    )
    args = p.parse_args()

    if not args.repo.is_dir():
        print(f"ERROR: --repo {args.repo} not found or not a directory", file=sys.stderr)
        return 2

    snapshot = dump_snapshot(args.repo, args.repo_id)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    t = snapshot["metadata"]["totals"]
    print(
        f"[snapshot] {args.out} : "
        f"{t['files']} files / {t['entities']} entities / {t['relations']} relations / "
        f"{t['errors']} errors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
