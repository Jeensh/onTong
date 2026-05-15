"""Plugin loader test — manifest parse + structure validate + discovery."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from backend.sim_v2.core.plugin_loader import (
    PluginManifest,
    PluginValidationError,
    discover_plugins,
    load_plugin,
    parse_manifest,
    validate_plugin_structure,
)

PLUGINS_ROOT = Path(__file__).resolve().parents[2] / "plugins"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


VALID_MANIFEST = dedent("""
    [plugin]
    name = "test-plugin"
    version = "0.0.1"
    description = "A test plugin"

    [recommendation]
    default_provider = "claude"
    allowed_providers = ["claude", "openai"]
    max_retries = 2

    [extensions]
    dispatchers = ["test.fancy_dispatch"]
    annotations = []
    aop = []
    bytecode = []

    [schema]
    source = "jpa_annotation"

    [fixtures]
    ids = ["A1", "A2"]

    [contracts]
    domain_exception = "TestException"
""").strip()


def _write_manifest(plugin_dir: Path, content: str = VALID_MANIFEST) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "manifest.toml").write_text(content, encoding="utf-8")


def _scaffold_artifacts(plugin_dir: Path) -> None:
    """7 artifact 모두 생성."""
    for sub in ("contracts", "entities", "mappings", "emitters", "fixtures", "aspects"):
        (plugin_dir / sub).mkdir(exist_ok=True)


@pytest.fixture
def tmp_plugin(tmp_path: Path) -> Path:
    plugin_dir = tmp_path / "test-plugin"
    _write_manifest(plugin_dir)
    _scaffold_artifacts(plugin_dir)
    return plugin_dir


# ─────────────────────────────────────────────────────────────────────────────
# parse_manifest
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_valid_manifest(tmp_plugin: Path):
    manifest = parse_manifest(tmp_plugin / "manifest.toml")
    assert manifest.plugin.name == "test-plugin"
    assert manifest.plugin.version == "0.0.1"
    assert manifest.extensions.dispatchers == ["test.fancy_dispatch"]
    assert manifest.fixtures.ids == ["A1", "A2"]


def test_parse_missing_manifest(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        parse_manifest(tmp_path / "no-such.toml")


def test_parse_invalid_schema_kind(tmp_path: Path):
    plugin_dir = tmp_path / "bad"
    bad = VALID_MANIFEST.replace('source = "jpa_annotation"', 'source = "yaml_garbage"')
    _write_manifest(plugin_dir, bad)
    with pytest.raises(ValidationError):
        parse_manifest(plugin_dir / "manifest.toml")


def test_parse_extra_field_forbidden(tmp_path: Path):
    plugin_dir = tmp_path / "extra"
    bad = VALID_MANIFEST + '\n[unknown_section]\nfoo = "bar"\n'
    _write_manifest(plugin_dir, bad)
    with pytest.raises(ValidationError):
        parse_manifest(plugin_dir / "manifest.toml")


# ─────────────────────────────────────────────────────────────────────────────
# validate_plugin_structure
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_structure_complete(tmp_plugin: Path):
    missing = validate_plugin_structure(tmp_plugin)
    assert missing == []


def test_validate_structure_missing_emitters(tmp_path: Path):
    plugin_dir = tmp_path / "incomplete"
    _write_manifest(plugin_dir)
    # Create 5 of 6 artifact dirs (skip emitters)
    for sub in ("contracts", "entities", "mappings", "fixtures", "aspects"):
        (plugin_dir / sub).mkdir()
    missing = validate_plugin_structure(plugin_dir)
    assert any("emitters" in m for m in missing)


def test_validate_structure_missing_manifest(tmp_path: Path):
    plugin_dir = tmp_path / "no-manifest"
    plugin_dir.mkdir()
    _scaffold_artifacts(plugin_dir)
    missing = validate_plugin_structure(plugin_dir)
    assert any("manifest.toml" in m for m in missing)


# ─────────────────────────────────────────────────────────────────────────────
# load_plugin
# ─────────────────────────────────────────────────────────────────────────────


def test_load_plugin_complete(tmp_plugin: Path):
    info = load_plugin(tmp_plugin, strict=True)
    assert info.loaded
    assert info.name == "test-plugin"
    assert info.path == tmp_plugin


def test_load_plugin_strict_raises_on_missing(tmp_path: Path):
    plugin_dir = tmp_path / "partial"
    _write_manifest(plugin_dir)
    (plugin_dir / "contracts").mkdir()  # only 1 of 6 artifact dirs
    with pytest.raises(PluginValidationError, match="missing required artifacts"):
        load_plugin(plugin_dir, strict=True)


def test_load_plugin_non_strict_skips_validation(tmp_path: Path):
    plugin_dir = tmp_path / "partial"
    _write_manifest(plugin_dir)
    (plugin_dir / "contracts").mkdir()
    info = load_plugin(plugin_dir, strict=False)
    assert info.loaded
    assert info.name == "test-plugin"


def test_load_plugin_unknown_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_plugin(tmp_path / "no-such-dir")


# ─────────────────────────────────────────────────────────────────────────────
# discover_plugins
# ─────────────────────────────────────────────────────────────────────────────


def test_discover_plugins_finds_all(tmp_path: Path):
    p1 = tmp_path / "plugin-a"
    p2 = tmp_path / "plugin-b"
    _write_manifest(p1, VALID_MANIFEST.replace("test-plugin", "plugin-a"))
    _scaffold_artifacts(p1)
    _write_manifest(p2, VALID_MANIFEST.replace("test-plugin", "plugin-b"))
    _scaffold_artifacts(p2)

    discovered = discover_plugins(tmp_path, strict=True)
    assert set(discovered.keys()) == {"plugin-a", "plugin-b"}


def test_discover_plugins_skips_non_plugin_dirs(tmp_path: Path):
    plugin = tmp_path / "real"
    _write_manifest(plugin, VALID_MANIFEST.replace("test-plugin", "real"))
    _scaffold_artifacts(plugin)
    (tmp_path / "garbage").mkdir()  # no manifest.toml
    (tmp_path / "loose-file.txt").write_text("hi")

    discovered = discover_plugins(tmp_path, strict=False)
    assert list(discovered.keys()) == ["real"]


def test_discover_plugins_duplicate_name(tmp_path: Path):
    p1 = tmp_path / "dir-a"
    p2 = tmp_path / "dir-b"
    _write_manifest(p1)  # both have name "test-plugin"
    _scaffold_artifacts(p1)
    _write_manifest(p2)
    _scaffold_artifacts(p2)
    with pytest.raises(PluginValidationError, match="duplicate plugin name"):
        discover_plugins(tmp_path, strict=True)


# ─────────────────────────────────────────────────────────────────────────────
# Real v2 plugin (integration)
# ─────────────────────────────────────────────────────────────────────────────


def test_load_real_v2_plugin():
    plugin_dir = PLUGINS_ROOT / "v2_slab_design"
    assert plugin_dir.is_dir(), f"v2_slab_design plugin missing at {plugin_dir}"
    info = load_plugin(plugin_dir, strict=True)
    assert info.name == "v2-slab-design"
    assert info.manifest.fixtures.ids == ["S1", "S2", "S3", "S4", "S5"]
    assert info.manifest.contracts.domain_exception == "AlgorithmException"


def test_discover_finds_real_v2():
    discovered = discover_plugins(PLUGINS_ROOT, strict=True)
    assert "v2-slab-design" in discovered
