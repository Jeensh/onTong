# Section 3 — Simulation Demo Guide

## 데모 시나리오

### S1. Ontology Graph 로드 확인
```bash
curl -sS http://localhost:8001/api/simulation/slab/ontology | head -c 300
# 기대: {"nodes":[...], "edges":[...]} 형식 JSON, HTTP 200
```

### S2. Mock Orders 로드 확인
```bash
curl -sS http://localhost:8001/api/simulation/slab/orders | head -c 300
# 기대: [{"order_id":"ORD-2024-0042", ...}, ...] 배열
```

### S3. Equipment Constraints 확인
```bash
curl -sS http://localhost:8001/api/simulation/slab/constraints
# 기대: {"target_width": {"min":900,"max":1570,...}, ...}
```

### S4. 프론트엔드 Slab Simulator 페이지
- http://localhost:3000 접속 후 상단 Simulation 탭 진입
- 상단 탭에 "soon" 배지가 없어야 함 (Wiki / Modeling / Simulation 모두 일반 탭)
- 페이지 로드 시 ontology 그래프가 렌더링되는지 확인
- 시나리오 A/B/C 실행 시 SSE 이벤트가 스트리밍되는지 확인

## Troubleshooting

### `/api/simulation/slab/ontology` 500 (ModuleNotFoundError)
- 원인: `venv/`에 `networkx` 미설치
- 해결: `venv/bin/pip install "networkx>=3.2,<4"`
- 재발 방지: `pyproject.toml`에 `networkx = "^3.2"` 선언 확인

### `/api/simulation/slab/run` scenario A/B에서 tool 호출 실패
- 원인: 동일 (networkx 필요). `find_edging_specs_for_order`, `find_orders_by_rolling_line`이 `build_mock_graph()` 내부에서 networkx 사용
- 해결: 동일

### Python 환경 혼동
- 프로젝트에 `venv/`와 `.venv/` 두 개 존재. 백엔드 서버는 `venv/`로 실행 중
- `ps -p <backend_pid> -o command`로 확인하거나 `lsof -p <pid> | grep site-packages`로 어느 환경인지 식별
