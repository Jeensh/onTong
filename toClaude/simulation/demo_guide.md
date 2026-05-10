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

---

## 2026-05-10 STEP 3a — ChangeSpec / SimResult schema 도입

### S5. ChangeSpec / SimResult Pydantic 모델 인스턴스화 검증

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.shared.contracts.simulation import ChangeSpec, SimResult, BREvidence

# spec 04 §6.3 P-2018-0098 회귀 시나리오
cs = ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.thickness": 220,
    },
    scenario_fixture={
        "lookups": {"Customer:7": {"id": 7, "priority": 1}},
        "metadata": {"scenario_origin": "P-2018-0098", "snapshot_at": "2018-04-23T03:14"},
    },
)
print("ChangeSpec OK:", cs.action_fqn)
print("  scenario_origin:", cs.scenario_fixture["metadata"]["scenario_origin"])

# SimResult sim_violation (DG003 width min 위반)
sr = SimResult(
    run_id="run-demo",
    status="completed",
    verdict="sim_violation",
    br_evidence=[BREvidence(
        br_fqn="br.scm.slab.DG003.WidthMin",
        severity="error",
        enforcer_method_fqn=None,
        outcome="violated",
        violation_path="scm.slab.SlabResult.width",
        expected=">=1200",
        actual=1180,
        operational_history_refs=["P-2018-0098"],
    )],
    affected_design_gaps=[3],
    started_at="2026-05-10T12:00:00Z",
    completed_at="2026-05-10T12:00:02Z",
    duration_ms=2000,
    change_spec_ref="sha256:demo",
)
print("SimResult OK:", sr.verdict)
print("  br violation:", sr.br_evidence[0].br_fqn, "→", sr.br_evidence[0].actual)
print("  affected_gaps:", sr.affected_design_gaps)
PY
# 기대 출력:
# ChangeSpec OK: scm.workflow.SDSlabEntity_step_1_to_8
#   scenario_origin: P-2018-0098
# SimResult OK: sim_violation
#   br violation: br.scm.slab.DG003.WidthMin → 1180
#   affected_gaps: [3]
```

### S6. 19 schema test 통과 확인

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_changespec_schema.py -v
# 기대: 19 passed
```

### S7. 회귀 — 전체 simulation test suite

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 195 passed, 17 skipped (+ 3 failed for sample-repos/slab-design/ 부재 — STEP 3a 무관)
```

## Troubleshooting

### `Cannot resolve 'backend.shared.contracts.simulation'`
- 원인: PYTHONPATH 미설정
- 해결: `export PYTHONPATH=$(pwd)` (onTong 루트에서)

### `ValidationError: Extra inputs are not permitted`
- 원인: schema 외 필드 전달 (Pydantic `extra="forbid"`)
- 해결: spec 04 §1~§2 의 필드명 정확히 사용. typo 의심.

### tests/simulation/test_agent3.py / test_demo_e2e.py 3 failure
- 원인: `sample-repos/slab-design/` 부재 (commit `2a346e3` 옵션 A 정렬 영향)
- 해결: 통합 작업 시 `sample-repos/slab-design-real_v2/` 와 매핑 결정 후 fixture 경로 갱신
