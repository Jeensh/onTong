# ADR-004: Schema Layer — 5번째 Ontology DDL + Migration Plan

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13)
선행: ADR-002 (Two-Engine + plugin)
관련: ADR-003 (Integrator), ADR-005 (Recommendation)
관련 결정: D4 (Schema Layer migration 시점 = spec 직후 즉시)

## 컨텍스트

ADR-002 의 D2 (Recommendation Engine) 가 UC4 (스키마 추천) 를 1급 use case 로 추가. 이는 ontology 의 4-layer (Code / Domain / Mapping / Simulation, 메모리 `project_decisions_v4_action.md` 참조) 외 **5번째 layer (Schema)** 필요.

DECISIONS-CONFIRMED.md 의 D4:
- 선택: spec 직후 즉시
- 의미: Additive only — risk 낮음. Spec 이 schema-ready 상태로 출발.

## 결정

**Ontology 에 Schema Layer 추가. Schema entity + Schema↔Code mapping. Migration 은 additive only, 기존 4 layer 변경 X.**

### 1. Schema Layer entity model

```
SchemaArtifact (5번째 layer)
├── Table — 물리 table
│   ├── name, schema_name, comment
│   └── columns: list[Column]
├── Column
│   ├── name, sql_type, nullable, default_expr
│   └── constraints (PK, FK, unique, check)
├── Index — secondary index
├── Constraint — FK / unique / check
├── ViewDef — DB view 정의
└── MigrationRevision — DDL version (Liquibase / Flyway style)
```

### 2. DDL (SQLite, ontology.db 의 추가 table)

```sql
-- ontology.db (SQLite)

CREATE TABLE schema_table (
    id INTEGER PRIMARY KEY,
    plugin TEXT NOT NULL,        -- "v2-slab-design", "broadleaf", "banking"
    schema_name TEXT,
    table_name TEXT NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (plugin, schema_name, table_name)
);

CREATE TABLE schema_column (
    id INTEGER PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES schema_table(id),
    column_name TEXT NOT NULL,
    sql_type TEXT NOT NULL,
    nullable INTEGER NOT NULL DEFAULT 1,
    default_expr TEXT,
    comment TEXT,
    ordinal INTEGER NOT NULL,
    UNIQUE (table_id, column_name)
);

CREATE TABLE schema_constraint (
    id INTEGER PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES schema_table(id),
    kind TEXT NOT NULL CHECK (kind IN ('PK', 'FK', 'UNIQUE', 'CHECK')),
    name TEXT,
    columns_json TEXT NOT NULL,  -- JSON array of column names
    fk_target_table_id INTEGER REFERENCES schema_table(id),
    fk_target_columns_json TEXT,
    check_expr TEXT,
    UNIQUE (table_id, kind, name)
);

CREATE TABLE schema_index (
    id INTEGER PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES schema_table(id),
    index_name TEXT NOT NULL,
    columns_json TEXT NOT NULL,
    unique_flag INTEGER NOT NULL DEFAULT 0,
    UNIQUE (table_id, index_name)
);

CREATE TABLE schema_view (
    id INTEGER PRIMARY KEY,
    plugin TEXT NOT NULL,
    view_name TEXT NOT NULL,
    definition_sql TEXT NOT NULL,
    UNIQUE (plugin, view_name)
);

CREATE TABLE schema_migration (
    id INTEGER PRIMARY KEY,
    plugin TEXT NOT NULL,
    version TEXT NOT NULL,        -- "1.0.0", "1.0.1", semantic versioning
    description TEXT,
    forward_ddl TEXT NOT NULL,    -- migration DDL
    backward_ddl TEXT,            -- rollback DDL (optional)
    applied_at TIMESTAMP,
    UNIQUE (plugin, version)
);
```

### 3. Schema↔Code mapping

Schema layer 가 code layer (Java JPO / Spring Data entity) 와 양방향 매핑:

```sql
CREATE TABLE schema_code_mapping (
    id INTEGER PRIMARY KEY,
    schema_table_id INTEGER REFERENCES schema_table(id),
    schema_column_id INTEGER REFERENCES schema_column(id),
    code_entity_id INTEGER REFERENCES code_entity(id),  -- 기존 Code Layer 의 entity
    code_field_id INTEGER,
    mapping_kind TEXT CHECK (mapping_kind IN ('table_to_class', 'column_to_field', 'fk_to_relation')),
    notes TEXT
);
```

`code_entity` 는 기존 4-layer 의 Code Layer 의 table — 변경 X.

