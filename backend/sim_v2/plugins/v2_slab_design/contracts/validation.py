"""v2 의 ValidationResult — Java 의 builder pattern 의 Python mirror.

Lesson 1 §4.1 — namespace class + builder pattern 의 first-class contract.
Phase α 의 ValidationResult 미구현 (Lesson 1 mismatch #5) 의 정식 대응.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ValidationStatus = Literal["VALID", "INVALID", "WARN"]


@dataclass(frozen=True)
class ValidationFailure:
    field_path: str
    code:       str
    message:    str = ""


@dataclass
class ValidationResult:
    """Java ValidationResult 의 Python equivalent.

    Builder pattern: `ValidationResult.fail(...)` / `.ok()` / `.warn(...)`.
    """
    status:   ValidationStatus
    failures: list[ValidationFailure] = field(default_factory=list)
    warnings: list[ValidationFailure] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(status="VALID")

    @classmethod
    def fail(cls, field_path: str, code: str, message: str = "") -> "ValidationResult":
        return cls(
            status="INVALID",
            failures=[ValidationFailure(field_path=field_path, code=code, message=message)],
        )

    @classmethod
    def warn(cls, field_path: str, code: str, message: str = "") -> "ValidationResult":
        return cls(
            status="WARN",
            warnings=[ValidationFailure(field_path=field_path, code=code, message=message)],
        )

    def is_valid(self) -> bool:
        return self.status == "VALID"

    def combine(self, other: "ValidationResult") -> "ValidationResult":
        combined_failures = [*self.failures, *other.failures]
        combined_warnings = [*self.warnings, *other.warnings]
        if combined_failures:
            new_status: ValidationStatus = "INVALID"
        elif combined_warnings:
            new_status = "WARN"
        else:
            new_status = "VALID"
        return ValidationResult(
            status=new_status,
            failures=combined_failures,
            warnings=combined_warnings,
        )
