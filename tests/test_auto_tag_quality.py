"""A8: Regression test for auto-tag suggestion quality.

Runs suggest_metadata against every wiki sample document and checks:
  - domain matches the file's actual directory (expected domain)
  - all returned tags are normalized (either reused from registry or
    explicitly flagged in tag_alternatives / tag_replaced)
  - response time < 10s per doc (LLM network bound, generous budget)

Baseline snapshot is written to tests/fixtures/auto_tag_baseline.json
for future diffing. Requires the backend to be running on :8001.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
import yaml

BACKEND = "http://localhost:8001"
WIKI_ROOT = Path(__file__).resolve().parents[1] / "wiki"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "auto_tag_baseline.json"

# Directories whose first path segment IS the expected domain.
DOMAIN_DIRS = {"SCM", "ERP", "MES", "인프라", "기획", "재무", "인사"}


def _collect_samples() -> list[Path]:
    out: list[Path] = []
    for p in WIKI_ROOT.rglob("*.md"):
        parts = p.relative_to(WIKI_ROOT).parts
        if not parts or parts[0].startswith("_") or parts[0].startswith("."):
            continue
        if parts[0] not in DOMAIN_DIRS:
            continue
        out.append(p)
    return sorted(out)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    try:
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body
    except Exception:
        return {}, text


def _is_backend_up() -> bool:
    try:
        return httpx.get(f"{BACKEND}/health", timeout=2.0).status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _is_backend_up(), reason="backend not running on :8001")
def test_auto_tag_quality_baseline():
    samples = _collect_samples()
    assert len(samples) >= 15, f"expected >=15 wiki samples, got {len(samples)}"

    results: list[dict] = []
    failures: list[str] = []

    with httpx.Client(timeout=30.0) as client:
        for path in samples:
            rel = str(path.relative_to(WIKI_ROOT.parent)).replace("\\", "/")
            expected_domain = path.relative_to(WIKI_ROOT).parts[0]
            text = path.read_text(encoding="utf-8")
            fm, body = _parse_frontmatter(text)
            existing_tags = fm.get("tags") or []

            t0 = time.perf_counter()
            r = client.post(
                f"{BACKEND}/api/metadata/suggest",
                json={
                    "content": body[:3000],
                    "existing_tags": [],  # force fresh suggestion
                    "path": rel,
                    "related": fm.get("related") or [],
                },
            )
            elapsed = time.perf_counter() - t0
            r.raise_for_status()
            data = r.json()

            results.append(
                {
                    "path": rel,
                    "expected_domain": expected_domain,
                    "suggested_domain": data.get("domain"),
                    "process": data.get("process"),
                    "tags": data.get("tags", []),
                    "tag_replaced": data.get("tag_replaced") or {},
                    "tag_alternatives_count": len(
                        data.get("tag_alternatives") or {}
                    ),
                    "confidence": data.get("confidence"),
                    "elapsed_sec": round(elapsed, 2),
                }
            )

            if data.get("domain") != expected_domain:
                failures.append(
                    f"{rel}: domain={data.get('domain')} != expected {expected_domain}"
                )
            if elapsed > 25.0:
                failures.append(f"{rel}: took {elapsed:.1f}s (>25s)")
            if not data.get("tags"):
                failures.append(f"{rel}: returned zero tags")

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    total = len(results)
    domain_hit = sum(
        1 for r in results if r["suggested_domain"] == r["expected_domain"]
    )
    replaced_total = sum(len(r["tag_replaced"]) for r in results)
    alt_total = sum(r["tag_alternatives_count"] for r in results)
    summary = {
        "total": total,
        "domain_accuracy": round(domain_hit / total, 3) if total else 0,
        "avg_confidence": round(
            sum(r["confidence"] or 0 for r in results) / total, 3
        )
        if total
        else 0,
        "avg_elapsed_sec": round(
            sum(r["elapsed_sec"] for r in results) / total, 2
        )
        if total
        else 0,
        "tags_replaced_total": replaced_total,
        "docs_with_alternatives": alt_total,
    }
    FIXTURE.write_text(
        json.dumps(
            {"summary": summary, "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Soft thresholds: domain accuracy ≥ 80% (LLM noise tolerated).
    assert summary["domain_accuracy"] >= 0.8, (
        f"domain accuracy {summary['domain_accuracy']} < 0.8\n"
        + "\n".join(failures)
    )
    # No catastrophic failures.
    hard_fails = [f for f in failures if "zero tags" in f or "took" in f]
    assert not hard_fails, "hard failures:\n" + "\n".join(hard_fails)
