# Phase α Lesson 1 — KNOWN_DIVERGENCE Root Cause

작성일: 2026-05-13 (implementation plan session)
대상: Phase α `backend/modeling/sim_verify/runtime/` (α1) + `toClaude/modeling/section4-verification/idioms/P*.md` (α2)
관련 ADR: ADR-001 (Python twin), ADR-005 (Recommendation defenses), ADR-010 (Phase α discard)
Phase α 산출물 reference:
- commit `5642a57 feat(sec4/runtime): slab_design_runtime Python substrate`
- commit `d4d80dc docs(sec4/idioms): 25 anchor-keyed Java→Python idiom cards`
- `toClaude/modeling/section4-verification/known-divergence-resolution-options.html`
- `toClaude/modeling/section4-verification/anchor-gaps.md` Gap E-1

---

## 1. 사실 — Phase α 의 5 API mismatch

α1 (runtime) 과 α2 (idiom 카드) 가 병렬로 작업하면서 5종 API mismatch 가 silent 하게 발생. 매 항목 = 카드 Python 블록을 그대로 import / exec 시 `NameError`.

| # | Java API | Idiom 카드 가정 | Runtime 의 실제 구현 | Mismatch 결과 |
|---|---|---|---|---|
| 1 | `BigDecimal` | `BigDecimal("100")` class 생성자 | `bd(value: Numeric) -> Decimal` factory 함수 | `NameError: BigDecimal` |
| 2 | `MathContext.DECIMAL64` | `MathContext.DECIMAL64` namespace 접근 | `DECIMAL64_PRECISION = 16` + `DECIMAL64_ROUNDING = ROUND_HALF_EVEN` 두 module 상수 | `NameError: MathContext` |
| 3 | `RoundingMode.FLOOR` | `RoundingMode.FLOOR` enum | `ROUND_FLOOR`, `ROUND_CEILING`, `ROUND_HALF_EVEN` (Python decimal 의 상수 그대로 re-export) | `NameError: RoundingMode` |
| 4 | `SdConstants.POS_SM` | `SdConstants.POS_SM` namespace 접근 | `POS_SM`, `POS_HR` module-level 상수 | `NameError: SdConstants` |
| 5 | `ValidationResult.fail(...)` | dataclass + builder pattern | 미구현 (idiom 카드만 reference, runtime 미작성) | `NameError: ValidationResult` |

5건 모두 silent — pytest run 시 import error 가 아니라 actual exec 시점에 발생. anchor-gaps.md Gap E-1 ("idiom × runtime API contract 미검증") 의 직접적 발현.

해소 옵션 비교는 `known-divergence-resolution-options.html` 에 3 방향 (A/B/C) 으로 정리되어 있으나, ADR-010 (Phase α 폐기) 결정으로 본 해소 자체는 무산. 본 lesson 은 그 root cause 보존.

---

## 2. Root cause — 분리된 design decision 의 동시 진행

### 2.1 α1 (runtime) 의 design 의도

`backend/modeling/sim_verify/runtime/bigdecimal.py` 의 작성 의도 (docstring 인용):

> Models Java's BigDecimal + MathContext.DECIMAL64 + RoundingMode combinations that appear throughout sample-repos/slab-design-real_v2.
> The helpers below intentionally stay close to the Java method names so Section 3's codegen can rewrite `a.setScale(2, HALF_EVEN)` as `bd_set_scale(a, 2)` without having to rebuild rounding logic.

즉 α1 은 "codegen 이 사용하는 helper 함수" 를 target. Convention 은 **snake_case 함수** (`bd()`, `bd_set_scale`, `bd_multiply_decimal64`).

### 2.2 α2 (idiom cards) 의 design 의도

`idioms/README.md` 의 작성 의도 인용:

> A canonical lookup table for Section 3's codegen: each card pins one `target_slot` value to its Java → Python translation.
> Use the **Canonical Python block as the template**, substituting locals (variable names, FQNs, error codes).

즉 α2 는 "**사람이 베끼는** Canonical Python template" 를 target. Convention 은 **Java 원본과 시각적 1:1 매핑** (`BigDecimal(...)`, `RoundingMode.FLOOR`).

### 2.3 두 의도의 충돌

| 차원 | α1 의 결정 | α2 의 결정 |
|---|---|---|
| 호출 형태 | snake_case 함수 | Java-mirror class 호출 |
| 정밀도 namespace | module 상수 분리 | namespace class 접근 |
| Audience | codegen | 사람 (template substitution) |
| Contract | implicit (자체 일관성) | implicit (Java 원본 매핑) |

둘 다 자체적으로는 일관된 design 이지만 **shared contract 가 없는 상태에서** 병렬 작성됨. 카드를 사람이 reference 로만 읽는 동안은 충돌 silent; 카드의 Python 블록을 실제 실행하려는 시점에 NameError 5건 발생.

---

## 3. 왜 발생했나 — process 적 분석

1. **α1, α2 의 sub-agent boundary 가 contract 없이 분리됨.** 작업 시작 시 "α1 = runtime, α2 = cards" 만 명시, runtime API 의 shape 미합의.
2. **첫 통합 검증 시점이 너무 늦음.** 카드 27장 + runtime 4 module 모두 완성 후 통합 시도 → 5건 한꺼번에 발현. 1번째 카드 통합 시점에 검증했으면 즉시 발견.
3. **검증 도구 (idiom × runtime smoke test) 가 없음.** anchor-gaps E-1 의 "Pattern → Runtime API 정합성 비검증" 항목.
4. **Audience 의 ambiguity.** "사람이 베끼는 reference" vs "codegen 이 emit 하는 spec" 의 boundary 가 양 agent 의 의도에서 다르게 해석됨.

