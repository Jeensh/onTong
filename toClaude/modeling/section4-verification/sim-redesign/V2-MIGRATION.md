# V2-MIGRATION — Phase α → 새 v2 plugin 재작성 절차

작성일: 2026-05-13 (implementation plan session)
관련 ADR: ADR-001 (Python twin), ADR-002 (Two-Engine + plugin), ADR-010 (Phase α discard), ADR-011 (3 systems)
관련 결정: D2 (v2 자산 폐기, non-default), M-D3 (병행)
Track 위치: Track A Phase A2 (W3-W8) — MILESTONES-2track.md §1

---

## 0. TL;DR

D2 결정 → Phase α 산출물 폐기, 새 plugin (`backend/sim_v2/plugins/v2-slab-design/`) 처음부터 작성.

**작업 분해:**
1. git revision tag `phase-alpha-snapshot` 생성 — Phase α 산출물 보존 (검색 가능 archive)
2. 새 plugin scaffold (`backend/sim_v2/plugins/v2-slab-design/`) — ADR-002 의 7 artifact 작성
3. Regression check — Phase α equivalent intent 의 새 fixture 가 동등 결과 산출
4. Phase α 산출물의 archive (코드 영역) — `backend/modeling/sim_verify/` 폐기 / 코드 영역 cleanup

**관련 lessons 참조** (W1-W2 작성, 본 migration 의 정수 흡수):
- Lesson 1 (KNOWN_DIVERGENCE) — runtime API contract 의무
- Lesson 2 (27 cards) — plugin scope first-class
- Lesson 3 (manual twin) — automation 정당화
- Lesson 4 (facade abstraction) — generic Java contract base
- Lesson 5 (fixture) — fixture format contract

---

## 1. Phase α 산출물의 분류 — 보존 vs 폐기 vs 학습 자산

### 1.1 보존 (archive via git tag)

| 산출물 | 위치 | Tag 보존 |
|---|---|---|
| 5 v2 golden fixture (S1-S5) | (Phase α 의 fixture 위치, 본 plan 작성 시점에 정확 위치 commit 추적) | ✓ |
| Runtime substrate (4 module) | `backend/modeling/sim_verify/runtime/` | ✓ |
| 27 idiom card | `toClaude/modeling/section4-verification/idioms/P*.md` | ✓ |
| Oracle differ | `scripts/section4_oracle_diff.py` | ✓ |
| Gap report | `toClaude/modeling/section4-verification/anchor-gaps.md` | ✓ |
| KNOWN_DIVERGENCE 분석 | `toClaude/modeling/section4-verification/known-divergence-resolution-options.html` | ✓ |
| Source-code fixes (D-1 partial / D-2 / D-3 / E-1) | `toClaude/modeling/section4-verification/source-code-fixes-pending.md` | ✓ |

모두 git tag `phase-alpha-snapshot` 으로 검색 가능 archive.

### 1.2 폐기 (코드 영역 cleanup)

| 산출물 | 폐기 시점 | 후속 |
|---|---|---|
| `backend/modeling/sim_verify/runtime/` | W8 (새 plugin 완성 후) | 삭제 (Lesson 4 의 facade 폐기 결정) |
| `scripts/section4_oracle_diff.py` | W8 | 삭제, `backend/sim_v2/core/verification/oracle.py` 로 generic 화 |
| 27 idiom cards | (코드 영역 X — markdown 만) | git tag 으로 보존, 본 마크다운은 reference only |
| 5 golden fixture | (Phase α fixture 위치) | 폐기, 새 plugin 의 fixture (S1'-S5') 로 의도 유지 |

### 1.3 학습 자산화 (보존 + 새 framework 의 reference)

5 lessons (`lessons/phase-alpha-*.md`, W1-W2 작성, 본 V2-MIGRATION 의 sibling) — ADR-010 의 학습 자산 결정 정식 실현.

---

## 2. git revision tag 전략

### 2.1 phase-alpha-snapshot tag 의 목적

