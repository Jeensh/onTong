# Perspective: Two-Engine Integrator

## 1. Summary

ADR-002 splits the simulation agent into two engines sharing one ontology and one Java AST: a **deterministic Verification Engine** (Anchored Twin Synthesizer, Round 1) and a **LLM-based Recommendation Engine** (Schema / Code / Ontology Evolver). Without an explicit integration substrate, the two engines will re-introduce α's "two-agent contract drift" at a larger scale — Recommendation will propose ontology shapes Verification cannot regenerate, Verification will produce twin behavior Recommendation never sees. This perspective designs the substrate: a **5-layer ontology** (Code / Domain / Mapping / Simulation + new **Schema Layer**), an explicit **Schema↔Code mapping** table mirroring `type_realizations`, a **proposal lifecycle** with deterministic state transitions, and a **shared revision pointer** that both engines stamp on every artifact. Result: every recommendation is a candidate ontology delta Verification can replay byte-for-byte; every twin run carries its revision id so a Recommendation 7 minutes later sees exactly the rows the twin ran against.

## 2. Architecture — Verification + Recommendation 공유

```
                ┌──────────────────────────────────────────────────────┐
                │  Shared Ontology Store (SQLite — data/ontology.db)   │
                │   Code | Domain | Mapping | Simulation | Schema (new)│
                │   + ontology_revisions / proposals / audit_log       │
                └──────┬───────────────────────────────┬───────────────┘
                       │ pinned revision R_n           │ pinned revision R_n
                       │ read-only consumer            │ read-only; advisory write via Integrator
                       ▼                               ▼
      ┌────────────────────────────┐   ┌──────────────────────────────────┐
      │  Verification Engine        │   │  Recommendation Engine           │
      │  (deterministic, ADR-001)   │   │  (LLM-based, ADR-002 §D2)        │
      │                             │   │                                  │
      │  Anchored Twin Synthesizer  │   │  Schema Recommender   (UC4)      │
      │  + Twin Scope Boundary      │   │  Code Recommender     (UC5)      │
      │  + Gap Surfacer             │   │  Ontology Evolver     (UC6)      │
      │  Twin Runner + Oracle Diff  │   │  → calls Verification.simulate() │
      └──────────┬──────────────────┘   └─────────────┬────────────────────┘
                 │ generated/*.py, trace.json,        │ proposals/<pid>/*
                 │ verification_runs                  │
                 ▼                                    ▼
        ┌──────────────────────────────────────────────────────────┐
        │  Integrator (transactional, ~200 LOC)                    │
        │  – applies accepted proposals → new ontology_revisions   │
        │  – stamps every artifact with (proposal, revision, run)  │
        └──────────────────────────────────────────────────────────┘
```

One SQLite file holds all state. Verification never writes ontology rows (read-only consumer); Recommendation writes only to `proposals/*`. All ontology mutations route through the **Integrator** — a single, sequential, transactional component. Every generated artifact (`generated/<repo>/<R_n>/*.py`, `runs/<run_id>/...`) carries the `ontology_revision_id` it was produced against. This is the "shared revision pointer" that prevents proposal-vs-execution races.

## 3. 5-layer ontology

The existing four layers (per `project_decisions_v4_action.md`) are Code, Domain, Mapping, Simulation. Schema Layer models the *persistence* surface that v2's 9 JPA repos + JPO entities implicitly describe.

### 3.1 Schema Layer — new tables (DDL)

