"""v2 slab manufacturing 의 domain exception.

Lesson 1 §4.1 + ADR-002 — system-specific exception base.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlgorithmException(Exception):
    """Slab design algorithm 의 root exception.

    step_no / step_name / error_code triplet — Phase α 의 algorithm_exception.py 의
    contract 와 동등 의도. 단 새 plugin 에서는 generic Java contract base 와 isolation.
    """
    step_no:    int
    step_name:  str
    error_code: str
    detail:     str = ""

    def __post_init__(self) -> None:
        super().__init__(
            f"[step {self.step_no}: {self.step_name}] {self.error_code}: {self.detail}"
        )