### 4. Schema↔Domain mapping

Domain BusinessTerm (메모리 `project_decisions_v4_action.md` 의 D2) 도 schema 와 매핑 가능:

```sql
CREATE TABLE schema_domain_mapping (
    id INTEGER PRIMARY KEY,
    schema_table_id INTEGER REFERENCES schema_table(id),
    schema_column_id INTEGER REFERENCES schema_column(id),
    domain_term_id INTEGER REFERENCES business_term(id),
    notes TEXT
);
```

이는 UC4 (스키마 추천) 의 핵심 reasoning input — "feature X" 의 domain term 이 어느 schema artifact 와 연결되는지 추적.

### 5. Migration plan (Additive only, D4 일관)

기존 4 layer (Code / Domain / Mapping / Simulation) 의 table 은 **변경 X**. 새 Schema Layer table 만 추가.

```
Migration sequence (v5.0.0):
  1. CREATE TABLE schema_table
  2. CREATE TABLE schema_column
  3. CREATE TABLE schema_constraint
  4. CREATE TABLE schema_index
  5. CREATE TABLE schema_view
  6. CREATE TABLE schema_migration
  7. CREATE TABLE schema_code_mapping
  8. CREATE TABLE schema_domain_mapping

Rollback: DROP TABLE 8 tables (idempotent)
```

기존 4-layer 의 데이터 손실 risk 0. Migration 은 단순 DDL.

### 6. Schema Layer 의 source 추출

각 plugin 의 schema 정보를 어디서 가져오는가?

| Plugin | Schema source |
|---|---|
| v2-slab-design | Java JPA entity → @Table / @Column 직접 추출 |
| broadleaf | Broadleaf 의 `*.hbm.xml` (Hibernate XML) + JPA annotation 혼용 |
| banking | 우리가 설계 → DDL 직접 작성 + JPA mapping |

Plugin 의 `schema_extractor.py` (extension point, ADR-013) 가 plugin-specific source 에서 schema artifact 를 ontology 에 import.

### 7. Schema diff (Proposal 의 변경 candidate)

ADR-003 의 SchemaDiff:

```python
class SchemaDiff(BaseModel):
    plugin: str
    migration_version: str  # 다음 버전

    new_tables: list[TableDef]
    altered_tables: list[TableAlteration]  # add column, drop column, alter type, etc.
    new_indexes: list[IndexDef]
    dropped_indexes: list[str]
    new_constraints: list[ConstraintDef]
    dropped_constraints: list[str]

    forward_ddl: str   # generated DDL
    backward_ddl: str | None
```

UC4 의 LLM output → SchemaDiff. Integrator (ADR-003) 가 receive → oracle.

### 8. 검증 (R3-R4 영역)

Schema diff 적용의 oracle 시:
- R3: 동일 input fixture 에서 동일 output 보장. Schema 변경이 input/output API 영향 시 fixture re-run 필요
- R4: Schema 변경의 실행 과정 (e.g., FK constraint 추가가 INSERT 의 fail point 가 되는 case) trace diff 로 검증
- Migration 이 forward + backward DDL pair 보유 → schema rollback 가능

## 결과 / 영향

- Ontology 가 5-layer 로 확장 — schema-aware reasoning 가능
- UC4 (스키마 추천) 의 mechanism 확립
- 기존 4-layer 의 작업물 (메모리 `project_decisions_v4_action.md` 의 4-layer + CallSiteAnalyzer) 영향 X
- Migration 의 risk 낮음 — additive only
- 3 system (v2 / Broadleaf / Banking) 각자의 schema source 가 다양 — schema_extractor extension 필요 (ADR-013 의 extensions)

## Honest limits

- 본 ADR 은 RDB (relational) schema 만 cover. NoSQL (Mongo / Cassandra) schema 는 phase 2
- DDL forward/backward 의 자동 generation 정확도는 plugin author 책임 — schema_extractor 의 quality 의존
- Schema migration 의 distributed environment (production DB) 적용은 본 ADR scope 외 (Liquibase / Flyway 등 외부 tool)
- Sharding / partitioning schema 는 phase 2

## 참조

- DECISIONS-CONFIRMED.md (D4)
- ADR-002 (Recommendation Engine)
- ADR-003 (Integrator + SchemaDiff)
- ADR-005 (Recommendation Engine LLM defenses)
- ADR-013 (Extensibility — schema_extractor 가 plugin extension)
- 메모리 `project_decisions_v4_action.md` (4-layer)