```sql
-- Logical schema table — one row per persistence table the system uses
CREATE TABLE IF NOT EXISTS schema_tables (
    fqn                 VARCHAR NOT NULL,     -- "schema.scm.cast_spec"
    physical_name       VARCHAR NOT NULL,     -- "TB_CAST_SPEC"
    label               VARCHAR NOT NULL,
    domain              VARCHAR NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    kind                VARCHAR NOT NULL,     -- "table"|"view"|"materialized_view"
    is_lookup           BOOLEAN NOT NULL,     -- true for CAST_SPEC/HR_SPEC pattern
    storage_engine      VARCHAR,              -- "Oracle"|"PostgreSQL"|"SQLite"|...
    source              VARCHAR NOT NULL,     -- "jpa"|"manual"|"recommendation"
    confirmed           BOOLEAN NOT NULL,
    repo_id             VARCHAR NOT NULL,
    revision_introduced INTEGER NOT NULL,     -- FK -> ontology_revisions.id
    revision_obsoleted  INTEGER,
    PRIMARY KEY (fqn, repo_id)
);
CREATE INDEX ix_schema_tables_repo_id   ON schema_tables (repo_id);
CREATE INDEX ix_schema_tables_revision  ON schema_tables (revision_introduced);

CREATE TABLE IF NOT EXISTS schema_columns (
    id                  INTEGER PRIMARY KEY,
    table_fqn           VARCHAR NOT NULL,
    physical_name       VARCHAR NOT NULL,     -- "CMP_CD"
    logical_name        VARCHAR NOT NULL,     -- "cmpCd"
    sql_type            VARCHAR NOT NULL,     -- "VARCHAR2(3)"|"NUMBER(10,3)"|...
    nullable            BOOLEAN NOT NULL,
    is_primary_key      BOOLEAN NOT NULL,
    pk_ordinal          INTEGER,              -- composite PK order
    default_value       VARCHAR,
    description         TEXT NOT NULL DEFAULT '',
    repo_id             VARCHAR NOT NULL,
    revision_introduced INTEGER NOT NULL,
    revision_obsoleted  INTEGER,
    FOREIGN KEY (table_fqn, repo_id) REFERENCES schema_tables (fqn, repo_id),
    CONSTRAINT uq_schema_column UNIQUE (table_fqn, physical_name, repo_id)
);
CREATE INDEX ix_schema_columns_table ON schema_columns (table_fqn);

CREATE TABLE IF NOT EXISTS schema_foreign_keys (
    id                  INTEGER PRIMARY KEY,
    from_table_fqn      VARCHAR NOT NULL,
    from_columns_json   TEXT NOT NULL,        -- ["CMP_CD","ORG_CD"]
    to_table_fqn        VARCHAR NOT NULL,
    to_columns_json     TEXT NOT NULL,
    on_delete           VARCHAR NOT NULL,     -- "cascade"|"restrict"|"set_null"
    on_update           VARCHAR NOT NULL,
    repo_id             VARCHAR NOT NULL,
    revision_introduced INTEGER NOT NULL,
    revision_obsoleted  INTEGER
);
CREATE INDEX ix_schema_fk_from ON schema_foreign_keys (from_table_fqn);
CREATE INDEX ix_schema_fk_to   ON schema_foreign_keys (to_table_fqn);

CREATE TABLE IF NOT EXISTS schema_indexes (
    id                  INTEGER PRIMARY KEY,
    table_fqn           VARCHAR NOT NULL,
    name                VARCHAR NOT NULL,
    columns_json        TEXT NOT NULL,        -- ["PRIORITY","CMP_CD"]
    is_unique           BOOLEAN NOT NULL,
    repo_id             VARCHAR NOT NULL,
    revision_introduced INTEGER NOT NULL,
    revision_obsoleted  INTEGER
);

CREATE TABLE IF NOT EXISTS schema_constraints (
    id                  INTEGER PRIMARY KEY,
    table_fqn           VARCHAR NOT NULL,
    name                VARCHAR NOT NULL,
    kind                VARCHAR NOT NULL,     -- "check"|"unique"|"not_null"
    expression          TEXT NOT NULL,        -- "PRIORITY > 0"
    repo_id             VARCHAR NOT NULL,
    revision_introduced INTEGER NOT NULL,
    revision_obsoleted  INTEGER
);
```

`revision_introduced` / `revision_obsoleted` give bitemporal slicing — Verification can replay against any historical revision without losing prior schema state.

### 3.2 Connection to existing 4 layers

Three attach points:

1. **Code Layer ↔ Schema** — each JPA `@Entity` class maps to one `schema_tables` row via the `schema_code_map` table (§4).
2. **Mapping Layer (Action) ↔ Schema** — anchor bindings of slot `body.service_lookup` gain an optional `schema_table_fqn` reference so Verification knows which lookup reads which physical table.
3. **Domain Layer ↔ Schema** — `business_term` for "CAST_SPEC 행" maps via the existing `type_realizations` table once `code_type_fqn` accepts `schema_tables.fqn` with `source='schema'`.

### 3.3 Migration path from current ontology.db

Additive only — no existing row touched:

```sql
.backup data/ontology.db.bak-pre-schema-layer
-- Apply 5 CREATE TABLE statements above + revision tracking tables (§8)
-- Seed Schema Layer from existing JPA entities
INSERT INTO schema_tables (fqn, physical_name, label, ..., revision_introduced)
  SELECT 'schema.' || lower(simple_name), '...', '...', 1
  FROM code_types
  WHERE json_extract(annotations_json, '$') LIKE '%@Entity%'
    AND repo_id = 'slab-design-real-v2';
-- Seed schema_code_map from @Table/@Column annotations on the same entities
```

Deterministic + reproducible — re-running the seed produces the same row set. Phase α data survives untouched.

## 4. Schema ↔ Code mapping

Existing `type_realizations` maps Java `code_types` → `business_terms`. We add a peer table mapping Java entity classes → schema tables, and Java fields → schema columns:

```sql
CREATE TABLE IF NOT EXISTS schema_code_map (
    id                  INTEGER PRIMARY KEY,
    code_type_fqn       VARCHAR NOT NULL,     -- "com.example.scm.entity.CastSpecEntity"
    code_field_fqn      VARCHAR,              -- "CastSpecEntity.slabThickness" (NULL = table-level)
    schema_table_fqn    VARCHAR NOT NULL,     -- "schema.scm.cast_spec"
    schema_column_id    INTEGER,              -- NULL when row is table-level
    source              VARCHAR NOT NULL,     -- "jpa_annotation"|"name_match"|"manual"|"recommendation"
    confidence          FLOAT NOT NULL,
    confirmed           BOOLEAN NOT NULL,
    confirmed_by        VARCHAR,
    rationale           TEXT NOT NULL,
    repo_id             VARCHAR NOT NULL,
    revision_introduced INTEGER NOT NULL,
    revision_obsoleted  INTEGER,
    FOREIGN KEY (schema_table_fqn, repo_id) REFERENCES schema_tables (fqn, repo_id),
    FOREIGN KEY (schema_column_id) REFERENCES schema_columns (id),
    CONSTRAINT uq_schema_code_map UNIQUE
        (code_type_fqn, code_field_fqn, schema_table_fqn, schema_column_id, repo_id)
);
CREATE INDEX ix_schema_code_map_code_type ON schema_code_map (code_type_fqn);
CREATE INDEX ix_schema_code_map_table     ON schema_code_map (schema_table_fqn);
```

Shape mirrors `type_realizations` deliberately — existing Section 2 modeling UI confirm-queues are reused: a `schema_code_map` row with `confirmed=0` shows up the same way a `type_realizations` row with `confirmed=0` does.

For v2 the seed is exact: `@Table(name="TB_CAST_SPEC") class CastSpecEntity` → one table-level row (`source='jpa_annotation'`, `confidence=1.0`, `confirmed=1`); each `@Column(name="SLAB_THICKNESS")` → one column-level row, same provenance. For systems without JPA (MyBatis, JDBC, NoSQL ORM), the seed source becomes `name_match` with lower confidence and falls into Section 2's confirm queue.

Verification's synthesizer now reads `schema_code_map` when emitting `body.service_lookup` anchors — the gap surfacer can additionally emit `# UNCLEAR: schema_code_map for column X has confidence 0.6` when the schema mapping itself is shaky.

## 5. End-to-end workflow — "고객사 슬랩 두께 override"

User wants customer-specific slab-thickness override. Seven concrete steps:

| # | Actor / Engine | Output / artifact | Storage |
|---|---|---|---|
| 1 | User → Recommendation | spec.md (verbatim text) + `proposals` row, status=`draft` | `proposals` table + filesystem |
| 2 | Recommendation (Schema sub-engine) | `proposals/<pid>/schema.sql` (DDL diff) + `ontology_delta.sql` (rows) | filesystem |
| 3 | Recommendation (Code sub-engine) | `proposals/<pid>/code_diff.patch` (Java change) | filesystem |
| 4 | User reviews & picks options | `proposals` → `accepted_partial`; `proposals_decisions` rows | DB |
| 5 | Integrator (atomic apply) | New `ontology_revisions` row R1; new Schema Layer rows + Domain Layer additions; `revision_introduced=R1` on new rows; obsoleted rows get `revision_obsoleted=R1` | one DB transaction |
| 6 | Verification Engine | Re-synthesize affected actions (cache invalidates on revision); produce `generated/<repo>/R1/*.py` | content-addressed |
| 7 | Verification (Twin Runner + Oracle Differ) | New fixture S6 (override case) + S1–S5 regression; `trace.json` + diff report | `verification_runs` row + filesystem |
| 8 | If pass: Integrator | Schema migration SQL (`migrations/2026-05-13-customer-override.sql`) + draft Java PR | git branch + filesystem |

