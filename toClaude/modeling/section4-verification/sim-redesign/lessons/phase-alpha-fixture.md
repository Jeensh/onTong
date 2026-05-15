# Phase α Lesson 5 — Fixture-driven Verification 의 적합성

작성일: 2026-05-13 (implementation plan session)
대상: Phase α 의 5 v2 golden fixtures (S1-S5) + oracle differ + pytest harness
관련 ADR: ADR-001 (Python twin), ADR-003 (Two-Engine substrate), ADR-010 (Phase α discard)
관련 requirement: R3 (동일 input → 동일 output), R4 (동일 처리 과정), R5 (수정 전후 비교)
Phase α 산출물 reference:
- commit `37c423d feat(sec4/oracle): trace differ + 5 v2 golden fixtures + pytest harness`
- `scripts/section4_oracle_diff.py` (oracle differ)
- `anchor-gaps.md` Gap E-2 (tolerance 미튜닝)

---

## 1. 사실 — Phase α 의 fixture 자산

| 항목 | 내용 |
|---|---|
| Fixture 개수 | 5 (S1-S5) |
| 도메인 | slab manufacturing 의 design algorithm scenario |
| 입력 형태 | `SDOrderEntity` instance (Java fixture serialized + Python deserialize) |
| 출력 형태 | `SDSlabEntity` instance + algorithm trace |
| Oracle differ | `scripts/section4_oracle_diff.py` (abs_tol=1e-6, rel_tol=1e-9 hardcode) |
| Harness | pytest |
| Trace differ | 별도 mechanism — per-step (step_no, error_code) sequence 비교 |
| 작성 작업량 | ~30-50h 추정 (fixture authoring + oracle differ + pytest harness) |

---

## 2. 무엇이 작동했나 — R3/R5 mechanism 의 실증

### 2.1 R3 (동일 input → 동일 output) — 가능

Fixture = `(input, expected_output)` pair. Oracle differ 가 두 output 의 deep diff 수행:
- Java baseline 의 output 과 Python proposal 의 output 의 비교
- Tolerance 안에서 동일 → R3 PASS

5 fixture 가 slab manufacturing 의 representative scenario cover — happy path / boundary / fallback / error 등.

### 2.2 R5 (수정 전후 비교) — baseline 으로 작용 가능

Fixture 의 expected_output 이 **revision baseline**:
- Pre-modification: 5 fixture 의 baseline 저장
- Java 수정 → Python twin 재생성 → 5 fixture 재실행 → diff vs baseline
- Diff = 의도된 변경 (user confirm) or regression (fix 필요)

이 mechanism 이 ADR-003 §5.3 의 R5 workflow 의 base.

### 2.3 R4 (동일 처리 과정) — 부분적

Trace differ 가 per-step (step_no, error_code) sequence 비교. R4 의 weak version — same sequence verifiable. R4 의 strong version (intermediate values + async boundary) 은 Phase α 의 trace structure 로는 부족.

새 framework 의 ADR-002 §trace diff mechanism 에서 강화.

### 2.4 Deterministic 의 입증

Fixture run 의 결과가 deterministic — 동일 fixture 재실행 시 동일 output. Random / 비결정 source 없음. R3 의 정의에 부합.

---

## 3. 무엇이 부족했나 — Phase β 의 잔존 risk

### 3.1 Tolerance 의 hardcode (anchor-gaps Gap E-2)

```python
# scripts/section4_oracle_diff.py
abs_tol = 1e-6
rel_tol = 1e-9
```

문제:
- 21-step a-a loop 의 cumulative drift 시 last-digit 흔들림 누적 — 1e-6 의 absolute tolerance 가 충분한지 measured X
- Step 별 tolerance 분리 안 됨 (per-action tolerance 부재)
- Fixture 별 tolerance override 안 됨 (per-fixture metadata 부재)

### 3.2 Fixture 의 trace contract 미정의

Fixture 가 input/output pair 만 정의, **expected trace** 미정의:
- Trace 의 shape: per-step `(step_no, error_code)` only — intermediate values 없음
- Trace 의 semantic alignment: step 의 의미 매핑 부재 (e.g., "step 5 의 error_code = LOW_FEED" 이 무엇 의미인지 trace 외부 metadata 필요)

새 framework 의 R4 (동일 처리 과정) 가 strong version 이 되려면 trace contract 확장 필요.

### 3.3 Fixture metadata 의 부재

Fixture file format 추정 (Phase α 종료 시점 확인 불가):
- `S1.input.json` + `S1.expected_output.json` + (possibly) `S1.expected_trace.json`
- 부족: domain tag, scenario_intent, version, regression_baseline_lineage

새 system onboarding 시 fixture 의 semantic context 가 사람만 안다 → onboarding cost ↑.

### 3.4 Idiom × runtime contract 미검증 (anchor-gaps Gap E-1)

Fixture pytest harness 가 idiom 카드의 Python 블록을 실행한 적 없음 — Lesson 1 의 5 mismatch silent. Fixture harness 자체가 substrate import 만 검증, idiom-level smoke test 부재.

---

## 4. 새 framework 의 적용 — Fixture format contract

### 4.1 Fixture file structure (ADR-003 §5.2 fixture baseline 의 정식)

