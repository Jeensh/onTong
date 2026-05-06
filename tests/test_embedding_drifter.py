"""OD-11-D3-2-a : CosineDrifter unit tests (embedding-based conflict candidate)."""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.embedding_drifter import (
    CosineDrifter,
    TextEmbedder,
)
from backend.modeling.gap_detection.gap_models import ScanConfig
from backend.modeling.manuals.manual_models import (
    DescribedInBinding,
    DescribedInTargetKind,
    GapDetectedBy,
    GapMode,
    GapSeverity,
    ManualFragment,
    ManualFragmentKind,
)
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


_CLOCK_TS = datetime(2026, 4, 21, 10, tzinfo=timezone.utc)


class _HashEmbedder:
    """결정적 해시 기반 embedder. 같은 텍스트 = 같은 벡터."""

    DIM = 16

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [b / 255.0 for b in digest[: self.DIM]]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class _ControlledEmbedder:
    """테스트용 — 텍스트→벡터 맵을 직접 주입."""

    def __init__(self, mapping: dict[str, list[float]]):
        self._map = mapping

    def embed(self, text: str) -> list[float]:
        return list(self._map[text])


def _rule(fqn: str, statement: str) -> BusinessRule:
    return BusinessRule(
        qualified_name=fqn,
        statement=statement,
        severity=RuleSeverity.HARD,
        confirmed=True,
        created_at=_CLOCK_TS,
    )


def _fragment(fqn: str, text: str) -> ManualFragment:
    return ManualFragment(
        qualified_name=fqn,
        section_fqn=fqn.rsplit("#", 1)[0] + "#sec",
        kind=ManualFragmentKind.TEXT,
        text=text,
        created_at=_CLOCK_TS,
    )


def _described(rule_fqn: str, frag_fqn: str) -> DescribedInBinding:
    return DescribedInBinding(
        source_fqn=rule_fqn,
        target_fqn=frag_fqn,
        target_kind=DescribedInTargetKind.MANUAL_FRAGMENT,
        confidence=1.0,
        source="manual",
        created_at=_CLOCK_TS,
    )


def _config() -> ScanConfig:
    return ScanConfig(
        repo_id="prod",
        gap_mode=GapMode.HIERARCHICAL,
        detected_by=GapDetectedBy.HIERARCHICAL,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_hash_embedder_conforms_to_protocol() -> None:
    embedder: TextEmbedder = _HashEmbedder()
    vec = embedder.embed("hello")
    assert isinstance(vec, list)
    assert len(vec) == _HashEmbedder.DIM


# ---------------------------------------------------------------------------
# CosineDrifter.find_drift
# ---------------------------------------------------------------------------
def test_find_drift_skips_when_no_described_in_mapping() -> None:
    drifter = CosineDrifter(embedder=_HashEmbedder(), clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "재고는 10 이상")
    frag = _fragment("doc#sec#f0", "전혀 다른 내용")
    drifts = drifter.find_drift(
        rules=[rule], fragments=[frag], described_in=[], config=_config(),
    )
    assert drifts == []


def test_find_drift_high_similarity_no_candidate() -> None:
    # rule 과 fragment 가 동일 텍스트 → cosine=1.0, cutoff 상회 → skip.
    drifter = CosineDrifter(embedder=_HashEmbedder(), cutoff=0.65,
                            clock=lambda: _CLOCK_TS)
    rule = _rule("rule.x", "안전재고 기준")
    frag = _fragment("doc#sec#f0", "안전재고 기준")
    drifts = drifter.find_drift(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.x", "doc#sec#f0")],
        config=_config(),
    )
    assert drifts == []


def test_find_drift_low_similarity_yields_candidate() -> None:
    # 직교 벡터 (cos=0) → cutoff(0.65) 미만.
    embedder = _ControlledEmbedder({
        "안전재고 ≥ 10": [1.0, 0.0],
        "신뢰도 < 50%": [0.0, 1.0],
    })
    drifter = CosineDrifter(embedder=embedder, cutoff=0.65, clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "안전재고 ≥ 10")
    frag = _fragment("doc#sec#f0", "신뢰도 < 50%")
    drifts = drifter.find_drift(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        config=_config(),
    )
    assert len(drifts) == 1
    d = drifts[0]
    assert d.direction is None
    assert d.target_fqn == "rule.safety"
    assert d.counterpart_fqn == "doc#sec#f0"
    # drifter 는 중립 MEDIUM. LLM 이 이후 재평가.
    assert d.severity is GapSeverity.MEDIUM


def test_find_drift_respects_custom_cutoff() -> None:
    embedder = _ControlledEmbedder({
        "rule A": [1.0, 0.0],
        "frag A": [0.9, 0.436],   # cos ≈ 0.9
    })
    cutoff_low = CosineDrifter(embedder=embedder, cutoff=0.7, clock=lambda: _CLOCK_TS)
    cutoff_high = CosineDrifter(embedder=embedder, cutoff=0.95, clock=lambda: _CLOCK_TS)
    rule = _rule("rule.x", "rule A")
    frag = _fragment("doc#sec#f0", "frag A")
    described = [_described("rule.x", "doc#sec#f0")]
    assert cutoff_low.find_drift(
        rules=[rule], fragments=[frag], described_in=described, config=_config(),
    ) == []
    high = cutoff_high.find_drift(
        rules=[rule], fragments=[frag], described_in=described, config=_config(),
    )
    assert len(high) == 1


def test_find_drift_skips_image_fragments() -> None:
    drifter = CosineDrifter(embedder=_HashEmbedder(), clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "rule stuff")
    img = ManualFragment(
        qualified_name="doc#sec#img",
        section_fqn="doc#sec",
        kind=ManualFragmentKind.IMAGE,
        text="image caption",
        image_ref="x.png",
        created_at=_CLOCK_TS,
    )
    drifts = drifter.find_drift(
        rules=[rule],
        fragments=[img],
        described_in=[_described("rule.safety", "doc#sec#img")],
        config=_config(),
    )
    assert drifts == []


def test_find_drift_stable_id_for_rescan() -> None:
    embedder = _ControlledEmbedder({
        "rule X": [1.0, 0.0],
        "frag Y": [0.0, 1.0],
    })
    drifter = CosineDrifter(embedder=embedder, cutoff=0.65, clock=lambda: _CLOCK_TS)
    rule = _rule("rule.x", "rule X")
    frag = _fragment("doc#sec#f0", "frag Y")
    described = [_described("rule.x", "doc#sec#f0")]
    first = drifter.find_drift(
        rules=[rule], fragments=[frag], described_in=described, config=_config(),
    )
    second = drifter.find_drift(
        rules=[rule], fragments=[frag], described_in=described, config=_config(),
    )
    assert first[0].id == second[0].id
