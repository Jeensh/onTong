"""Phase 6-B — 실행 이력 저장소 + lineage 트래킹.

Run = sandbox step 1회 실행 기록.
- inputs/outputs JSON 직렬화 저장
- baseline 표시 + parent_run_id 로 supersede chain
- regression diff 는 baseline 과 새 run 비교

lineage 관계:
- supersedes: 새 run 이 이전 run 을 대체 (rule fix 후 재실행)
- baseline_of: scenario 의 기준 run (회귀 비교 대상)
- regression_of: 회귀 검증을 위해 실행된 run
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import db as db_mod


@dataclass
class Run:
    id: str
    step_id: str
    inputs: dict
    outputs: Optional[dict] = None
    scenario_id: Optional[str] = None
    stage: Optional[str] = None
    error_code: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    is_baseline: bool = False
    parent_run_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "step_id": self.step_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "stage": self.stage,
            "error_code": self.error_code,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
            "is_baseline": self.is_baseline,
            "parent_run_id": self.parent_run_id,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        id=row["id"],
        scenario_id=row["scenario_id"],
        step_id=row["step_id"],
        inputs=json.loads(row["inputs_json"]) if row["inputs_json"] else {},
        outputs=json.loads(row["outputs_json"]) if row["outputs_json"] else None,
        stage=row["stage"],
        error_code=row["error_code"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        elapsed_ms=row["elapsed_ms"],
        is_baseline=bool(row["is_baseline"]),
        parent_run_id=row["parent_run_id"],
    )


def log_run(
    step_id: str,
    inputs: dict,
    outputs: Optional[dict] = None,
    *,
    scenario_id: Optional[str] = None,
    stage: Optional[str] = None,
    error_code: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    parent_run_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Run:
    """1회 sandbox 실행 기록 저장. parent_run_id 가 있으면 supersedes lineage 자동 추가."""
    now = _now_iso()
    run = Run(
        id=f"run-{uuid.uuid4().hex[:12]}",
        scenario_id=scenario_id,
        step_id=step_id,
        inputs=inputs,
        outputs=outputs,
        stage=stage or _infer_stage(outputs),
        error_code=error_code or _infer_error_code(outputs),
        started_at=now,
        completed_at=now if outputs is not None else None,
        elapsed_ms=elapsed_ms,
        is_baseline=False,
        parent_run_id=parent_run_id,
    )

    with db_mod.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (id, scenario_id, step_id, inputs_json, outputs_json,
                              stage, error_code, started_at, completed_at, elapsed_ms,
                              is_baseline, parent_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id, run.scenario_id, run.step_id,
                json.dumps(run.inputs, ensure_ascii=False, default=str),
                json.dumps(run.outputs, ensure_ascii=False, default=str) if run.outputs is not None else None,
                run.stage, run.error_code,
                run.started_at, run.completed_at, run.elapsed_ms,
                int(run.is_baseline), run.parent_run_id,
            ),
        )
        if parent_run_id:
            _insert_lineage(conn, parent_run_id, run.id, "supersedes", now)
    return run


def _infer_stage(outputs: Optional[dict]) -> Optional[str]:
    if not outputs:
        return None
    if "stage" in outputs:
        return outputs["stage"]
    if "error" in outputs:
        return "algorithm"
    return "ok"


def _infer_error_code(outputs: Optional[dict]) -> Optional[str]:
    if not outputs:
        return None
    err = outputs.get("error")
    if isinstance(err, dict):
        return err.get("error_code")
    return None


def list_runs(
    *,
    scenario_id: Optional[str] = None,
    step_id: Optional[str] = None,
    only_baseline: bool = False,
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> list[Run]:
    sql = "SELECT * FROM runs"
    args: list = []
    where = []
    if scenario_id:
        where.append("scenario_id = ?")
        args.append(scenario_id)
    if step_id:
        where.append("step_id = ?")
        args.append(step_id)
    if only_baseline:
        where.append("is_baseline = 1")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY started_at DESC LIMIT ?"
    args.append(int(limit))

    with db_mod.connect(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_row_to_run(r) for r in rows]


def get_run(run_id: str, *, db_path: Optional[Path] = None) -> Optional[Run]:
    with db_mod.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def register_baseline(
    run_id: str, *, scenario_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """run 을 baseline 으로 표시. scenario_id 가 주어지면 baseline_of lineage 추가."""
    now = _now_iso()
    with db_mod.connect(db_path) as conn:
        # 같은 scenario 내 이전 baseline 해제
        if scenario_id:
            conn.execute(
                "UPDATE runs SET is_baseline = 0 WHERE scenario_id = ? AND is_baseline = 1",
                (scenario_id,),
            )
        cur = conn.execute(
            "UPDATE runs SET is_baseline = 1 WHERE id = ?",
            (run_id,),
        )
        if scenario_id and cur.rowcount > 0:
            _insert_lineage(conn, run_id, run_id, "baseline_of", now)
    return cur.rowcount > 0


def get_baseline(scenario_id: str, *, db_path: Optional[Path] = None) -> Optional[Run]:
    with db_mod.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE scenario_id = ? AND is_baseline = 1 "
            "ORDER BY started_at DESC LIMIT 1",
            (scenario_id,),
        ).fetchone()
    return _row_to_run(row) if row else None


# ─── Lineage ─────────────────────────────────────────────────────────


def _insert_lineage(conn: sqlite3.Connection, frm: str, to: str, relation: str, when: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO lineage (from_run_id, to_run_id, relation, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (frm, to, relation, when),
    )


def get_lineage(run_id: str, *, db_path: Optional[Path] = None) -> dict:
    """run_id 를 중심으로 한 양방향 lineage 반환.

    Returns: {"upstream": [...], "downstream": [...]}
        upstream: 이 run 이 어떤 run 을 supersede 했는지 / baseline 등록 여부
        downstream: 이 run 을 supersede 한 후속 run 들
    """
    with db_mod.connect(db_path) as conn:
        upstream = conn.execute(
            "SELECT from_run_id, relation, created_at FROM lineage WHERE to_run_id = ?",
            (run_id,),
        ).fetchall()
        downstream = conn.execute(
            "SELECT to_run_id, relation, created_at FROM lineage WHERE from_run_id = ? AND from_run_id != to_run_id",
            (run_id,),
        ).fetchall()
    return {
        "upstream": [{"run_id": r["from_run_id"], "relation": r["relation"], "at": r["created_at"]} for r in upstream],
        "downstream": [{"run_id": r["to_run_id"], "relation": r["relation"], "at": r["created_at"]} for r in downstream],
    }


# ─── Regression diff ────────────────────────────────────────────────


def regression_diff(
    baseline_run_id: str, candidate_run_id: str, *,
    db_path: Optional[Path] = None,
) -> dict:
    """두 run 의 outputs 비교 → field-by-field 차이.

    레코드 lineage 에 regression_of 관계 추가.
    """
    base = get_run(baseline_run_id, db_path=db_path)
    cand = get_run(candidate_run_id, db_path=db_path)
    if base is None or cand is None:
        return {"error": "run not found", "baseline": baseline_run_id, "candidate": candidate_run_id}

    diffs = _diff_dicts(base.outputs or {}, cand.outputs or {})
    summary = {
        "stage_changed": (base.stage != cand.stage),
        "error_code_changed": (base.error_code != cand.error_code),
        "field_diffs": diffs,
        "diff_count": len(diffs),
    }

    now = _now_iso()
    with db_mod.connect(db_path) as conn:
        _insert_lineage(conn, baseline_run_id, candidate_run_id, "regression_of", now)

    return {
        "baseline": base.to_dict(),
        "candidate": cand.to_dict(),
        "summary": summary,
    }


def _diff_dicts(a: dict, b: dict, *, prefix: str = "") -> list[dict]:
    """플랫 diff. 중첩 dict 도 깊이 우선 펼침. 값이 다르면 (path, before, after) 출력."""
    diffs: list[dict] = []
    keys = set(a.keys()) | set(b.keys())
    for k in sorted(keys):
        path = f"{prefix}.{k}" if prefix else k
        av = a.get(k)
        bv = b.get(k)
        if isinstance(av, dict) and isinstance(bv, dict):
            diffs.extend(_diff_dicts(av, bv, prefix=path))
        elif av != bv:
            diffs.append({"path": path, "before": av, "after": bv})
    return diffs
