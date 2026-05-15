"""Plugin loader — manifest.toml parser + plugin discovery + extension registration.

ADR-002 (plugin contract) + ADR-013 (extensibility).

Public API:
    - PluginManifest — pydantic model (manifest.toml 의 정형)
    - PluginInfo — discovered plugin metadata + load state
    - PluginLoader — discovery / loading / validation
    - load_plugin(path) — single plugin load
    - discover_plugins(root) — iterate plugins/ dir

Manifest format (ADR-002 + V2-MIGRATION.md §4.1):
    [plugin]
    name = "v2-slab-design"
    version = "0.1.0"
    description = "..."

    [recommendation]
    default_provider = "claude"
    allowed_providers = ["claude", "openai", "gemini"]
    max_retries = 3

    [extensions]
    dispatchers = []
    annotations = []
    aop = []
    bytecode = []

    [schema]
    source = "jpa_annotation"

    [fixtures]
    ids = ["S1", "S2", ...]

    [contracts]
    domain_exception = "AlgorithmException"
    numeric_convention = "decimal64_halfeven"
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Manifest schema
# ─────────────────────────────────────────────────────────────────────────────


class PluginCore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name:        str
    version:     str
    description: str = ""


class RecommendationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    default_provider:  str = "claude"
    default_model:     str | None = None
    allowed_providers: list[str] = Field(default_factory=lambda: ["claude"])
    max_retries:       int = 3


class ExtensionsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dispatchers: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)
    aop:         list[str] = Field(default_factory=list)
    bytecode:    list[str] = Field(default_factory=list)


class SchemaConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: Literal["jpa_annotation", "hibernate_xml", "ddl_file", "liquibase", "flyway"]


class FixturesConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    ids: list[str] = Field(default_factory=list)


class ContractsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    domain_exception:     str | None = None
    numeric_convention:   str | None = None
    domain_namespace_class: str | None = None


class PluginManifest(BaseModel):
    """Parsed manifest.toml — top-level.

    `schema_config` is the Python attribute name; TOML key is still `[schema]`
    via pydantic alias — avoids shadowing BaseModel.schema (deprecated v2 method).
    """
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    plugin:         PluginCore
    recommendation: RecommendationConfig = Field(default_factory=RecommendationConfig)
    extensions:     ExtensionsConfig = Field(default_factory=ExtensionsConfig)
    schema_config:  SchemaConfig | None = Field(default=None, alias="schema")
    fixtures:       FixturesConfig = Field(default_factory=FixturesConfig)
    contracts:      ContractsConfig = Field(default_factory=ContractsConfig)


# ─────────────────────────────────────────────────────────────────────────────
# Plugin info + loader
# ─────────────────────────────────────────────────────────────────────────────


class PluginValidationError(ValueError):
    """Raised when plugin structure violates the 7-artifact contract."""


@dataclass
class PluginInfo:
    name:     str
    path:     Path
    manifest: PluginManifest
    loaded:   bool = False


# 7 artifact 의 directory / file 이름 — ADR-002
_REQUIRED_ARTIFACTS = {
    "contracts": "dir",   # contracts/
    "entities":  "dir",
    "mappings":  "dir",
    "emitters":  "dir",
    "fixtures":  "dir",
    "aspects":   "dir",
    "manifest":  "manifest.toml",  # file
}


def parse_manifest(manifest_path: Path) -> PluginManifest:
    """manifest.toml → PluginManifest. 누락 / type mismatch → pydantic ValidationError."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.toml not found: {manifest_path}")
    with manifest_path.open("rb") as f:
        data = tomllib.load(f)
    return PluginManifest.model_validate(data)


def validate_plugin_structure(plugin_dir: Path) -> list[str]:
    """7 artifact 의 directory / file 존재 확인. 누락 list 반환 (empty = OK)."""
    missing: list[str] = []
    for name, kind in _REQUIRED_ARTIFACTS.items():
        if kind == "dir":
            target = plugin_dir / name
            if not target.is_dir():
                missing.append(f"{name}/ (directory)")
        else:
            target = plugin_dir / kind
            if not target.is_file():
                missing.append(kind)
    return missing


def load_plugin(plugin_dir: Path, *, strict: bool = True) -> PluginInfo:
    """plugin directory → PluginInfo. strict=True 시 7 artifact 위반에 raise."""
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"plugin directory not found: {plugin_dir}")

    manifest = parse_manifest(plugin_dir / "manifest.toml")

    missing = validate_plugin_structure(plugin_dir)
    if missing and strict:
        raise PluginValidationError(
            f"plugin {manifest.plugin.name!r} missing required artifacts: "
            + ", ".join(missing)
        )

    # Extension registration (ADR-013) — import each declared extension submodule.
    # The submodule's __init__.py is expected to call register_*() functions.
    plugin_pkg = _resolve_plugin_package(plugin_dir)
    for category in ("dispatchers", "annotations", "aop", "bytecode"):
        declared = getattr(manifest.extensions, category)
        if declared and plugin_pkg is not None:
            try:
                importlib.import_module(f"{plugin_pkg}.{category}")
            except ImportError:
                # Skip if extension submodule missing — registered on first actual use.
                pass

    return PluginInfo(
        name=manifest.plugin.name,
        path=plugin_dir,
        manifest=manifest,
        loaded=True,
    )


def _resolve_plugin_package(plugin_dir: Path) -> str | None:
    """Convert filesystem path → Python package name.

    e.g., /<root>/backend/sim_v2/plugins/v2-slab-design/
        → backend.sim_v2.plugins.v2-slab-design (but dashes invalid in import...)

    Returns None if not importable (e.g., name contains dash).
    """
    # Walk up to find a 'backend' or top-level package ancestor.
    for parent in plugin_dir.parents:
        if (parent / "__init__.py").is_file():
            continue
        break
    # Construct relative path from project-ish root.
    try:
        idx = plugin_dir.parts.index("backend")
    except ValueError:
        return None
    parts = plugin_dir.parts[idx:]
    if any("-" in p for p in parts):
        # Python doesn't allow dashes in module names — use importlib spec approach instead
        return None
    return ".".join(parts)


def discover_plugins(plugins_root: Path, *, strict: bool = False) -> dict[str, PluginInfo]:
    """plugins/ 디렉토리 내 모든 plugin 발견."""
    if not plugins_root.is_dir():
        raise FileNotFoundError(f"plugins root not found: {plugins_root}")

    discovered: dict[str, PluginInfo] = {}
    for child in plugins_root.iterdir():
        if not child.is_dir():
            continue
        if not (child / "manifest.toml").is_file():
            continue
        info = load_plugin(child, strict=strict)
        if info.name in discovered:
            raise PluginValidationError(
                f"duplicate plugin name {info.name!r} at {child} (also at {discovered[info.name].path})"
            )
        discovered[info.name] = info
    return discovered


__all__ = [
    "ContractsConfig",
    "ExtensionsConfig",
    "FixturesConfig",
    "PluginCore",
    "PluginInfo",
    "PluginManifest",
    "PluginValidationError",
    "RecommendationConfig",
    "SchemaConfig",
    "discover_plugins",
    "load_plugin",
    "parse_manifest",
    "validate_plugin_structure",
]