- Phase α 의 모든 산출물의 **검색 가능 snapshot** 생성
- 새 framework 작성 중 reference 필요 시 `git show phase-alpha-snapshot:<file>` 가능
- 폐기 결정 후 코드 영역 cleanup 시 안전 (tag 가 안전망)

### 2.2 Tag 의 commit 위치

후보 commit (Phase α 종료 시점):

| Commit | 메시지 | Tag 후보 사유 |
|---|---|---|
| `6769560` | `fix(sec4/source-fixes): D-1 partial + D-2 + D-3 + E-1` | Phase α 의 마지막 cleanup commit |
| `0777217` | `docs(sec4/gaps): v2 anchor gap report (Phase α deliverable #5)` | Phase α 의 deliverable #5 commit |
| `dcdf251` | `docs(sec4/sim-redesign): handoff for next-session resume` | Sim-redesign session 시작 직전 |

**추천**: `dcdf251` — sim-redesign session 시작 직전의 모든 Phase α 산출물 보존.

### 2.3 Tag 생성 절차 (W1)

```bash
# 1. 현재 branch 확인 (section4-verification)
git status

# 2. 본 plan 작성 commit 까지 포함된 시점에서 tag 생성
git tag -a phase-alpha-snapshot dcdf251 -m "Phase α (Section 4 verification, 2026-04-25 ~ 5-12) 산출물 archive.

포함:
- 4 runtime substrate (backend/modeling/sim_verify/runtime/)
- 27 idiom cards (toClaude/modeling/section4-verification/idioms/)
- 5 v2 golden fixtures + oracle differ + pytest harness
- anchor-gaps report
- KNOWN_DIVERGENCE 5종 분석
- source-code-fixes-pending (D-1 partial / D-2 / D-3 / E-1)

폐기 결정: ADR-010 (D2 확정). 학습 자산 5종으로 추출 (lessons/phase-alpha-*.md).
새 plugin 위치: backend/sim_v2/plugins/v2-slab-design/ (Track A2, W3-W8).
"

# 3. (선택적) remote push — 다른 컴퓨터 / 다른 세션 접근 가능
git push origin phase-alpha-snapshot
```

### 2.4 추가 tag (선택적)

- `phase-alpha-deliverable-5`: anchor-gaps.md 작성 시점 (`0777217`)
- `phase-alpha-pre-redesign`: redesign 결정 직전 (`dcdf251`)

기본은 `phase-alpha-snapshot` 하나면 충분.

---

## 3. 새 v2 plugin (`backend/sim_v2/plugins/v2-slab-design/`) 의 7 artifact

ADR-002 의 plugin contract:

| # | Artifact | 위치 | Phase α 의 대응 | 새 작성 cost |
|---|---|---|---|---|
| 1 | `contracts/base.py` | `backend/sim_v2/plugins/v2-slab-design/contracts/` | 4 runtime module 의 일부 (bigdecimal generic, lookup_source Spring base) | core/contracts 상속 + slab-specific override ~50 LOC |
| 2 | `entities/` | `backend/sim_v2/plugins/v2-slab-design/entities/` | (none, Phase α 는 Python hand-crafted) | Java AST 자동 추출 (~0 사람 작업) |
| 3 | `mappings/` | `backend/sim_v2/plugins/v2-slab-design/mappings/` | (none, anchor-gaps Gap C 14건 미확정 잔존) | Section 2 ontology 자동 import + name_match 처리 |
| 4 | `emitters/` | `backend/sim_v2/plugins/v2-slab-design/emitters/` | 27 idiom cards 의 ~63% (P01-P08, P10, P12-P19) 가 core, 나머지 plugin override | 17 cards generic + 7-10 cards plugin override ~200 LOC |
| 5 | `fixtures/` | `backend/sim_v2/plugins/v2-slab-design/fixtures/` | 5 fixture S1-S5 (의도만 reference, format 새로 작성) | 5 fixture × (input.json + expected_output.json + metadata.toml + README.md) ~150 LOC + tolerance 측정 |
| 6 | `aspects/` | `backend/sim_v2/plugins/v2-slab-design/aspects/` | (Phase α 단계엔 없었던 항목) | @Aspect handler (slab dispatch metadata, P27) ~50 LOC |
| 7 | `manifest.toml` | `backend/sim_v2/plugins/v2-slab-design/manifest.toml` | (없음) | Plugin metadata (~30 LOC) |

