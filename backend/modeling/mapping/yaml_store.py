"""YAML read/write for mapping files."""
from __future__ import annotations

from pathlib import Path

import yaml

from backend.modeling.mapping.mapping_models import MappingFile


def load_mapping_yaml(path: Path) -> MappingFile:
    with open(path) as f:
        data = yaml.safe_load(f)
    return MappingFile(**data)


def save_mapping_yaml(path: Path, mf: MappingFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": mf.version,
        "repo_id": mf.repo_id,
        "mappings": [m.model_dump(exclude_none=True, mode="json") for m in mf.mappings],
    }
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