Each artifact carries `(proposal_id, revision_id, run_id)` triple in its header.

## 6. Data flow

**Verification** (deterministic):
- Input: `ontology.db` at revision `R_n` (immutable view) + Java repo at git commit `C_n`
- Output: `generated/<repo>/<R_n>/*.py` + `runs/<run_id>/{trace.json, output.json, gap-report.json}` + `verification_runs` row

**Recommendation** (LLM-based):
- Input: User spec + ontology at `R_n` (read-only) + Java AST at `C_n` + a Verification call for "what does the twin do with `R_n` + proposed_delta?"
- Output: `proposals/<pid>/{spec.md, schema.sql, code_diff.patch, ontology_delta.sql, rationale.md}` + `proposals` row

The only shared writeable is `ontology.db` mutation via the Integrator — sequential and transactional. Both engines emit content-addressed artifacts so reruns are reproducible.

## 7. Concurrency / race condition handling

| Scenario | Resolution |
|---|---|
| Recommendation writes while user edits ontology directly | Proposal pins `base_revision`. If user creates `R_n+1` before apply, Integrator rejects with `STALE_PROPOSAL`. Proposal then rebased or discarded. |
| Two simultaneous proposals from different users | Each pins its own `base_revision`. First-apply wins; second fails `STALE_PROPOSAL`. No silent merge. |
| Verification on `R_n` while Integrator commits `R_n+1` | Verification keyed by revision id; `R_n` artifacts remain readable forever (bitemporal). |
| LLM call mid-flight when peer proposal accepted | Proposal status state-machine (`draft → analyzing → ready → reviewed → accepted | rejected | stale`); accepted proposal forces peers to re-check `base_revision` before they can transition to `accepted`. |

## 8. Audit + versioning

Two new tables + extension of existing `audit_log`:

```sql
CREATE TABLE IF NOT EXISTS ontology_revisions (
    id           INTEGER PRIMARY KEY,
    parent_id    INTEGER,
    created_at   DATETIME NOT NULL,
    created_by   VARCHAR NOT NULL,    -- "user:jeensh"|"recommendation:engine"|"system:migration"
    summary      TEXT NOT NULL,
    proposal_id  VARCHAR,             -- NULL if hand-edited; FK to proposals
    git_commit   VARCHAR,             -- bound Java commit
    FOREIGN KEY (parent_id) REFERENCES ontology_revisions (id)
);

CREATE TABLE IF NOT EXISTS proposals (
    id                  VARCHAR PRIMARY KEY,  -- UUID
    kind                VARCHAR NOT NULL,     -- "schema"|"code"|"ontology"|"composite"
    status              VARCHAR NOT NULL,     -- draft|analyzing|ready|reviewed|accepted|rejected|stale
    base_revision       INTEGER NOT NULL,
    target_revision     INTEGER,
    created_by          VARCHAR NOT NULL,
    created_at          DATETIME NOT NULL,
    spec_md_path        VARCHAR NOT NULL,
    artifacts_json      TEXT NOT NULL,        -- {schema_sql, code_diff, ontology_delta, rationale_md}
    user_decisions_json TEXT NOT NULL,        -- accept/reject per sub-option
    FOREIGN KEY (base_revision)   REFERENCES ontology_revisions (id),
    FOREIGN KEY (target_revision) REFERENCES ontology_revisions (id)
);

CREATE TABLE IF NOT EXISTS verification_runs (
    id           VARCHAR PRIMARY KEY,
    revision_id  INTEGER NOT NULL,
    fixture      VARCHAR NOT NULL,
    proposal_id  VARCHAR,
    status       VARCHAR NOT NULL,            -- pass|fail|partial
    result_path  VARCHAR NOT NULL,
    started_at   DATETIME NOT NULL,
    ended_at     DATETIME,
    FOREIGN KEY (revision_id) REFERENCES ontology_revisions (id),
    FOREIGN KEY (proposal_id) REFERENCES proposals (id)
);
```

Every accepted proposal produces an `ontology_revisions` row (`proposal_id` set), a stream of `audit_log` rows (one per mutated table), and one transition in `proposals.status`. A rejected proposal still leaves the row + artifacts on disk — full forensic trail. This satisfies skeptic M10 at the proposal level: every proposal is "smoke-tested" by Verification before acceptance.

## 9. CI/CD integration

