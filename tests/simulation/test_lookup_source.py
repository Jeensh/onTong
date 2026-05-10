"""LookupDataSource (spec 05 §3) — fixture_only 모드 검증.

scenario_fixture.lookups 의 row 를 in-memory 로 노출하는 LookupDataSource 의
get / list / validate 동작을 검증.

TDD — 본 테스트가 먼저, lookup_source.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations


# ─── 가짜 OntologyClient (TableSpec derive 검증용) ─────────────────


class FakeOntologyClient:
    """spec 05 §3.4 의 _derive_table_specs 가 기대하는 최소 인터페이스.

    실제 modeling 측 OntologyQueryClientImpl 와 같은 list_code_types(role=...) 메서드만 stub.
    """

    def __init__(self, code_types):
        self._code_types = code_types

    def list_code_types(self, role=None):
        if role is None:
            return list(self._code_types)
        return [ct for ct in self._code_types if ct.role == role]


class FakeCodeField:
    def __init__(self, slot_name, atomic_fqn=None, is_pk=False, drama_dna_kind=None):
        self.slot_name = slot_name
        self.atomic_fqn = atomic_fqn
        self.is_pk = is_pk
        self.drama_dna_kind = drama_dna_kind


class FakeCodeType:
    def __init__(self, fqn, fields, role="lookup_table"):
        self.fqn = fqn
        self.fields = fields
        self.role = role


def make_customer_std_spec():
    return FakeCodeType(
        fqn="scm.std.CustomerStd",
        fields=[
            FakeCodeField("customer_no", atomic_fqn="scm.shared.atomic.customer_no", is_pk=True),
            FakeCodeField("customer_name", atomic_fqn="scm.shared.atomic.customer_name", drama_dna_kind="alias"),
            FakeCodeField("thickness_min", atomic_fqn="scm.shared.atomic.thickness"),
            FakeCodeField("raw_java_only_field"),  # atomic_fqn 없음 → columns 에서 제외
        ],
    )


# ─── LookupDataSource ──────────────────────────────────────────────


def test_lookup_data_source_get_existing_row():
    """get(table_spec_fqn, pk) 로 단일 row 조회."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    fixture = {
        "lookups": {
            "scm.std.CustomerStd:7": {
                "pk": 7,
                "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "정XX", "thickness_min": 200},
            }
        }
    }
    client = FakeOntologyClient([make_customer_std_spec()])
    src = LookupDataSource(ontology_client=client, fixture=fixture)

    row = src.get("scm.std.CustomerStd", 7)
    assert row is not None
    assert row.pk == 7
    assert row.columns["customer_name"] == "정XX"


def test_lookup_data_source_get_missing_row_returns_none():
    """fixture 에 없는 PK → None (fixture_only 모드)."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    src = LookupDataSource(
        ontology_client=FakeOntologyClient([make_customer_std_spec()]),
        fixture={"lookups": {}},
    )
    assert src.get("scm.std.CustomerStd", 999) is None


def test_lookup_data_source_list_all_rows_of_table():
    """list(table_spec_fqn) — 그 테이블의 모든 row."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    fixture = {
        "lookups": {
            "scm.std.CustomerStd:7": {
                "pk": 7, "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "정XX"},
            },
            "scm.std.CustomerStd:8": {
                "pk": 8, "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "박XX"},
            },
        }
    }
    src = LookupDataSource(
        ontology_client=FakeOntologyClient([make_customer_std_spec()]),
        fixture=fixture,
    )

    rows = src.list("scm.std.CustomerStd")
    assert len(rows) == 2
    pks = sorted(r.pk for r in rows)
    assert pks == [7, 8]


