# Section 3 — 검증 체크리스트 (테스팅 매뉴얼)

> 각 Phase별로 데모 전 반드시 통과해야 하는 검증.
> CHECKLIST는 **체크박스 없는** 매뉴얼 (Single Source of Truth는 TODO.md).

---

## 공통

- pytest: `pytest tests/simulation/ -v` 전수 PASS
- 타입체크: `cd frontend && npx tsc --noEmit` 0 errors
- 백엔드 기동: `uvicorn backend.main:app --reload --port 8000` → http://localhost:8000/docs
- 프론트 기동: `cd frontend && npm run dev` → http://localhost:3000/simulation

---

## Phase 1 — Sandbox

### Step 변환 정확성

각 step 변환본은 다음 케이스에 대해 Java 알고리즘 doc(`ALGORITHM.md`)과 정합:

| Step | 입력 | 기대 출력 | 검증 방식 |
|---|---|---|---|
| Validator DG001 | order.stockCode=1 | `(False, "DG001")` | unit test |
| Validator DG004 | designPendQtyHigh < pkgWgtLow | `(False, "DG004")` | unit test |
| Productivity | confirmedPlantCd="K K K   " (HR/HRF/CR active) | 0.95 × 0.93 × 0.92 = 0.8126 | unit test |
| Thickness | order(prodTypeCd="A001"), CastSpec(thickness=220) | 220 | unit test |
| SplitRange | maxSplitCount=5, splitWgt=10t | range 객체 | unit test |
| SlabCount | designPendQtyHigh=100t, productivity=0.8, splitWgt=10t | 매수=12 | unit test |
| FinalRange | step 16~19 chain | dict | unit test |

### Sandbox 격리

- subprocess 메모리 한도 256MB 설정 → 한도 초과 시 OSError 캡처
- subprocess CPU 한도 5s 설정 → 한도 초과 시 timeout 캡처
- 정상 케이스 ≤ 200ms (1 step / 1 fixture)

### CLI 검증
```bash
python -m backend.simulation.sandbox.runner \
  --step productivity \
  --input '{"confirmedPlantCd": "K K K   "}'
# → {"result": 0.8126, "elapsed_ms": 12}
```

---

## Phase 2 — Agent 2 (★)

### API
```bash
# SSE 스트림
curl -N -X POST http://localhost:8000/api/simulation/agents/test-data/stream \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "step",
    "target_id": "9",
    "case_types": ["normal", "boundary"],
    "test_count": 50
  }'
# 기대: data: {"event":"case_started","case_id":1,...}\n\n 형식 50+ 이벤트 + summary
```

### 브라우저
1. `/simulation` → "Agent 2 — 테스트 데이터" 패널
2. target=step 9, count=100, types=[boundary, error] → 실행
3. SandboxConsole에 1~100 진행 표시 (실시간)
4. ResultChart에 분포 히스토그램 + 실패 케이스 테이블
5. "코드 스켈레톤" 영역에 pytest 파일 다운로드 가능

### Edge case
- count=0 → 400 에러 + 안내 메시지
- count=10000 → 정상 동작 (server-side max=1000 cap, 안내)
- target_id 미존재 → ontology에서 unsupported, 안내 메시지

---

## Phase 3 — Agent 1 / 3

### Agent 1 (영향도 + 전후 비교)
1. target=column:HR_PRODUCTIVITY, modification=value_change, new_value=0.92
2. 응답 fields: direct_impact / indirect_impact / risk_level / **diff_summary** / **viz_data**
3. 프론트 Agent1ImpactPanel: 트리뷰 + Plotly diff 차트

### Agent 3 (위치 + preview)
1. q="단중상한" → matched_terms 1+, source_locations 1+
2. 응답에 `source_preview` (코드 snippet ±10줄) 포함
3. UI에 Monaco preview 렌더 + "이 step 시뮬" 버튼 → A2 패널 jump (target 사전 채움)

---

## Phase 4 — 데모 e2e

### 시나리오 5 (누적 실수율) e2e
1. Agent 1 실행: column:HR_PRODUCTIVITY value_change 0.92
2. 영향도 결과: step 5/6/9 표시
3. "샌드박스 비교 실행" 클릭 → 전후 결과 차트
4. 차트에서 "주문 N건이 Slab 매수 변동" 카드 확인

### 시나리오 8 (A-a 루프) e2e
1. Agent 2 실행: step 9, types=[boundary, error], count=200
2. SSE 진행 1~200 visual confirm
3. minimal fail case 1+ 자동 발견 (Hypothesis shrink)
4. 코드 스켈레톤 다운로드 → pytest 실행 가능 확인

### 시나리오 1 (PRODUCT_TYPE_CD) e2e
1. Agent 3 실행: q="품종 코드"
2. 4개 컬럼 + 2개 step 위치 표시
3. 각 위치 클릭 → Monaco preview
4. step 1 위치에서 "이 step 시뮬" → A2 jump

---

## 자동화

`toClaude/_shared/verify.sh`에 다음 추가 (사용자 승인 후):

```bash
# Section 3 simulation 검증
echo "[Section 3] pytest"
pytest tests/simulation/ -q --tb=short || exit 1

echo "[Section 3] sandbox CLI"
python -m backend.simulation.sandbox.runner --step productivity --input '{"confirmedPlantCd":"K K K   "}' || exit 1

echo "[Section 3] SSE 스모크"
# (curl 비동기 + grep summary)
```