A PR touching Java triggers three gates:

1. **Verification regression gate** — re-run twin against current revision + S1–S5; fail if any byte-identical fixture diverges. Records results in `verification_runs`.
2. **Schema-Code sync gate** — re-extract JPA entities from PR's Java; diff against `schema_code_map` at current revision. If a `@Column` was renamed without a `schema_code_map` migration, fail. Forces "Java schema change ⇒ ontology revision."
3. **Proposal validation gate** — if PR references an accepted `proposal_id` (commit trailer), confirm the diff matches `proposals.artifacts_json.code_diff`. Prevents silent drift between recommendation and implementation.

A PR touching ontology (Schema Layer only) triggers Verification on the new revision; if no Java change accompanies, the gate passes only when the schema is genuinely additive (new optional column with default).

## 10. Failure modes

- **Recommendation produces an ontology delta contradicting existing rows.** Caught at apply time by SQL constraint violations (unique constraints, FK to obsoleted rows). User sees concrete error, can amend.
- **LLM hallucinates a schema column not in any system.** Recommendation always grounds suggestions in retrieved `schema_tables` rows + Java AST; pure-invention proposals fail the "every referenced symbol must resolve" check before reaching the user.
- **Verification fails after proposal applied.** Integrator does NOT auto-rollback (would erase audit). Instead `proposal.status='accepted_verification_failed'`, the new revision remains in history with a `revision_failed_at` marker; user fixes forward via a new proposal or hand-reverts via an inverse-delta proposal.
- **Partial proposal acceptance creates incoherent state.** Recommendation declares dependencies in `artifacts_json.options[*].requires[]`; UI greys out sub-options whose prerequisites were rejected; Integrator validates the closure at apply time.
- **Engine communication failure (Recommendation can't call Verification).** Recommendation degrades to "proposal without simulated validation" and stamps `validation_status='unsimulated'`. User sees an explicit warning at review.

## 11. Honest weaknesses

- **SQLite write contention.** Both engines + Section 2 UI sharing one file with mutation transactions will hit lock contention if proposal acceptance is concurrent with Section 2 anchor confirmation. Mitigation: WAL mode + serialized writer (single integrator goroutine). At ~10k proposals/year this is fine; at higher scale shard or move to PostgreSQL.
- **Schema Layer seed quality depends on JPA annotation completeness.** Systems with reflection-based or XML mapping (Hibernate `.hbm.xml`, MyBatis mapper files) need additional extractors. v2 is JPA-only so the seed is trivial; other systems require system-specific extractors that ADR-002's "system-agnostic" goal anticipates but doesn't yet implement.
- **Bitemporal slicing complexity.** `revision_introduced` / `revision_obsoleted` on every Schema-Layer row makes simple queries verbose. Mitigated by views (`schema_tables_current AS SELECT * FROM schema_tables WHERE revision_obsoleted IS NULL`), but the maintenance cost is real.
- **Proposal artifact storage volume.** Each non-trivial proposal generates ~10 KB; rejected proposals accumulate. At 100/day this is 1 MB/day — manageable, but a janitor for `rejected AND older_than_90d` is needed.
- **LLM determinism not enforced.** Recommendation may produce different proposals for the same input. Mitigation: seed the LLM call, cache (spec_hash, revision_id) → proposal_id. Re-running identical query returns the cached proposal. Narrows but doesn't eliminate drift — acceptable because outputs are always reviewed before apply.
- **Integrator is a single point of failure.** All ontology mutations route through it. SQLite rollback handles mid-transaction crashes, but in-flight proposals may need manual rerun. Mitigation: idempotent apply (re-applying a proposal with the same id is a no-op if already applied).
- **No explicit story for cross-repo proposals.** A proposal touching schema in repo A but code in repo B is plausible (microservices migration). Current design handles only same-repo; cross-repo is future ADR-003 candidate.

The two-engine architecture's defensibility rests on one observation: the failure mode that bit Phase α (two artifacts produced by two parallel authors without an explicit contract) reappears at a higher abstraction in any two-engine system. By making the **(ontology revision, schema_code_map row, proposal artifact)** triple the contract, routing every mutation through one Integrator, and stamping every artifact with the revision it was produced against, we convert "implicit, silent, race-prone divergence" into "explicit, recorded, auditable disagreement that fails loudly at the apply boundary." Verification stays deterministic; Recommendation gets the LLM's flexibility without the LLM's drift cost.
