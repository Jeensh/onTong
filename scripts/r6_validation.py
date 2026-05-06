"""R6 validation — measure cap 2 confidence with vs. without javadoc/comments.

Setup:
  - Pick `HrSpecJpo` from `slab-design-real` (rich Korean inline comments
    + class javadoc — a realistic "well-documented legacy" baseline).
  - Run cap 2 (hypothesize) on the original ExtractedJpo → baseline.
  - Strip class_docstring=None and all column comments=None → "blind"
    ExtractedJpo.
  - Run cap 2 on the blind version → measured.
  - Compare: confidence, tool_call_count, hypothesis content.
  - Then run cap 5 (gaps), cap 6 (options), cap 7 (pattern) on the blind
    flow to demonstrate the full graph-aware pipeline.

Cost: 2× cap 2 (Opus) + 1× cap 5 + 1× cap 6 + 1× cap 7 ≈ $1.50 total.

Usage:
    set -a && . ./.env && set +a
    ./.venv/bin/python scripts/r6_validation.py 2>&1 | tee toClaude/modeling/r6_val_run.log
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.application.authoring import session as smod
from backend.application.authoring.agent_tool_adapter import (
    list_tool_calls_for_session,
)
from backend.application.authoring.capabilities import (
    answer_absorber as aa,
    code_extractor as ce,
    gap_detector as gd,
    hypothesis as hp,
    option_proposer as op,
    pattern_checker as pc,
)
from backend.modeling.persistence.database import bootstrap_database


REPO_ID = "slab-design-real"
JPO_FQN = "com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo"


def _strip(jpo: ce.ExtractedJpo) -> ce.ExtractedJpo:
    """Return a copy with class_docstring=None and every column.comment=None."""
    return ce.ExtractedJpo(
        package=jpo.package,
        class_name=jpo.class_name,
        table_name=jpo.table_name,
        pk_class=jpo.pk_class,
        class_docstring=None,
        pk_columns=[
            ce.CodeColumn(
                name=c.name,
                db_column=c.db_column,
                java_type=c.java_type,
                db_length=c.db_length,
                db_precision=c.db_precision,
                db_scale=c.db_scale,
                is_pk=c.is_pk,
                comment=None,
            )
            for c in jpo.pk_columns
        ],
        regular_columns=[
            ce.CodeColumn(
                name=c.name,
                db_column=c.db_column,
                java_type=c.java_type,
                db_length=c.db_length,
                db_precision=c.db_precision,
                db_scale=c.db_scale,
                is_pk=c.is_pk,
                comment=None,
            )
            for c in jpo.regular_columns
        ],
    )


async def main() -> dict[str, Any]:
    bootstrap_database()

    java_path = Path(
        "sample-repos/slab-design-real/slab-design-store/src/main/java/"
        "com/example/slabdesign/store/sd/std/oracle/jpo/HrSpecJpo.java"
    )
    java_text = java_path.read_text(encoding="utf-8")

    # ── Step 0 — extract baseline JPO from real file ────────────────
    sess_a = smod.create_session(operator_id="r6_val_baseline", repo_id=REPO_ID)
    print(f"\n=== R6 VAL — session A (baseline, with javadoc): {sess_a} ===")
    t0 = time.perf_counter()
    extracted = await ce.extract_jpo_from_file(
        path=str(java_path),
        content=java_text,
        session_id=sess_a,
        turn_no=1,
    )
    print(f"[cap1] extracted: {extracted.class_name} ({extracted.table_name}), "
          f"PK={len(extracted.pk_columns)} cols, regular={len(extracted.regular_columns)} cols, "
          f"docstring={'YES' if extracted.class_docstring else 'NO'} "
          f"({len(extracted.class_docstring or '')} chars)  [{int((time.perf_counter()-t0)*1000)}ms]")

    blind = _strip(extracted)
    print(f"[strip] blind version: docstring={blind.class_docstring is None}, "
          f"any comment={any(c.comment for c in [*blind.pk_columns, *blind.regular_columns])}")

    # ── Step 1A — cap 2 on baseline ─────────────────────────────────
    t0 = time.perf_counter()
    h_baseline = await hp.propose_entity_hypothesis(
        extracted, session_id=sess_a, turn_no=2
    )
    dur_a = int((time.perf_counter() - t0) * 1000)
    trace_a = list_tool_calls_for_session(sess_a)
    print(f"\n[cap2 baseline] confidence={h_baseline.confidence:.2f}, "
          f"role={h_baseline.domain_role}, "
          f"label={h_baseline.candidate_term_korean!r} / {h_baseline.candidate_term_english!r}, "
          f"tools={len(trace_a)}, dur={dur_a}ms")
    for t in trace_a:
        print(f"  · {t['tool_name']}({list(t['args'].keys())[:1]}) {t['duration_ms']}ms")

    # ── Step 1B — cap 2 on blind ────────────────────────────────────
    sess_b = smod.create_session(operator_id="r6_val_blind", repo_id=REPO_ID)
    print(f"\n=== R6 VAL — session B (blind, no doc/comments): {sess_b} ===")
    t0 = time.perf_counter()
    h_blind = await hp.propose_entity_hypothesis(
        blind, session_id=sess_b, turn_no=1
    )
    dur_b = int((time.perf_counter() - t0) * 1000)
    trace_b = list_tool_calls_for_session(sess_b)
    print(f"\n[cap2 blind] confidence={h_blind.confidence:.2f}, "
          f"role={h_blind.domain_role}, "
          f"label={h_blind.candidate_term_korean!r} / {h_blind.candidate_term_english!r}, "
          f"tools={len(trace_b)}, dur={dur_b}ms")
    for t in trace_b:
        print(f"  · {t['tool_name']}({list(t['args'].keys())[:1]}) {t['duration_ms']}ms")

    # ── Step 2 — cap 5 (gaps) on blind ──────────────────────────────
    # Hand-built AbsorbedAnswers (no real interview ran; this is a stub
    # so cap 5/6/7 have something to chew on).
    answers = aa.AbsorbedAnswers(
        per_question={},
        emergent_facts=[],
        contradictions=[],
        confidence_after=h_blind.confidence,
    )

    print(f"\n=== R6 VAL — cap 5 (gaps) on blind ===")
    t0 = time.perf_counter()
    gaps = await gd.detect_gaps(
        blind, h_blind, answers, session_id=sess_b, turn_no=2
    )
    dur_g = int((time.perf_counter() - t0) * 1000)
    print(f"[cap5] gaps={len(gaps.gaps)}, severity={gaps.severity_summary!r}, "
          f"blocks={gaps.blocks_modeling}, dur={dur_g}ms")
    for g in gaps.gaps:
        print(f"  · [{g.kind}/{g.severity}] {g.title}")

    # ── Step 3 — cap 6 (options) on blind ───────────────────────────
    print(f"\n=== R6 VAL — cap 6 (options) on blind ===")
    t0 = time.perf_counter()
    opts = await op.propose_options(
        h_blind, answers, session_id=sess_b, turn_no=3
    )
    dur_o = int((time.perf_counter() - t0) * 1000)
    print(f"[cap6] options={len(opts.options)}, recommended={opts.recommended_id!r}, dur={dur_o}ms")
    for o in opts.options:
        marker = "★" if o.id == opts.recommended_id else " "
        print(f"  {marker} {o.id} — {o.name} ({o.entities_count_hint} entity, align={o.domain_alignment})")

    accepted = next(o for o in opts.options if o.id == opts.recommended_id)

    # ── Step 4 — cap 7 (pattern) on blind ───────────────────────────
    print(f"\n=== R6 VAL — cap 7 (pattern) on blind ===")
    t0 = time.perf_counter()
    pattern = await pc.check_pattern(
        h_blind, accepted, session_id=sess_b, turn_no=4
    )
    dur_p = int((time.perf_counter() - t0) * 1000)
    print(f"[cap7] findings={len(pattern.findings)}, score={pattern.consistency_score:.2f}, "
          f"recommendation={pattern.recommendation!r}, dur={dur_p}ms")
    for f in pattern.findings:
        print(f"  · [{f.dimension}/{f.severity}/{f.alignment}] {f.title}")
    print(f"[cap7] summary: {pattern.summary}")

    # ── Final trace counts ──────────────────────────────────────────
    final_trace = list_tool_calls_for_session(sess_b)
    print(f"\n=== Session B final trace: {len(final_trace)} total tool calls ===")
    by_cap: dict[str, int] = {}
    for t in final_trace:
        by_cap[t["capability"]] = by_cap.get(t["capability"], 0) + 1
    for cap, cnt in sorted(by_cap.items()):
        print(f"  · {cap}: {cnt}")

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("R6-VAL SUMMARY")
    print("=" * 60)
    print(f"Cap 2 confidence  baseline (with javadoc): {h_baseline.confidence:.2f}")
    print(f"Cap 2 confidence  blind   (no doc/comment): {h_blind.confidence:.2f}")
    print(f"Cap 2 confidence  delta:                    {h_blind.confidence - h_baseline.confidence:+.2f}")
    print(f"Cap 2 tool calls  baseline:                 {len(trace_a)}")
    print(f"Cap 2 tool calls  blind:                    {len([t for t in trace_b if t['capability']=='hypothesis'])}")
    print(f"Pipeline outputs  on blind:")
    print(f"  · cap 5 gaps:        {len(gaps.gaps)} ({gaps.severity_summary})")
    print(f"  · cap 6 options:     {len(opts.options)} (★ {opts.recommended_id})")
    print(f"  · cap 7 findings:    {len(pattern.findings)} (score {pattern.consistency_score:.2f})")

    return {
        "baseline": {
            "session_id": sess_a,
            "confidence": h_baseline.confidence,
            "domain_role": h_baseline.domain_role,
            "label_ko": h_baseline.candidate_term_korean,
            "label_en": h_baseline.candidate_term_english,
            "tool_call_count": len(trace_a),
            "duration_ms": dur_a,
            "concerns": h_baseline.concerns,
            "assumptions": h_baseline.assumptions,
        },
        "blind": {
            "session_id": sess_b,
            "confidence": h_blind.confidence,
            "domain_role": h_blind.domain_role,
            "label_ko": h_blind.candidate_term_korean,
            "label_en": h_blind.candidate_term_english,
            "tool_call_count": len([t for t in trace_b if t["capability"] == "hypothesis"]),
            "duration_ms": dur_b,
            "concerns": h_blind.concerns,
            "assumptions": h_blind.assumptions,
            "trace": [
                {
                    "tool_name": t["tool_name"],
                    "args": t["args"],
                    "result_summary": t["result_summary"],
                    "duration_ms": t["duration_ms"],
                    "cached": t["cached"],
                }
                for t in trace_b if t["capability"] == "hypothesis"
            ],
        },
        "pipeline_blind": {
            "gaps": {
                "count": len(gaps.gaps),
                "severity_summary": gaps.severity_summary,
                "blocks": gaps.blocks_modeling,
                "duration_ms": dur_g,
                "items": [g.model_dump() for g in gaps.gaps],
            },
            "options": {
                "count": len(opts.options),
                "recommended_id": opts.recommended_id,
                "duration_ms": dur_o,
                "items": [o.model_dump() for o in opts.options],
            },
            "pattern": {
                "findings_count": len(pattern.findings),
                "score": pattern.consistency_score,
                "recommendation": pattern.recommendation,
                "summary": pattern.summary,
                "duration_ms": dur_p,
                "items": [f.model_dump() for f in pattern.findings],
            },
        },
    }


if __name__ == "__main__":
    out = asyncio.run(main())
    Path("toClaude/modeling/r6_val_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nSaved → toClaude/modeling/r6_val_summary.json")