---

## 4. 새 framework 의 적용

### 4.1 Synthesizer 의 runtime API contract 의 명시 의무

새 framework 의 emitter 가 emit 하는 코드의 referent 는 **plugin contract 의 first-class artifact**:

```python
# backend/sim_v2/plugins/v2-slab-design/contracts/runtime_api.py

class JavaBigDecimal:
    """Java BigDecimal 의 method-level equivalent.

    합성기 emitter 가 Java AST 의 `a.setScale(2, HALF_EVEN)` 를
    `JavaBigDecimal.set_scale(a, 2, RoundingMode.HALF_EVEN)` 로 변환.
    """
    @staticmethod
    def set_scale(value: Decimal, scale: int, mode: RoundingMode) -> Decimal: ...
    @staticmethod
    def multiply(a: Decimal, b: Decimal, mc: MathContext | None = None) -> Decimal: ...

class MathContext(NamedTuple):
    precision: int
    rounding: RoundingMode

class RoundingMode(Enum):
    HALF_EVEN = "half_even"
    FLOOR = "floor"
    CEILING = "ceiling"
    HALF_UP = "half_up"
    HALF_DOWN = "half_down"
    UP = "up"
    DOWN = "down"
    UNNECESSARY = "unnecessary"

DECIMAL64 = MathContext(16, RoundingMode.HALF_EVEN)
```

Emitter 가 referent 하는 모든 symbol 은 contract 안에 존재 의무. SIGNATURE_LOCKED 또는 plugin extension 없으면 NameError 자체가 발생 불가.

### 4.2 Contract validator 의 framework core enforce

```python
# backend/sim_v2/core/synthesizer/contract_validator.py

def validate_emitter_output(emitted_code: PythonAST, plugin_contract: PluginContract) -> ValidationResult:
    """Emitter 의 출력 중 plugin contract 에 없는 symbol 검출.

    실패 시 SIGNATURE_LOCKED 또는 plugin extension 등록 요구.
    """
```

Contract validator 가 emitter test suite 의 일부 — 매 emitter 의 출력이 contract 매핑 안에 있는지 enforce. 사용자 메모리 `feedback_verify_before_demo.md` 와 일관.

### 4.3 ADR-005 anti-pattern catalog 의 entry 5개

```python
# backend/sim_v2/core/recommendation/anti_patterns/known_divergence_5.py

ANTI_PATTERNS = [
    AntiPattern(
        id="phase_alpha_bigdecimal_class_vs_function",
        signal_pattern=r"\bBigDecimal\(",  # cards 에 등장
        runtime_check=r"def\s+bd\(",       # runtime 의 실제 형태
        severity="ERROR",
        rationale="Phase α 의 α1/α2 mismatch — runtime 은 함수, cards 는 class 호출",
    ),
    # ... 4 more entries (MathContext / RoundingMode / SdConstants / ValidationResult)
]
```

Recommendation Engine 의 4-layer defense (ADR-005) 중 Layer 2 (output validation) 가 본 anti-pattern catalog 를 검사 → 같은 mismatch 재발 차단.

### 4.4 Sub-agent boundary 의 contract first

새 framework 의 plugin onboarding 시:
- 작업 분담 시작 전 contract artifact (runtime_api.py + emitter_protocol.py) 의 first-class 작성 의무
- Sub-agent 간 첫 1건 통합 시 contract validator 실행 의무
- 위반 = 작업 중단 + sync session

---

## 5. 학습 정수

1. **"사람용 reference" 와 "machine-executable code" 의 contract 는 별개 artifact.** Audience 가 다르면 contract 도 다름.
2. **Parallel design 의 shared contract 는 first-class artifact.** Implicit 인 채로 두면 NameError-shaped 디버깅 → 후반에 더 비싸짐.
3. **Naming convention 선택의 strategic cost.** Java-mirror vs Pythonic — 한 쪽 선택 = 다른 쪽 cost. 새 framework 는 emitter 가 강제하므로 사람이 선택할 일 없음.
4. **검증 도구의 작성 시점.** Idiom × runtime smoke test 는 카드 1장 통합 시점에 작성. Phase α 는 27장 후 작성하려다 폐기.

---

## 6. Anti-pattern 5종 의 신 framework 적용 요약

| Anti-pattern | 신 framework 의 적용 위치 | Enforcement |
|---|---|---|
| BigDecimal class vs function | `backend/sim_v2/plugins/<sys>/contracts/runtime_api.py` 의 JavaBigDecimal class | Contract validator |
| MathContext namespace vs constants | 위 contract 의 MathContext NamedTuple | Contract validator |
| RoundingMode enum vs constants | 위 contract 의 RoundingMode Enum | Contract validator |
| SdConstants namespace vs imports | 위 contract 의 system-specific Namespace class | Plugin contract |
| ValidationResult 미구현 | 위 contract 의 system-specific ValidationResult dataclass | Plugin manifest 의 declared API |

---

## 7. 참조

- ADR-001 — Python = Java twin (사람이 편집 X)
- ADR-005 — 4-layer defense, anti-pattern catalog
- ADR-010 — Phase α discard rationale, Lesson preservation
- `known-divergence-resolution-options.html` — 3 해소 옵션 비교 (A/B/C)
- `anchor-gaps.md` — Gap E-1 (idiom × runtime contract 미검증)
- `backend/modeling/sim_verify/runtime/bigdecimal.py` — α1 의 실제 구현
- `idioms/README.md` — α2 의 작성 의도