총 새 작성: ~500-600 LOC of plugin artifacts + 작은 사람 작업 (fixture 의도 author, tolerance 측정).

---

## 4. Per-artifact 작성 절차 (W3-W8 sprint detail)

### W3-W4 — Artifact 1 + Artifact 7 (contract + manifest)

#### 4.1 `manifest.toml` (Artifact 7)

```toml
[plugin]
name = "v2-slab-design"
version = "0.1.0"
description = "onTong slab manufacturing twin plugin (post-Phase-α rewrite)"

[recommendation]
default_provider = "claude"
default_model = "claude-opus-4-7"
allowed_providers = ["claude", "openai", "gemini"]
max_retries = 3

[extensions]
dispatchers = []           # Case 1-2 minimal (v2 의 8 dispatch_kind 중 자주 사용 안 함)
annotations = []
aop = []
bytecode = []

[schema]
source = "jpa_annotation"  # JPA annotation 기반 schema extraction

[fixtures]
ids = ["S1", "S2", "S3", "S4", "S5"]

[contracts]
domain_exception = "AlgorithmException"
numeric_convention = "decimal64_halfeven"
domain_namespace_class = "SdConstants"
```

#### 4.2 `contracts/base.py` (Artifact 1)

```python
# backend/sim_v2/plugins/v2-slab-design/contracts/base.py

from core.contracts.base import JavaContract
from core.contracts.numeric_base import DECIMAL64, RoundingMode

from .domain_namespace import SdConstants
from .exception import AlgorithmException
from .validation import ValidationResult


class SlabDesignContract(JavaContract):
    """v2 (slab manufacturing) plugin contract.
    
    Phase α 의 4 runtime module 의 reusable 부분을 core 상속 + slab-specific override.
    Lesson 4 의 facade abstraction failure 의 대응.
    """
    exception_base = AlgorithmException

    def domain_namespace(self) -> dict:
        return {
            "SdConstants": SdConstants,  # POS_SM, POS_HR, ...
            "ValidationResult": ValidationResult,
        }

    def numeric_convention(self) -> NumericConvention:
        return NumericConvention(
            bigdecimal_precision=16,
            bigdecimal_rounding=RoundingMode.HALF_EVEN,
            domain_scales={
                "slab.weight_kg": 3,
                "slab.dimension_mm": 0,
                "productivity.rate": 6,
            },
        )
```

`contracts/domain_namespace.py` — Phase α 의 `SdConstants.POS_SM` etc. 의 Python class 화:

```python
# backend/sim_v2/plugins/v2-slab-design/contracts/domain_namespace.py

class SdConstants:
    """Slab manufacturing 의 namespace constants (Java SdConstants 의 Python mirror).
    
    Lesson 1 의 KNOWN_DIVERGENCE Mismatch #4 의 대응 — 
    namespace class 가 first-class artifact.
    """
    POS_SM = "SM______"  # 8-position string
    POS_HR = "HR______"
    # ... (Phase α 의 8-position string set)
```

#### 4.3 acceptance criteria — W3-W4

- `manifest.toml` 유효 (`core.plugin_loader.load_plugin` 통과)
- `SlabDesignContract` 가 `JavaContract` 의 abstract method 모두 구현
- `SdConstants` namespace 가 Phase α 의 모든 plant code 값 cover
- `validate_contract.py` smoke test pass

---

### W4-W5 — Artifact 2 (entities) + Artifact 3 (mappings)

#### 4.4 `entities/` (Artifact 2)

```python
# backend/sim_v2/plugins/v2-slab-design/entities/__init__.py

from core.synthesizer.java_ast import extract_entities

ENTITIES = extract_entities(
    java_source_root=Path("sample-repos/slab-design-real-v2/src/main/java/"),
    package_filter="kr.co.posco.slab.*",
)
```

