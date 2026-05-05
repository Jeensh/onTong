"""ontong migrate refindex-build tests."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


VENV = "/Users/donghae/workspace/ai/onTong/.venv/bin/python"


@pytest.fixture
def tmp_wiki(tmp_path, monkeypatch):
    """Build a tmp wiki directory with a few documents."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "alpha.md").write_text(
        """---
related:
  - beta.md
  - missing.md
---
# Alpha

See [link](beta.md) and [[gamma]].
""",
        encoding="utf-8",
    )
    (wiki / "beta.md").write_text(
        """---
related:
  - alpha.md
---
# Beta

[back to alpha](alpha.md)
""",
        encoding="utf-8",
    )
    (wiki / "_skills").mkdir()
    (wiki / "_skills" / "skill.md").write_text(
        "# Skill\n[link](alpha.md)\n",  # should be skipped
        encoding="utf-8",
    )
    return wiki


def test_refindex_build_creates_index_with_refs(tmp_wiki, tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    monkeypatch.setenv("WIKI_DIR", str(tmp_wiki))

    cwd = "/Users/donghae/workspace/ai/onTong/.worktrees/phase0-rename-concurrency"
    r = subprocess.run(
        [VENV, "-m", "backend.cli", "migrate", "refindex-build", "--batch", "10"],
        capture_output=True, text=True, cwd=cwd,
        env={**os.environ, "ONTONG_PROFILE": "dev", "WIKI_DIR": str(tmp_wiki)},
    )
    assert r.returncode == 0, f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    assert "Done:" in r.stdout
    # Should report 2 files (skip _skills)
    assert "2 files" in r.stdout

    # Verify the SQLite file was created
    db_path = tmp_wiki / ".ontong" / "refs.db"
    assert db_path.exists()

    # Open the index directly to verify content
    from backend.core.backends import _reset_for_test
    _reset_for_test()
    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    idx = SqliteRefIndex(str(db_path))
    out_alpha = idx.outbound("alpha.md")
    targets = sorted(r.target_path for r in out_alpha)
    assert "beta.md" in targets
    assert "missing.md" in targets
    assert "gamma" in targets

    # Skipped system path
    assert idx.outbound("_skills/skill.md") == []


def test_refindex_build_reset_clears_first(tmp_wiki, tmp_path, monkeypatch):
    """--reset clears the index before rebuilding."""
    cwd = "/Users/donghae/workspace/ai/onTong/.worktrees/phase0-rename-concurrency"
    env = {**os.environ, "ONTONG_PROFILE": "dev", "WIKI_DIR": str(tmp_wiki)}

    # First build
    subprocess.run([VENV, "-m", "backend.cli", "migrate", "refindex-build"], capture_output=True, env=env, cwd=cwd)

    # Add a stale row directly
    from backend.core.backends import _reset_for_test
    _reset_for_test()
    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    from backend.application.refindex.extractor import Reference, RefKind
    db_path = tmp_wiki / ".ontong" / "refs.db"
    idx = SqliteRefIndex(str(db_path))
    idx.upsert_for_source("stale.md", [
        Reference(source_path="stale.md", target_path="x.md", kind=RefKind.BODY_MD_LINK,
                  location={"offset": 0, "length": 4, "raw": "x.md"})
    ])
    assert len(idx.outbound("stale.md")) == 1

    # Rebuild with --reset
    r = subprocess.run(
        [VENV, "-m", "backend.cli", "migrate", "refindex-build", "--reset"],
        capture_output=True, text=True, env=env, cwd=cwd,
    )
    assert r.returncode == 0
    assert "RefIndex cleared" in r.stdout

    _reset_for_test()
    idx2 = SqliteRefIndex(str(db_path))
    assert idx2.outbound("stale.md") == []
    assert len(idx2.outbound("alpha.md")) > 0
