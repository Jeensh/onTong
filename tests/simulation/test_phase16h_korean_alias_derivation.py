"""Phase 16H — Korean alias derivation from Action FQN/label."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _load_module():
    p = Path(__file__).parents[2] / "scripts" / "seed_phase16h_action_korean_aliases.py"
    spec = importlib.util.spec_from_file_location("seed_phase16h", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pure_korean_label() -> None:
    """label = 분류 → [분류]."""
    mod = _load_module()
    r = mod.derive_korean_aliases("action.scm.product.분류", "분류")
    assert r == ["분류"]


def test_compound_korean_kept_split_emitted() -> None:
    """compound (e.g. 정합성_검증) full + split parts emitted, stopword 검증 제외."""
    mod = _load_module()
    r = mod.derive_korean_aliases("action.scm.order.정합성_검증", "정합성_검증")
    assert "정합성_검증" in r
    assert "정합성" in r
    assert "검증" not in r, f"stopword 검증 단독 제외. r={r}"


def test_korean_with_english_fqn() -> None:
    """label = '고객표준 매칭 (first match)' → [고객표준, 매칭]."""
    mod = _load_module()
    r = mod.derive_korean_aliases(
        "action.scm.std.match_customer_limit_for_order",
        "고객표준 매칭 (first match)",
    )
    assert "고객표준" in r
    assert "매칭" in r


def test_korean_underscore_compound_in_fqn() -> None:
    """FQN 의 슬랩설계_실행 → compound + 슬랩설계 (실행 단독은 stopword 제외)."""
    mod = _load_module()
    r = mod.derive_korean_aliases("action.scm.슬랩설계_실행", "slab design")
    assert "슬랩설계_실행" in r
    assert "슬랩설계" in r
    assert "실행" not in r, f"stopword 실행 단독 제외. r={r}"


def test_english_only_no_korean() -> None:
    """순수 English FQN/label → 빈 list."""
    mod = _load_module()
    r = mod.derive_korean_aliases("action.scm.find_spec", "find_spec")
    assert r == []


def test_duplicate_dedup() -> None:
    """FQN + label 양쪽에 동일 Korean 있으면 한 번만 emit."""
    mod = _load_module()
    r = mod.derive_korean_aliases("action.scm.결정", "결정")
    assert r == ["결정"], f"dedup 실패. r={r}"