자동 추출 — 사람 작업 0 (Phase α 의 hand-crafted entity 폐기, Lesson 3 의 automation 정당화).

#### 4.5 `mappings/` (Artifact 3)

```python
# backend/sim_v2/plugins/v2-slab-design/mappings/__init__.py

from core.ontology import OntologyAPI

# Section 2 의 v2 ontology DB 에서 자동 import
MAPPINGS = OntologyAPI().load_mappings(repo_id="slab-design-real-v2")
```

자동 import — 단 anchor-gaps Gap C 의 14 type_realization 미확정은 W4 사람 review 필요:
- `SdHistoryController -> term.scm.history_controller` 등 14건 (anchor-gaps §Gap C)
- modeling UI 의 매핑 confirm 흐름으로 처리 — Section 2 본체 작업

#### 4.6 acceptance criteria — W4-W5

- `ENTITIES` 가 v2 의 128 code_types cover (anchor-gaps §0)
- `MAPPINGS` 가 v2 의 163 anchor_bindings + 43 realizations import
- Gap C 14건 review 완료
- `mapping_health_check.py` test pass (confirmed_rate >= 90%)

---

### W5-W6 — Artifact 4 (emitters)

#### 4.7 `emitters/` (Artifact 4)

```python
# backend/sim_v2/plugins/v2-slab-design/emitters/__init__.py

from core.synthesizer.emitters import (
    BodyComputeEmitter,
    BodySetOutputEmitter,
    BodyBranchEmitter,
    # ... 17 generic emitters (Lesson 2 §3 의 system-agnostic 카드)
)

from .atomic_safety_absolute_max import AtomicSafetyAbsoluteMaxEmitter
from .atomic_confirmed_plant_cd import AtomicConfirmedPlantCdEmitter
# ... 7 slab-specific emitter (Lesson 2 §3 의 P20-P26)

EMITTERS = {
    "body.compute": BodyComputeEmitter(),
    "body.set_output": BodySetOutputEmitter(),
    # ... 17 generic
    "atomic.safety.absolute_max": AtomicSafetyAbsoluteMaxEmitter(),
    "atomic.confirmed_plant_cd.invalid_check": AtomicConfirmedPlantCdEmitter("invalid_check"),
    # ... 7 plugin-specific
}
```

각 emitter 는 ADR-006 의 polymorphic dispatch contract 준수. Phase α 의 27 cards 의 의도 흡수 (codified, machine-executable).

#### 4.8 acceptance criteria — W5-W6

- 56 distinct `target_slot` 모두 emitter 매핑 (anchor-gaps §0 의 coverage 유지)
- 17 generic emitter 가 `backend/sim_v2/core/synthesizer/emitters/` 의 상속
- 7-10 plugin emitter 가 `backend/sim_v2/plugins/v2-slab-design/emitters/` 내 정의
- Emitter test (Java AST 입력 → Python 출력) → contract validator 통과 (Lesson 1 §4.2)
- Anti-pattern 5 KNOWN_DIVERGENCE 재발 없음 (Lesson 1 §4.3)

---

### W6-W7 — Artifact 5 (fixtures)

#### 4.9 `fixtures/` (Artifact 5)

Phase α 의 5 fixture S1-S5 의 의도만 reference, 새 format:

```
backend/sim_v2/plugins/v2-slab-design/fixtures/
  S1/
    input.json                  # SDOrderEntity 입력 (Phase α equivalent intent)
    expected_output.json        # SDSlabEntity 예상 output
    expected_trace.json         # per-action trace (strong R4)
    metadata.toml               # tolerance / intent / version
    README.md                   # scenario description
  S2/ ... S5/
```

Scenario 의도 (Phase α 와 동등 — Lesson 5 §5):
- **S1**: happy path (full algorithm 21-step success)
- **S2**: boundary (a-a loop split fallback 발동)
- **S3**: fallback (productivity safe_range fallback)
- **S4**: error (validation fail, dg_throw)
- **S5**: edge (BigDecimal precision boundary, async batch)

