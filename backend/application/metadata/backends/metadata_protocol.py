"""MetadataIndex backend protocol — opaque dict load/save."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


_EMPTY = {
    "domains": {}, "domain_processes": {}, "tags": {}, "untagged": [],
    "files": {}, "domain_files": {}, "process_files": {}, "tag_files": {},
    "status_files": {}, "supersedes_index": {}, "related_index": {},
}


def empty_default() -> dict[str, Any]:
    return {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in _EMPTY.items()}


class MetadataBackend(ABC):
    @abstractmethod
    def load(self) -> dict[str, Any]: ...

    @abstractmethod
    def save(self, data: dict[str, Any]) -> None: ...
