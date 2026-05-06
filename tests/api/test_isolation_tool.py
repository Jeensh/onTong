"""C5 isolation 도구 검증 — 가짜 agent 폴더 만들어 실험."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
TOOL = ROOT / "tools" / "check_agent_isolation.py"
AGENTS_DIR = ROOT / "backend" / "agents"


def _run() -> tuple[int, str]:
    res = subprocess.run(
        [sys.executable, str(TOOL)], capture_output=True, text=True, cwd=str(ROOT),
    )
    return res.returncode, (res.stdout + res.stderr)


class TestIsolationTool:
    def test_passes_when_no_agents(self):
        # AGENTS_DIR 가 없거나 비어 있어야
        if AGENTS_DIR.exists():
            shutil.rmtree(AGENTS_DIR)
        code, out = _run()
        assert code == 0
        assert "skip" in out.lower() or "위반 0" in out

    def test_passes_for_compliant_agent(self):
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        good = AGENTS_DIR / "good_agent"
        good.mkdir(exist_ok=True)
        (good / "__init__.py").write_text("")
        (good / "handler.py").write_text(
            "from backend.shared.contracts import OntologyQueryClient, TermDTO\n"
            "import json\n"
        )
        try:
            code, out = _run()
            assert code == 0, out
        finally:
            shutil.rmtree(AGENTS_DIR)

    def test_fails_for_internal_import(self):
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        bad = AGENTS_DIR / "bad_agent"
        bad.mkdir(exist_ok=True)
        (bad / "__init__.py").write_text("")
        (bad / "handler.py").write_text(
            "from backend.modeling.mapping_layer.store import MappingLayerStore\n"
        )
        try:
            code, out = _run()
            assert code == 1
            assert "mapping_layer" in out
        finally:
            shutil.rmtree(AGENTS_DIR)

    def test_fails_for_persistence_import(self):
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        bad = AGENTS_DIR / "leaky"
        bad.mkdir(exist_ok=True)
        (bad / "__init__.py").write_text("")
        (bad / "x.py").write_text(
            "from backend.modeling.persistence.database import session_scope\n"
        )
        try:
            code, out = _run()
            assert code == 1
            assert "persistence" in out
        finally:
            shutil.rmtree(AGENTS_DIR)
