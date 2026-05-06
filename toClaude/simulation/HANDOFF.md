# Section 3 — Simulation HANDOFF

섹션 담당: 시뮬레이션 Claude 세션
쓰기 영역: `toClaude/simulation/`
읽기 전용: `toClaude/wiki/`, `toClaude/modeling/`, `toClaude/_shared/`

## 현재 상태 (2026-04-17)
- 백엔드 Slab Agent API (`/api/simulation/slab/*`) 동작 중 (port 8001, venv/)
- 프론트엔드 Slab Simulator UI 존재 (`frontend/src/lib/simulation/`, `frontend/src/components/simulation/`)
- 시나리오 A/B/C agent + ontology 기반 tool들 구성됨

## 최근 변경
- 2026-04-17: `/api/simulation/slab/ontology` 500 에러 수정
  - 원인: 백엔드 `venv/`에 `networkx` 미설치 + `pyproject.toml` 미선언
  - 조치: `pyproject.toml`에 `networkx = "^3.2"` 추가, `venv/bin/pip install networkx` 실행
  - 영향: ontology endpoint + scenario A/B tool (`find_edging_specs_for_order`, `find_orders_by_rolling_line`) 모두 정상화

## 다음 세션 첫 작업
- (미정) 사용자 지시 대기

## 환경 설정 메모
- 백엔드 실행 환경: `venv/` (`.venv/`가 아님)
- 프론트엔드: port 3000, Next.js rewrite `/api/*` → `http://localhost:8001/api/*`
- ontology 데이터: `backend/simulation/data/mock_ontology.json`
- 시뮬레이터 Python 환경 테스트 시 반드시 `venv/bin/python` 사용 (`.venv/`는 별도 환경, 혼동 주의)
