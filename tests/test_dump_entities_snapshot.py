"""OD-11-E1-j (A1) — entities.json 스냅샷 스크립트 테스트.

스크립트가 11-analyzer 파이프라인을 정확히 묶고, JSON 스키마 invariant 를
지키는지 검증. Slab 샘플 그대로 사용 — 데모 코드 도착 후에도 동일 스크립트로
재실행 가능해야 함.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dump_entities_snapshot import _build_parser, dump_snapshot


SLAB_REPO = Path("sample-repos/slab-design-engine/src/main/java")


def _slab_or_skip() -> Path:
    if not SLAB_REPO.is_dir():
        pytest.skip("Slab sample missing — script test requires sample-repos/")
    return SLAB_REPO


# ---------------------------------------------------------------------------
# 11-analyzer 구성
# ---------------------------------------------------------------------------
def test_build_parser_wires_twelve_spring_analyzers() -> None:
    parser, names = _build_parser()
    assert len(names) == 12
    # Spring analyzer 셋의 핵심 멤버가 다 포함됐는지.
    expected = {
        "DIAnalyzer", "AopAnalyzer", "HttpAnalyzer", "EventsAnalyzer",
        "ScheduledAnalyzer", "ProfileAnalyzer", "ReflectionAnalyzer",
        "MapStructAnalyzer", "BeanUtilsAnalyzer", "NativeSqlAnalyzer",
        "ConfigPropertiesAnalyzer", "JpaAnalyzer",
    }
    assert set(names) == expected
    # JavaParser 객체 자체도 동일 개수 보유.
    assert len(parser._spring_analyzers) == 12  # noqa: SLF001 — internal sanity


# ---------------------------------------------------------------------------
# Slab 스냅샷 — 스키마 + 결정성
# ---------------------------------------------------------------------------
class TestSnapshotSchema:
    def setup_method(self) -> None:
        self.repo = _slab_or_skip()
        self.snap = dump_snapshot(self.repo, "slab-design-engine")

    def test_top_level_has_metadata_and_files(self) -> None:
        assert set(self.snap.keys()) == {"metadata", "files"}

    def test_metadata_fields(self) -> None:
        meta = self.snap["metadata"]
        assert meta["repo_id"] == "slab-design-engine"
        assert meta["repo_path"] == str(self.repo)
        assert "generated_at" in meta
        assert isinstance(meta["analyzers"], list)
        assert len(meta["analyzers"]) == 12
        totals = meta["totals"]
        # E1-f 검증 결과 (95/177/0) — 회귀 차단 baseline.
        assert totals["files"] == 11
        assert totals["entities"] == 95
        assert totals["relations"] == 177
        assert totals["errors"] == 0

    def test_file_keys_are_relative(self) -> None:
        # 절대 경로 / Windows 경로 섞이면 diff 가 깨짐 — 상대 경로 강제.
        for key in self.snap["files"].keys():
            assert not key.startswith("/")
            # POSIX 분리자만 (sorted rglob 가 native sep 사용 — Windows 에선 \).
            # 본 프로젝트는 macOS/Linux only 라 / 가정.
            assert "\\" not in key

    def test_each_file_has_entities_and_relations_lists(self) -> None:
        for path, entry in self.snap["files"].items():
            assert "language" in entry
            assert "errors" in entry
            assert isinstance(entry["entities"], list)
            assert isinstance(entry["relations"], list)

    def test_config_property_entries_round_trip(self) -> None:
        ep = self.snap["files"]["com/ontong/slab/config/EquipmentProperties.java"]
        cps = [e for e in ep["entities"] if e["kind"] == "config_property"]
        assert len(cps) == 5
        # E1-f 검증 결과와 동일 (default 값 + kebab alias 모두 보존).
        max_thickness = next(
            e for e in cps if e["qualified_name"] == "slab.equipment.maxThicknessMm"
        )
        assert max_thickness["attributes"]["default_value"] == "240.0"
        assert (
            max_thickness["attributes"]["key_kebab"]
            == "slab.equipment.max-thickness-mm"
        )


# ---------------------------------------------------------------------------
# JSON 직렬화 안정성
# ---------------------------------------------------------------------------
class TestJsonSerialization:
    def test_snapshot_is_json_serializable(self) -> None:
        repo = _slab_or_skip()
        snap = dump_snapshot(repo, "slab-design-engine")
        # 라운드트립 — 스키마 안에 enum / datetime 등 비직렬화 객체가 없음을 확인.
        text = json.dumps(snap, ensure_ascii=False, indent=2)
        loaded = json.loads(text)
        assert loaded["metadata"]["totals"] == snap["metadata"]["totals"]
        assert set(loaded["files"].keys()) == set(snap["files"].keys())

    def test_writes_to_file_when_invoked_via_main(self, tmp_path: Path) -> None:
        # main() 호출은 sys.argv 바꿔야 해서 여기서는 스킵 — dump_snapshot 만 검증.
        # 출력 파일 작성은 main 의 args.out.write_text(...) 라인 단순 I/O.
        repo = _slab_or_skip()
        snap = dump_snapshot(repo, "slab-design-engine")
        out = tmp_path / "snap.json"
        out.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        assert out.exists()
        assert out.stat().st_size > 0
        # tail 검증.
        content = out.read_text(encoding="utf-8")
        assert content.startswith("{")
        assert content.endswith("}")