#### 4.10 acceptance criteria — W6-W7

- 5 fixture format 완성 (input/output/trace/metadata + README)
- 각 fixture 의 tolerance 실측 측정 후 `metadata.toml` 의 per-action override 작성
- Trace contract strong version (intermediate values + async boundary) cover
- Anti-pattern (Lesson 5 §6.5 fixture metadata 부재) 재발 없음

---

### W7-W8 — Artifact 6 (aspects) + 통합 검증

#### 4.11 `aspects/` (Artifact 6)

```python
# backend/sim_v2/plugins/v2-slab-design/aspects/dispatch_metadata.py

from core.synthesizer.aspects import DispatchMetadataAspect

class V2DispatchMetadata(DispatchMetadataAspect):
    """Phase α 의 P27 카드 의도 — action.metadata.tiebreaker / fallback_kind 의 ROOT."""
    
    def tiebreaker(self, action_fqn: str, candidates: list[Realization]) -> Realization:
        # v2 의 specific dispatch policy
        ...
```

v2 단계에서 @Aspect 자체 사용 안 — 단 dispatch metadata 의 aspect 화 (P27).

#### 4.12 통합 검증 (W7-W8)

```bash
# core/plugin_loader 가 v2 plugin 인식
python -m core.plugin_loader load backend/sim_v2/plugins/v2-slab-design

# 7 artifact 모두 등록 확인
python -m core.plugin_validator backend/sim_v2/plugins/v2-slab-design

# 5 fixture 실행
pytest backend/sim_v2/plugins/v2-slab-design/fixtures/ -v

# Anti-pattern catalog 검사
python -m core.recommendation.anti_patterns.scan backend/sim_v2/plugins/v2-slab-design
```

#### 4.13 acceptance criteria — W7-W8

- 7 artifact 모두 작성 완료
- `core.plugin_loader.load_plugin("v2-slab-design")` 성공
- 5 fixture pytest 모두 PASS
- Anti-pattern scan 0 hit
- **G1 gate 대비 완료** (W10 의 cross-validate gate, ADR-011)

---

## 5. Regression check — 새 plugin 의 R3 equivalence

W8 종료 후 W9-W10 의 verification:

### 5.1 Phase α equivalent intent

5 fixture 의 의도 = Phase α 의 S1-S5 와 동등. 동일 algorithm scenario 의 동일 input 입력 시 동일 output (within tolerance).

### 5.2 두 twin 의 비교

```bash
# Phase α twin (phase-alpha-snapshot tag 의 코드, archive 형태)
git worktree add /tmp/phase-alpha phase-alpha-snapshot
cd /tmp/phase-alpha
python -m backend.modeling.sim_verify.runtime <fixture-S1> > phase_alpha_output.json

# 새 plugin twin
cd /Users/donghae/workspace/ai/onTong
python -m core.verification.run --plugin v2-slab-design --fixture S1 > new_plugin_output.json

# Diff
diff phase_alpha_output.json new_plugin_output.json
```

기대: tolerance 안에서 동일 (R3 equivalence).

### 5.3 Equivalence 의 의미

새 plugin 의 결과가 Phase α 와 동등 → Lesson 1-4 의 lessons 가 valid (새 framework 가 hand-crafted 의 silent drift 회피하면서도 same output).

차이 발생 시:
- Phase α 의 silent bug 발현 (e.g., negative scale rejected) — 새 plugin 이 올바름
- 새 plugin 의 bug — fix 후 재실행

---

## 6. Phase α 산출물의 archive 절차 (W8 후)

### 6.1 코드 영역 cleanup

```bash
# 1. phase-alpha-snapshot tag 의 존재 확인 (안전망)
git tag -l phase-alpha-snapshot

# 2. backend/modeling/sim_verify/ 폐기
git rm -r backend/modeling/sim_verify/
git commit -m "remove: Phase α slab-specific substrate (archived via phase-alpha-snapshot tag).

ADR-010 의 D2 결정 후 새 plugin (backend/sim_v2/plugins/v2-slab-design/) 완성. 
Phase α 산출물은 phase-alpha-snapshot tag 으로 보존."

# 3. scripts/section4_oracle_diff.py 폐기
git rm scripts/section4_oracle_diff.py
git commit -m "remove: scripts/section4_oracle_diff.py (generic backend/sim_v2/core/verification/oracle.py 로 대체)."
```

