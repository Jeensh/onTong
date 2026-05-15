"""Verification Engine — Two-Engine 의 deterministic 측 (ADR-001 + ADR-002).

본 file = entry-point class skeleton. Anchored Twin Synthesizer / Twin Runner /
Oracle Differ / Trace Diff Analyzer 의 actual impl 은 별도 module (W3-W12 sprint).

Public API:
    - VerificationEngine — class implementing the Protocol from integrator/integrator.py
    - TwinSynthesizer / TwinRunner — Protocol (W4-W8 impl)
    - SyntheticTwin — synthesized Python twin reference

설계 (W3 skeleton, expand W4-W12):
- run_oracle(request) — FixtureRunner 호출 + aggregate_status 산출
- TwinSynthesizer = Java AST + ontology → Python code emit (ADR-001, plugin-specific override)
- TwinRunner = synthesized twin execute + trace collect
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    FixtureRunner,
    OracleRequest,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)


# ─────────────────────────────────────────────────────────────────────────────
# Synthesizer / runner Protocols (W4-W12 impl)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SyntheticTwin:
    """Synthesized Python twin reference.

    Result of TwinSynthesizer.synthesize(java_ast, ontology) — opaque handle.
    Future detail: emit_path, dispatch_kind_counts, contract_validator_result.
    """
    plugin:        str
    java_revision: str  # git tag / commit
    emit_path:     str  # filesystem path or in-memory blob ref
    metadata:      dict[str, Any]


class TwinSynthesizer(Protocol):
    """Java AST + ontology → Python twin. ADR-001 의 deterministic synthesis."""

    def synthesize(
        self,
        plugin: str,
        java_revision: str,
        apply_diffs: dict[str, Any] | None = None,
    ) -> SyntheticTwin:
        ...


class TwinRunner(Protocol):
    """Synthesized twin 실행 + trace + output 수집."""

    def run(
        self,
        twin: SyntheticTwin,
        fixture_id: str,
    ) -> "TwinRunResult":
        ...


@dataclass(frozen=True)
class TwinRunResult:
    fixture_id: str
    output:     Any
    trace:      list[dict[str, Any]]
    error:      str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# VerificationEngine — Integrator's VerificationEngine Protocol 구현
# ─────────────────────────────────────────────────────────────────────────────


class VerificationEngine:
    """Deterministic verification — Integrator 의 oracle 요청 수신.

    W3 skeleton: FixtureRunner 의존 (oracle 의 actual fixture run).
    W4-W12 expansion: TwinSynthesizer + TwinRunner 가 internal — synthesize 후 run.
    """

    def __init__(
        self,
        fixture_runner: FixtureRunner,
        plugin: str = "",
    ) -> None:
        self._fixture_runner = fixture_runner
        self._plugin = plugin

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        """Per-fixture run + aggregate.

        ADR-003 §4: 4-tier aggregate_status (PASS / FAIL_BREAKING / FAIL_DRIFT / INCONCLUSIVE).
        """
        apply_diffs = {
            "schema": request.apply_schema_diff,
            "code":   request.apply_code_diff,
            "ontology": request.apply_ontology_diff,
        }
        by_fixture: dict[str, FixtureOracleResult] = {}
        for fixture_id in request.fixture_subset:
            try:
                result = self._fixture_runner.run_fixture(
                    fixture_id=fixture_id,
                    plugin=self._plugin,
                    apply_diffs=apply_diffs,
                )
            except Exception as e:  # graceful — surface as ERROR
                result = FixtureOracleResult(
                    fixture_id=fixture_id,
                    java_baseline_output=None,
                    python_proposal_output=None,
                    output_diff=OutputDiff(is_equivalent=False),
                    trace_diff=TraceDiff(is_equivalent=False),
                    status="ERROR",
                    error=f"{type(e).__name__}: {e}",
                )
            by_fixture[fixture_id] = result

        status = aggregate_status_from_fixtures(by_fixture)
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture=by_fixture,
            aggregate_status=status,
            summary=f"{len(by_fixture)} fixture(s), status: {status}",
        )


__all__ = [
    "SyntheticTwin",
    "TwinRunResult",
    "TwinRunner",
    "TwinSynthesizer",
    "VerificationEngine",
]
