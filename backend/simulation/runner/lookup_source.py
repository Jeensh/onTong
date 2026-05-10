"""LookupDataSource (spec 05 §3) — scenario_fixture.lookups 를 in-memory 로 노출.

Section 3 시뮬에서 Java sandbox 가 DB 룩업처럼 호출하는 데이터 source.
spec 05 §3.5 의 3 mode 중 본 구현은 **fixture_only** 만 (첫 iteration).

향후 확장:
- fixture_with_db_fallback : fixture 미스 시 modeling 측 read-only DB
- db_snapshot              : scenario.metadata.snapshot_at 시점의 snapshot

본 모듈은 `backend.modeling.api.ontology_query.OntologyQueryClient` 의 facade 를
read-only 로 import — modeling internal layer 는 절대 import 안 함 (Section isolation).
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from backend.shared.contracts.simulation import LookupRow, TableSpec

logger = logging.getLogger(__name__)


# ─── 의존성 — OntologyClient duck-typed Protocol ───────────────────


class _OntologyClientProtocol(Protocol):
    """LookupDataSource 가 의존하는 최소 인터페이스.

    실제 구현은 modeling 측 OntologyQueryClientImpl. 본 Protocol 은 duck-typed —
    list_code_types(role=...) 메서드 하나만 사용 (spec 05 §3.4 _derive_table_specs).
    """

    def list_code_types(self, role: Optional[str] = None) -> list[Any]: ...


# ─── LookupDataSource ──────────────────────────────────────────────


class LookupDataSource:
    """scenario_fixture.lookups 의 row 를 sandbox 에 in-memory 로 제공.

    Constructor:
        ontology_client : modeling 측 facade (TableSpec derive 에 사용)
        fixture         : ChangeSpec.scenario_fixture 의 dict — {"lookups": {...}, "metadata": {...}}

    구조:
        self._table_specs : {code_type_fqn → TableSpec}
        self._rows        : {(table_spec_fqn, pk) → LookupRow}
    """

    def __init__(
        self,
        ontology_client: _OntologyClientProtocol,
        fixture: dict[str, Any],
    ):
        self._ont = ontology_client
        self._fixture = fixture
        self._table_specs: dict[str, TableSpec] = self._derive_table_specs(ontology_client)
        self._rows: dict[tuple[str, Any], LookupRow] = self._index_fixture(fixture)

    # ─── Public API ───────────────────────────────────────────────

    def get(self, table_spec_fqn: str, pk: Any) -> Optional[LookupRow]:
        """단일 row 조회 — sandbox 의 Java code 가 DB 룩업처럼 호출."""
        return self._rows.get((table_spec_fqn, pk))

    def list(self, table_spec_fqn: str) -> list[LookupRow]:
        """전체 lookup — Java code 의 list 형 룩업용."""
        return [r for (fqn, _pk), r in self._rows.items() if fqn == table_spec_fqn]

    def validate(self) -> list[str]:
        """fixture 가 derive 된 TableSpec 과 일치하는지 검증.

        Returns: warning 메시지 목록 (empty = OK).

        검증 항목 (첫 iteration):
        - fixture row 의 table_spec_fqn 이 derive 된 TableSpec 에 존재하는가
        - row 의 columns 가 TableSpec.columns 키에 포함되는가 (extra column 은 warn)

        향후 확장: atomic.facets (range_min/max/unit/enum) 로 값 검증.
        """
        warnings: list[str] = []
        for (table_spec_fqn, pk), row in self._rows.items():
            spec = self._table_specs.get(table_spec_fqn)
            if spec is None:
                warnings.append(
                    f"unknown table_spec_fqn '{table_spec_fqn}' for pk={pk!r} — "
                    "ontology_client.list_code_types() 가 이 TableSpec 을 알지 못함"
                )
                continue
            unknown_cols = set(row.columns.keys()) - set(spec.columns.keys())
            if unknown_cols:
                warnings.append(
                    f"row {table_spec_fqn}:{pk} 에 unknown column {sorted(unknown_cols)} — "
                    f"TableSpec.columns 에 정의되지 않음"
                )
        return warnings

    def table_specs(self) -> dict[str, TableSpec]:
        """derive 된 TableSpec 매핑 — debug / validation 용."""
        return dict(self._table_specs)

    def metadata(self) -> dict[str, Any]:
        """fixture.metadata — scenario_origin / snapshot_at 등."""
        return dict(self._fixture.get("metadata", {}))

    # ─── 내부 — TableSpec derive (spec 05 §3.4) ──────────────────

    @staticmethod
    def _derive_table_specs(client: _OntologyClientProtocol) -> dict[str, TableSpec]:
        """CodeType → TableSpec 매핑 자동 derive (spec 05 §3.4 step 1~4).

        1. role='lookup_table' 인 CodeType 후보 수집
        2. is_pk=True 첫 field 의 atomic_fqn 을 PK 로 사용 (없으면 skip)
        3. atomic_fqn 매핑된 field 만 columns 에 (raw java field 제외)
        4. drama_dna_kind 마킹된 field → drama_dna_columns
        """
        specs: dict[str, TableSpec] = {}
        try:
            candidates = client.list_code_types(role="lookup_table")
        except Exception as exc:
            logger.warning(
                "list_code_types(role='lookup_table') 호출 실패 — "
                "TableSpec derive 빈 결과 (%s)",
                exc,
            )
            return specs

        for ct in candidates:
            fields = getattr(ct, "fields", None) or []
            pk_field = next(
                (f for f in fields if getattr(f, "is_pk", False) and getattr(f, "atomic_fqn", None)),
                None,
            )
            if pk_field is None:
                logger.debug("CodeType %s skip — PK 없음", getattr(ct, "fqn", "?"))
                continue
            columns = {
                f.slot_name: f.atomic_fqn
                for f in fields
                if getattr(f, "atomic_fqn", None) is not None
            }
            drama = [
                f.slot_name
                for f in fields
                if getattr(f, "drama_dna_kind", None) is not None
            ]
            specs[ct.fqn] = TableSpec(
                code_type_fqn=ct.fqn,
                pk_atom_fqn=pk_field.atomic_fqn,
                columns=columns,
                drama_dna_columns=drama,
            )
        return specs

    # ─── 내부 — fixture 인덱싱 ──────────────────────────────────

    @staticmethod
    def _index_fixture(fixture: dict[str, Any]) -> dict[tuple[str, Any], LookupRow]:
        """fixture['lookups'] → {(table_spec_fqn, pk) → LookupRow}.

        lookup key 형식 (spec 04 §1.1): "{table_spec_fqn}:{pk}".
        row 는 {"pk", "table_spec_fqn", "columns"} 형식 (spec 05 §3.3).
        """
        rows: dict[tuple[str, Any], LookupRow] = {}
        lookups = fixture.get("lookups", {}) or {}
        for key, raw in lookups.items():
            if not isinstance(raw, dict):
                logger.warning("lookup key %s 의 value 가 dict 아님 — skip", key)
                continue
            try:
                row = LookupRow(
                    pk=raw["pk"],
                    table_spec_fqn=raw["table_spec_fqn"],
                    columns=raw.get("columns", {}),
                )
            except KeyError as missing:
                logger.warning("lookup key %s — 필수 필드 누락: %s", key, missing)
                continue
            rows[(row.table_spec_fqn, row.pk)] = row
        return rows


__all__ = ["LookupDataSource"]
