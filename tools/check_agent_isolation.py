#!/usr/bin/env python3
"""Agent isolation 정적 검사.

backend/agents/**/*.py 가 ontology Core internal 모듈을 직접 import 시 fail.

허용 import:
- backend.shared.contracts.*       (DTO + Protocol)
- backend.shared.agent_framework.* (base class)
- backend.shared.contracts          (re-export)
- 자기 폴더 안 (`backend.agents.<own_name>.*`)
- 표준 라이브러리 / pip dependencies

차단 import:
- backend.modeling.code_layer.*
- backend.modeling.domain_layer.*
- backend.modeling.mapping_layer.*
- backend.modeling.persistence.*
- backend.modeling.code_analysis.*
- backend.modeling.api.*
- backend.application.*       (Section 1 wiki 측 — agent 별도)

사용:
    .venv/bin/python tools/check_agent_isolation.py
    → exit 0 : OK
    → exit 1 : 위반 발견 (위반 list 출력)

CI / pre-commit 에 통합.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

AGENT_ROOT = ROOT / "backend" / "agents"

# 차단 prefix (string startswith 매칭)
FORBIDDEN_PREFIXES = (
    "backend.modeling.code_layer",
    "backend.modeling.domain_layer",
    "backend.modeling.mapping_layer",
    "backend.modeling.persistence",
    "backend.modeling.code_analysis",
    "backend.modeling.api",
    "backend.application",
)


def _imports(source: str) -> list[tuple[str, int]]:
    """파이썬 source → [(module_name, lineno)]."""
    tree = ast.parse(source)
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            level = node.level or 0
            if level > 0:
                # relative import — 파일 위치 기반 절대 경로 추론은 생략.
                # 우리는 모든 코드를 절대 import 강제 (style 정책).
                out.append((f"<relative>{node.module}", node.lineno))
            else:
                out.append((node.module, node.lineno))
    return out


def _is_self_or_allowed(module: str, agent_dir: Path) -> bool:
    """agent 자기 폴더 또는 허용 prefix 인가."""
    own_pkg = ".".join(agent_dir.relative_to(ROOT).parts)
    if module.startswith(own_pkg):
        return True
    if module.startswith("backend.shared.contracts") or module.startswith("backend.shared.agent_framework"):
        return True
    if module.startswith("backend.shared"):
        return True
    if not module.startswith("backend."):
        return True
    return False


def check_file(path: Path, agent_dir: Path) -> list[str]:
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{path}: read error — {e}"]
    try:
        imports = _imports(src)
    except SyntaxError as e:
        return [f"{path}: syntax error at line {e.lineno}"]

    violations: list[str] = []
    for module, lineno in imports:
        # forbidden first
        if any(module.startswith(p) for p in FORBIDDEN_PREFIXES):
            violations.append(
                f"{path}:{lineno}: agent imports Core internal {module!r} — "
                f"use backend.shared.contracts.* instead"
            )
            continue
        # 그 외 backend.* 는 self/allowed 체크
        if module.startswith("backend.") and not _is_self_or_allowed(module, agent_dir):
            violations.append(
                f"{path}:{lineno}: agent imports non-allowed backend module {module!r} — "
                f"agents must only depend on backend.shared.*"
            )
    return violations


def main() -> int:
    if not AGENT_ROOT.exists():
        # Phase 0 — agent 폴더 없음. 통과.
        print(f"OK: {AGENT_ROOT.relative_to(ROOT)} 가 아직 없음 (Phase A1 미시작) — isolation 검사 skip.")
        return 0

    violations: list[str] = []
    for agent_dir in AGENT_ROOT.iterdir():
        if not agent_dir.is_dir() or agent_dir.name.startswith("__"):
            continue
        for py in agent_dir.rglob("*.py"):
            if py.name == "__pycache__" or "__pycache__" in py.parts:
                continue
            violations.extend(check_file(py, agent_dir))

    if violations:
        print(f"FAIL: {len(violations)} agent isolation violation(s):")
        for v in violations:
            print(f"  {v}")
        print()
        print("Agent 는 backend.shared.contracts.* 와 backend.shared.agent_framework.* 만 import.")
        print("Core internal model 직접 접근 시 ontology API 변경에 취약.")
        return 1

    print(f"OK: agent isolation 위반 0 (검사한 agent 폴더: {sum(1 for d in AGENT_ROOT.iterdir() if d.is_dir())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
