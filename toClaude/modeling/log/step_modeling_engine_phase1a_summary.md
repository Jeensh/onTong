# Section 2 Modeling Engine — Phase 1a 완료 요약

**날짜**: 2026-04-16
**브랜치**: main
**커밋**: 9e72597 ~ 7ad3f6f (11 commits)
**테스트**: 28 backend tests passing, TS clean build

---

## 구현 내용

Engine-First Architecture로 Section 2 리디자인. 기존 CRUD 데이터 관리 → "분석 콘솔" 기본 진입점으로 전환.

### 백엔드 (7 files)

| 파일 | 역할 |
|------|------|
| `backend/modeling/simulation/sim_models.py` | ParametricSimResult, SimulationParam, SimulationOutput, AffectedProcessRef |
| `backend/modeling/query/term_resolver.py` | Korean alias(30개) → fuzzy(0.55) → LLM fallback |
| `backend/modeling/simulation/sim_registry.py` | 9 SCM 엔티티 × calc functions + SimRegistry |
| `backend/modeling/simulation/sim_engine.py` | SimulationEngine: param clamp + calc + BFS impact |
| `backend/modeling/api/engine_api.py` | /engine/query, /simulate, /params/{id}, /status |
| `backend/modeling/api/modeling.py` | engine_api router wiring + dependency init |
| `backend/modeling/api/seed_api.py` | sim_entities count in seed response |

### 프론트엔드 (4 files)

| 파일 | 역할 |
|------|------|
| `frontend/src/components/sections/modeling/AnalysisConsole.tsx` | 자연어 입력 → 영향 분석 UI |
| `frontend/src/components/sections/modeling/SimulationPanel.tsx` | 파라미터 슬라이더 + before/after 비교 |
| `frontend/src/components/sections/ModelingSection.tsx` | MAIN_NAV/SETTINGS_NAV 구분, 기본탭=analysis |
| `frontend/src/lib/api/modeling.ts` | engineQuery, engineSimulate, engineGetParams, engineStatus |

### 테스트 (5 files, 28 tests)

| 파일 | 테스트 수 |
|------|----------|
| `tests/test_sim_models.py` | 5 |
| `tests/test_term_resolver.py` | 8 |
| `tests/test_sim_registry.py` | 6 |
| `tests/test_sim_engine.py` | 3 |
| `tests/test_engine_api.py` | 6 |

## 검증 결과

- pytest 28/28 pass
- TypeScript `tsc --noEmit` clean
- UI: 사이드바 구조 확인, 데모 로드, 분석 콘솔 → 시뮬레이션 네비게이션
- API: 한국어 term resolution ("안전재고 계산 로직 변경" → SafetyStockCalculator)
- API: 시뮬레이션 (safety_factor 1.65→2.5 → 안전재고 +51.5%, 재주문점 +7.7%)

## 코드 리뷰 수정

- Division-by-zero guard: param clamp to min/max in SimulationEngine.simulate()
- Hardcoded condition fix: `24 <= 24` → `d_threshold <= 24` in _calc_shipment_tracker

## 설계/플랜 문서

- 설계: `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260415-213837.md`
- 플랜: `docs/superpowers/plans/2026-04-15-modeling-engine-phase1a.md`
- 데모: `toClaude/demo_guide_modeling.md`
