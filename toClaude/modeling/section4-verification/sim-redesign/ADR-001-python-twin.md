# ADR-001: Python 등가 코드 = Java 의 재생성 가능한 실행 twin

작성일: 2026-05-12
상태: 확정 (사용자 결정)
대상 세션: section4-verification / sim-redesign

## 컨텍스트

Phase α (Section 4 verification) 진행 중 다음 문제가 드러났다:
- 27 idiom card 와 runtime substrate 사이 5종 API 미스매치 (KNOWN_DIVERGENCE: BigDecimal / MathContext / RoundingMode / SdConstants / ValidationResult)
- "Python 코드의 본질이 무엇인가" 라는 메타 질문 미해결 → Q1 (trace granularity) 그릴링 중 5개 옵션 (E/A/B/C/D) 비교에 도달했으나 macro 결정 부재로 수렴 실패

사용자가 명시적으로 결정 (2026-05-12 sim-redesign 세션 중):

> "파이썬 코드는 사람이 편집하지 않는다는거야. 사람이 편집하게 된다면 그건 자바코드 일거야. 파이썬은 자바 코드를 실제 런타임으로 돌리기에 필요한 인프라와 연결된 내용이 너무 많아서 띄우는 것이 현실적으로 어려워 실행을 위해 만든 자바 소스의 twin개념으로 설계한 건데."

## 결정

**Python 등가 코드 = Java 의 실행 인프라 우회 twin**.

1. **Python 은 사람이 직접 편집하지 않는다.** 사람의 편집 대상은 Java 만이다.
2. **Python 은 Java 의 twin** — v2 Java 와 동등한 처리 과정/출력을 보장. Spring DI, JPA, DB 등 실제 런타임 인프라 없이 실행 가능한 형태.
3. **Python 은 ontology + Java AST 로부터 deterministic 하게 생성**되는 산출물. 재생성 시 동일 결과 (같은 input → 같은 output).
4. **Java 가 v2 → v2' 로 수정**되면 ontology 갱신 후 Python 도 자동 재생성. 두 Python 의 실행 결과 비교 = R5 의 "수정 전후 비교 분석".

## 결과 (이전 가정 무효화)

- **사람-주도 Python refactor 시나리오 제거** — Q1 의 시나리오 #2 (사람 refactor 의 정당성 판정) 는 무관 처리
- **α 의 idiom card 가 "사람용 변환 가이드" 였던 것이 부적합** — 카드는 합성기의 internal registry 로 흡수되어야 함. 또는 폐기
- **Trace granularity (Q1) 는 합성기 결정의 자식 결정** — 합성기가 합성 시점에 어떤 metadata 를 Python 에 박을지로 reframe
- **검증 mechanism 의 본질이 명확해짐** — R3 (output) 은 두 Python 실행 결과 비교. R4 (처리 과정) 는 합성기 정확성으로 by-construction 보장하거나, 합성 시점 instrumentation 으로 런타임 직접 검증

## 영향받는 후속 결정 (Q2-Q6 reframe)

| 이전 질문 | Twin concept 적용 후 |
|---|---|
| Q2 — Python lifecycle | 재생성 가능 산출물로 확정. 별도 결정 불필요 |
| Q3 — gap surface | 합성 시점 정적 marker (Python 코드에 `# UNCLEAR` 주석 자동 삽입) + 선택적 런타임 emit |
| Q4 — 에이전트 자율도 | 합성기 = LLM 도구인가 결정론적 파이프라인인가는 macro 탐색에서 결정 |
| Q5 — idiom card 운명 | 합성기 internal registry 흡수 또는 폐기. 사람용 markdown 별도 유지 X |
| Q6 — R5 surface | Java diff → 두 Python 합성 → 두 실행 결과 비교 (output + trace) |

## 미해결 — 다음 단계로 위임

이 ADR 은 "twin" 이라는 wide-stroke 결정만 확정. 다음 결정은 macro 관점 4 perspective 병렬 탐색으로:
- automation purist (완전 자동 합성)
- minimal twin (Java AST literal translation)
- Phase α reuse (기존 자산 활용 + bridge)
- skeptic (twin 자체 risk + 위 셋 risk 분석)

탐색 산출물은 `explorations/` 에 저장, 종합 비교 후 최종 설계 spec 으로 통합. 최종 spec 의 ADR-002 ~ 가 이 결정의 자식.

## 참조

- SESSION-RESUME.md §1 (사용자 R1-R5)
- feedback_simulation_design.md (no MVP / 풀 시연 필수)
- project_decisions_v4_action.md (Code/Domain/Mapping/Simulation 4-layer)
- anchor-gaps.md (Gap A-F)
- Phase α 산출물: backend/modeling/sim_verify/runtime/, idioms/P*.md, scripts/section4_oracle_diff.py