```
backend/sim_v2/plugins/<sys>/fixtures/
  S1/
    input.json                  # 입력 entity
    expected_output.json        # 예상 output entity
    expected_trace.json         # per-action trace baseline (optional)
    metadata.toml               # tolerance, intent, version
    README.md                   # human-readable scenario description
```

### 4.2 metadata.toml 의 spec

```toml
[fixture]
id = "S1"
domain = "slab.manufacturing.design_algorithm"
scenario_intent = "happy_path"  # or "boundary" / "fallback" / "error"
version = "1.0"
parent_baseline = null          # revision lineage (ADR-003 §5)

[tolerance]
default_abs = 1e-6
default_rel = 1e-9

# per-action override
[[tolerance.action]]
action_fqn = "action.scm.slab.cumulative_productivity"
abs = 1e-5  # 21-step cumulative drift 의 측정 후 조정
rel = 1e-8

[trace]
contract_version = "1.0"
required_fields = ["step_no", "step_name", "error_code", "intermediate_values"]
async_boundary_required = true  # TX, async batch 의 align 필수
```

### 4.3 Fixture-oracle protocol (ADR-003 §4 의 정식)

```python
# backend/sim_v2/core/verification/oracle.py

class FixtureRunner:
    def run(self, fixture: FixturePath, twin: PythonTwin) -> FixtureRunResult:
        """Fixture 의 input 으로 twin 실행, trace + output 수집."""
        ...

class OracleDiffer:
    def diff(self, baseline: FixtureRunResult, proposal: FixtureRunResult, metadata: FixtureMetadata) -> OracleResult:
        """
        - Output diff (per metadata.tolerance)
        - Trace diff (per metadata.trace.contract_version)
        - Aggregate status: PASS / FAIL_BREAKING / FAIL_DRIFT / INCONCLUSIVE
        """
        ...
```

### 4.4 Fixture lineage 의 revision pointer 통합 (ADR-003 §5)

```python
class Revision:
    # ...
    fixture_baseline: dict[FixtureId, FixtureBaseline]

class FixtureBaseline:
    output: Any
    trace: list[TraceEvent]
    measured_tolerance: ToleranceMetric  # 실측 drift
    parent_revision: RevisionId
```

R5 의 mechanism: revision N 의 fixture_baseline 이 revision N+1 의 oracle 비교 기준. Revision chain 이 fixture 의 진화 trace.

---

## 5. Phase α 의 fixture 자체의 운명 (D2 폐기 결정)

ADR-010 D2:
> 5 golden fixture S1-S5 → 폐기 (새 fixture 작성 필요)

폐기 사유:
- Slab manufacturing 의 hand-crafted edge case 가 generic fixture format 결정 전 작성됨
- Trace contract 의 weak version 만 보장 — strong version 호환 X
- Tolerance hardcode — per-action override 의 retrofit cost > 새 작성 cost

새 v2 plugin 의 fixture (S1'-S5') 는:
- 의도 (intent) 유지: BigDecimal precision / async batch / boundary / fallback / error 5종
- 새 format (input.json + expected_output.json + expected_trace.json + metadata.toml)
- Per-action tolerance 측정 후 설정

---

## 6. 학습 정수

1. **Fixture = R3/R5 의 evidence. R4 의 partial evidence.** Fixture format design 이 R4 의 strong version 의 limit.
2. **Tolerance 는 metadata 의 first-class field.** Hardcode = 도메인 over-fit. Per-fixture override 가 fixture format 의 첫 비-trivial 결정.
3. **Trace contract 의 strong version 의 의무.** "step_no + error_code" only 의 weak version 은 R4 의 strong 검증 불가. Intermediate values + async boundary 필수.
4. **Fixture 의 revision lineage 가 R5 의 mechanism.** Fixture baseline = revision pointer chain (ADR-003 §5).
5. **Onboarding cost 의 fixture 비중.** 5 fixture authoring + metadata + tolerance 측정 = ~20-30h per system (D6 cost estimate 의 sub-component).

---

## 7. 새 framework 의 적용

| 영역 | 적용 항목 |
|---|---|
| `backend/sim_v2/core/verification/fixture/` | Fixture format spec (input/output/trace + metadata.toml) |
| `backend/sim_v2/core/verification/oracle.py` | Oracle differ + per-action tolerance |
| `backend/sim_v2/core/verification/trace_differ.py` | Strong R4 mechanism — intermediate values + async boundary |
| `backend/sim_v2/core/integrator/revision.py` | Fixture baseline → revision pointer lineage |
| `backend/sim_v2/plugins/<sys>/fixtures/` | system-specific fixture (S1-S5 equivalent) |
| Plugin onboarding checklist | 5 fixture authoring + tolerance 측정 + trace contract 의무 |
| `backend/sim_v2/core/recommendation/anti_patterns/fixture_no_metadata.py` | "Fixture metadata 부재 (tolerance, trace contract)" anti-pattern entry |

---

## 8. 참조

- ADR-001 — Python = Java twin (R3 의 deterministic synthesis 정당화)
- ADR-002 — Two-Engine + plugin (fixture in 7 artifact)
- ADR-003 — Two-Engine Substrate (Oracle protocol + Revision pointer)
- ADR-010 — Phase α discard (D2 결정으로 fixture 폐기)
- `scripts/section4_oracle_diff.py` — α3 의 oracle differ 실제 코드
- `anchor-gaps.md` — Gap E-2 (tolerance 미튜닝)
- 사용자 R3/R4/R5 requirements