def test_lookup_data_source_list_empty_for_unknown_table():
    """list(존재 안 하는 table) → 빈 리스트."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    src = LookupDataSource(
        ontology_client=FakeOntologyClient([make_customer_std_spec()]),
        fixture={"lookups": {}},
    )
    assert src.list("scm.std.Unknown") == []


def test_lookup_data_source_validate_no_warnings_for_clean_fixture():
    """validate() — 정상 fixture 는 warning 0건."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    fixture = {
        "lookups": {
            "scm.std.CustomerStd:7": {
                "pk": 7, "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "정XX"},
            }
        }
    }
    src = LookupDataSource(
        ontology_client=FakeOntologyClient([make_customer_std_spec()]),
        fixture=fixture,
    )
    warnings = src.validate()
    assert warnings == []


def test_lookup_data_source_validate_warns_for_unknown_table_spec_fqn():
    """validate() — fixture 에 unknown table_spec_fqn → warning."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    fixture = {
        "lookups": {
            "scm.std.Unknown:1": {
                "pk": 1, "table_spec_fqn": "scm.std.Unknown",
                "columns": {},
            }
        }
    }
    src = LookupDataSource(
        ontology_client=FakeOntologyClient([make_customer_std_spec()]),
        fixture=fixture,
    )
    warnings = src.validate()
    assert any("scm.std.Unknown" in w for w in warnings)


def test_lookup_data_source_table_specs_derived_from_ontology_client():
    """spec 05 §3.4 — _derive_table_specs 가 CodeType → TableSpec 매핑."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    src = LookupDataSource(
        ontology_client=FakeOntologyClient([make_customer_std_spec()]),
        fixture={"lookups": {}},
    )

    specs = src.table_specs()
    assert "scm.std.CustomerStd" in specs
    spec = specs["scm.std.CustomerStd"]
    # is_pk=True 첫 field 의 atomic_fqn 이 pk_atom_fqn
    assert spec.pk_atom_fqn == "scm.shared.atomic.customer_no"
    # atomic_fqn 매핑된 field 만 columns 에
    assert "customer_name" in spec.columns
    assert "raw_java_only_field" not in spec.columns
    # drama_dna_kind 마킹된 field → drama_dna_columns
    assert "customer_name" in spec.drama_dna_columns


def test_lookup_data_source_skips_code_type_without_pk():
    """is_pk=True field 없는 CodeType 은 TableSpec 으로 derive 안 됨 (spec 05 §3.4 step 2)."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    no_pk = FakeCodeType(
        fqn="scm.std.NoPk",
        fields=[FakeCodeField("name", atomic_fqn="scm.shared.atomic.name")],  # is_pk=False
    )
    src = LookupDataSource(
        ontology_client=FakeOntologyClient([no_pk]),
        fixture={"lookups": {}},
    )
    specs = src.table_specs()
    assert "scm.std.NoPk" not in specs


def test_lookup_data_source_phase_c_fixture_p_2018_0098():
    """spec 04 §6.3 P-2018-0098 회귀 fixture 가 LookupDataSource 로 정상 처리."""
    from backend.simulation.runner.lookup_source import LookupDataSource

    customer_spec = make_customer_std_spec()
    hr_spec_ct = FakeCodeType(
        fqn="scm.spec.HrSpec",
        fields=[
            FakeCodeField("hr_id", atomic_fqn="scm.shared.atomic.hr_id", is_pk=True),
            FakeCodeField("proc", atomic_fqn="scm.shared.atomic.proc"),
        ],
    )

    fixture = {
        "lookups": {
            "scm.std.CustomerStd:7": {
                "pk": 7, "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "정XX", "thickness_min": 200},
            },
            "scm.spec.HrSpec:HR-23-A": {
                "pk": "HR-23-A", "table_spec_fqn": "scm.spec.HrSpec",
                "columns": {"proc": "0HR23456"},
            },
        },
        "metadata": {"scenario_origin": "P-2018-0098"},
    }
    src = LookupDataSource(
        ontology_client=FakeOntologyClient([customer_spec, hr_spec_ct]),
        fixture=fixture,
    )
    cust = src.get("scm.std.CustomerStd", 7)
    hr = src.get("scm.spec.HrSpec", "HR-23-A")
    assert cust is not None and cust.columns["customer_name"] == "정XX"
    assert hr is not None and hr.columns["proc"] == "0HR23456"
    assert src.validate() == []
