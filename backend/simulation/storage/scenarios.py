"""Phase 6-B — 시나리오 라이브러리.

CRUD + YAML 시드 로더. 시나리오 = step_id + inputs(YAML) + tags + source.

YAML 시드 위치: `backend/simulation/data/scenarios/*.yaml`
한 파일은 다음 형식:

```yaml
- id: scn-rule-hr-095
  name: "HR 실수율 0.95 → 0.92"
  description: "..."
  step_id: pipeline_full
  tags: [productivity, rule-change]
  inputs:
    rules:
      hr: "0.92"
- id: scn-edging-wildcard-missing
  name: "EDGING_SPEC '*' fallback 누락"
  ...
```
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from . import db as db_mod

_SEED_DIR = Path(__file__).parent.parent / "data" / "scenarios"


@dataclass
class Scenario:
    id: str
    name: str
    step_id: str
    inputs: dict
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    source: str = "user"  # 'yaml' / 'user' / 'auto'
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "step_id": self.step_id,
            "inputs": self.inputs,
            "tags": list(self.tags),
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_scenario(row: sqlite3.Row) -> Scenario:
    inputs = yaml.safe_load(row["inputs_yaml"]) or {}
    tags = [t for t in (row["tags"] or "").split(",") if t]
    return Scenario(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        step_id=row["step_id"],
        inputs=inputs,
        tags=tags,
        source=row["source"] or "user",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_scenarios(
    *, step_id: Optional[str] = None, tag: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> list[Scenario]:
    sql = "SELECT * FROM scenarios"
    args: list = []
    where = []
    if step_id:
        where.append("step_id = ?")
        args.append(step_id)
    if tag:
        where.append("tags LIKE ?")
        args.append(f"%{tag}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC"

    with db_mod.connect(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_row_to_scenario(r) for r in rows]


def get_scenario(scenario_id: str, *, db_path: Optional[Path] = None) -> Optional[Scenario]:
    with db_mod.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
    return _row_to_scenario(row) if row else None


def upsert_scenario(scn: Scenario, *, db_path: Optional[Path] = None) -> Scenario:
    """create-or-update. id 가 없으면 자동 생성."""
    if not scn.id:
        scn.id = f"scn-{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    if not scn.created_at:
        scn.created_at = now
    scn.updated_at = now

    inputs_yaml = yaml.safe_dump(scn.inputs, allow_unicode=True, sort_keys=False)
    tags = ",".join(scn.tags)

    with db_mod.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO scenarios (id, name, description, step_id, inputs_yaml, tags, source,
                                   created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                step_id = excluded.step_id,
                inputs_yaml = excluded.inputs_yaml,
                tags = excluded.tags,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                scn.id, scn.name, scn.description, scn.step_id,
                inputs_yaml, tags, scn.source,
                scn.created_at, scn.updated_at,
            ),
        )
    return scn


def delete_scenario(scenario_id: str, *, db_path: Optional[Path] = None) -> bool:
    with db_mod.connect(db_path) as conn:
        cur = conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
    return cur.rowcount > 0


# ─── YAML 시드 로더 ─────────────────────────────────────────────────


def load_yaml_seeds(
    *, seed_dir: Optional[Path] = None, db_path: Optional[Path] = None,
) -> int:
    """seed_dir 내 모든 .yaml 을 source='yaml' 로 upsert. 추가/갱신 건수 반환."""
    seed_dir = seed_dir or _SEED_DIR
    if not seed_dir.exists():
        return 0
    count = 0
    for yaml_file in sorted(seed_dir.glob("*.yaml")):
        with yaml_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, list):
            continue
        for item in data:
            scn = Scenario(
                id=item.get("id") or "",
                name=item["name"],
                description=item.get("description"),
                step_id=item["step_id"],
                inputs=item.get("inputs", {}) or {},
                tags=item.get("tags", []) or [],
                source="yaml",
            )
            upsert_scenario(scn, db_path=db_path)
            count += 1
    return count