### 6.2 Markdown 영역 reference 유지

`toClaude/modeling/section4-verification/` 의 markdown 산출물 (idioms/ + anchor-gaps.md + known-divergence-resolution-options.html + source-code-fixes-pending.md) 는 폐기 X — git 안에서 reference. 단 README 에 "Phase α deliverables — superseded by sim-redesign/ ADRs and lessons/" 표시.

---

## 7. 잔여 source-code-fixes 처리

Phase α 종료 시 `source-code-fixes-pending.md` 의 D-1 (code_layer composite PK) 가 미처리:
> `CodeTypeRow`, `CodeMethodRow` 2개는 미적용. 사유: ForeignKey 의존성 복잡

본 migration plan 안에서 처리 시점:
- W7 (W6-W7 fixture authoring 와 병행) — 본 fix 는 modeling 본체 작업, 새 plugin 작성 전 ORM 정합성 필요
- 또는 implementation phase 에서 별도 (Section 2 modeling 본체 작업)

추천: implementation phase 에서 별도 (V2-MIGRATION 의 plan 안에 포함 X — modeling 본체 영역).

---

## 8. Risk + contingency

| Risk | Impact | Mitigation |
|---|---|---|
| Phase α 와 새 plugin 의 R3 equivalence 실패 | High (Lesson 1-4 valid 검증 무산) | W9-W10 의 regression check 시점에 차이 분석. Phase α 의 silent bug 발견 시 새 plugin 이 올바름 — accept. 새 plugin bug 시 fix |
| 17 generic emitter 의 core 작성이 W5-W6 안에 못 끝남 | Medium (Track A 의 W6 schedule 영향) | Track B Phase B3 (W4-W10) 의 broadleaf/banking 의 emitter 작성과 cross-share. 동일 generic emitter 가 3 system 에 reusable |
| Anchor-gaps Gap C 14건 review 가 W4-W5 안에 미완 | Medium | unconfirmed 14건은 lower confidence 로 sentinel 처리, blocker 아님. 단 G1 gate 시 confirmed_rate >= 95% 의무 |
| Phase α fixture 의도 의 ambiguity (S2 의 a-a loop split fallback 의 정확 의도 불명 등) | Low | S1-S5 의 README 가 새 plugin 의 fixture README 의 source. Phase α 의 README 가 fixture format 결정 시점에 명확 작성 권장 (W3 prep) |

---

## 9. 참조

### Phase α 산출물 (phase-alpha-snapshot tag 으로 archive)
- `backend/modeling/sim_verify/runtime/` (4 module)
- `scripts/section4_oracle_diff.py`
- `toClaude/modeling/section4-verification/idioms/` (27 cards)
- `toClaude/modeling/section4-verification/anchor-gaps.md`
- `toClaude/modeling/section4-verification/known-divergence-resolution-options.html`
- `toClaude/modeling/section4-verification/source-code-fixes-pending.md`

### ADRs
- ADR-001 (Python twin)
- ADR-002 (Two-Engine + plugin) — 7 artifact 의 source
- ADR-010 (Phase α discard) — D2 결정의 정식
- ADR-011 (3 systems) — v2 cost 100-200h estimate

### Lessons (sibling artifacts)
- `lessons/phase-alpha-known-divergence.md` (L1)
- `lessons/phase-alpha-idiom-cards.md` (L2)
- `lessons/phase-alpha-manual-twin.md` (L3)
- `lessons/phase-alpha-facade.md` (L4)
- `lessons/phase-alpha-fixture.md` (L5)

### Implementation plan
- `implementation-plan.md` (Track A Phase A2, W3-W8 의 본 migration 의 sprint task)
- `MILESTONES-2track.md` (sprint cadence)
