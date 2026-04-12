"""Language-agnostic code parser protocol and shared entity types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable
from pathlib import Path


class EntityKind(str, Enum):
    PACKAGE = "package"
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    METHOD = "method"
    FIELD = "field"
    CONSTRUCTOR = "constructor"


class RelationKind(str, Enum):
    CONTAINS = "contains"          # package->class, class->method
    CALLS = "calls"                # method->method
    EXTENDS = "extends"            # class->class
    IMPLEMENTS = "implements"      # class->interface
    DEPENDS_ON = "depends_on"     # class->class (import)
    READS = "reads"                # method->field
    WRITES = "writes"              # method->field


@dataclass(frozen=True)
class CodeEntity:
    """A single code element extracted by a parser."""
    kind: EntityKind
    qualified_name: str            # e.g., "com.client.inventory.SafetyStockCalculator"
    name: str                      # e.g., "SafetyStockCalculator"
    file_path: str                 # relative path in repo
    line_start: int
    line_end: int
    modifiers: list[str] = field(default_factory=list)   # public, static, abstract, etc.
    parent: str | None = None      # qualified name of containing entity


@dataclass(frozen=True)
class CodeRelation:
    """A directed relationship between two code entities."""
    kind: RelationKind
    source: str                    # qualified name
    target: str                    # qualified name
    file_path: str | None = None   # where the relation was found
    line: int | None = None


@dataclass
class ParseResult:
    """Output of parsing a single file."""
    entities: list[CodeEntity]
    relations: list[CodeRelation]
    file_path: str
    language: str
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class CodeParser(Protocol):
    """Language-specific parser plugin interface."""

    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles (e.g., ['.java'])."""
        ...

    def language_name(self) -> str:
        """Human-readable language name (e.g., 'Java')."""
        ...

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        """Parse a single source file into entities and relations."""
        ...
