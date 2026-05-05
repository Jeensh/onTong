"""ontong CLI migrate test."""
from __future__ import annotations

import subprocess


def test_help_lists_migrate():
    r = subprocess.run(
        ["/Users/donghae/workspace/ai/onTong/.venv/bin/python", "-m", "backend.cli", "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "migrate" in r.stdout


def test_migrate_help_lists_subcommands():
    r = subprocess.run(
        ["/Users/donghae/workspace/ai/onTong/.venv/bin/python", "-m", "backend.cli", "migrate", "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "db-upgrade" in r.stdout
    assert "refindex-build" in r.stdout
