# Section 3 — Simulation CHANGES

Ad-hoc change log. `[x]` = done, `[ ]` = deferred/pending.

## 2026-04-17
- [x] 상단 SectionNav에서 Simulation 탭의 "soon" 배지 제거
  - `frontend/src/components/sections/SectionNav.tsx` Simulation entry `status: "scaffolding"` → `"active"`
  - 이유: Section 3 엔드포인트 동작 확인됨, 더 이상 예정 상태 아님
- [x] `networkx` 의존성 추가 및 설치
  - `pyproject.toml`: `[tool.poetry.dependencies]`에 `networkx = "^3.2"` 선언 (Graph Database neo4j 섹션 아래)
  - `venv/`에 `networkx 3.6.1` 설치 (`venv/bin/pip install "networkx>=3.2,<4"`)
  - 이유: `backend/simulation/tools/ontology_graph.py:13`의 top-level `import networkx`로 인해 `/api/simulation/slab/ontology` + scenario A/B tool 500 에러 발생 중
  - 검증: `curl http://localhost:8001/api/simulation/slab/ontology` → HTTP 200, proxy `http://localhost:3000/...` → HTTP 200
