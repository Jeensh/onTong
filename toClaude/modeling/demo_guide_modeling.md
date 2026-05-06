# Section 2 Modeling — 데모 가이드

> Engine Phase 1a + Source Viewer & Mapping Workbench Phase 2a

---

## OD-11-B5-7 (JPA) — `JpaAnalyzer` 12번째 Spring analyzer 검증 (2026-04-25)

데모 코드 어차피 JPA 쓸 거라 미리 준비. Spring Data Repository 메서드 → 테이블 접근 그래프 자동 추출.

```bash
# 1. 단위 테스트
.venv/bin/python -m pytest tests/test_spring_jpa_analyzer.py -v
# → 27 passed (TestDetection 5 + TestMethodNameOperations 14 + TestMethodAttributes 3 + TestMultipleMethods 2 + TestProtocol 3)

# 2. 직접 시연 (실제 JPA Repository 코드)
.venv/bin/python -c "
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser
from backend.modeling.code_analysis.spring import JpaAnalyzer

src = '''
package com.demo;
public interface OrderRepository extends JpaRepository<Order, Long> {
    Order findByOrderNo(String no);
    long countByStatus(String status);
    void deleteByCustomerId(Long id);
    Order save(Order o);
}
'''
parser = Parser(Language(tsjava.language()))
tree = parser.parse(src.encode())
_, edges = JpaAnalyzer().analyze(tree=tree, content=src.encode(),
                                  file_path='OrderRepository.java', pkg_name='com.demo')
for e in edges:
    print(f'  [{e.kind}] {e.source} → {e.target}')
    print(f'         attrs: {dict(e.attributes)}')
"
```

**기대 출력**:
```
  [reads_table]  com.demo.OrderRepository.findByOrderNo → Order
         attrs: {'jpa_operation': 'find', 'jpa_property_path': ['orderNo'], 'target_kind': 'jpa_entity_simple_name'}
  [reads_table]  com.demo.OrderRepository.countByStatus → Order
         attrs: {'jpa_operation': 'count', 'jpa_property_path': ['status'], 'target_kind': 'jpa_entity_simple_name'}
  [writes_table] com.demo.OrderRepository.deleteByCustomerId → Order
         attrs: {'jpa_operation': 'delete', 'jpa_property_path': ['customerId'], 'target_kind': 'jpa_entity_simple_name'}
  [writes_table] com.demo.OrderRepository.save → Order
         attrs: {'jpa_operation': 'save', 'jpa_property_path': [], 'target_kind': 'jpa_entity_simple_name'}
```

**메서드 이름 컨벤션 매핑**:
| Prefix | jpa_operation | Edge kind |
|---|---|---|
| `find*By*` / `get*By*` / `query*By*` / `read*By*` / `search*By*` | `find` | READS_TABLE |
| `exists*By*` | `exists` | READS_TABLE |
| `count*By*` | `count` | READS_TABLE |
| `delete*By*` / `remove*By*` | `delete` | WRITES_TABLE |
| `save` / `saveAll` / `saveAndFlush` (정확 매치) | `save` | WRITES_TABLE |
| 그 외 | — | (edge 없음) |

**Property path 추출 규칙**:
- `findByEmail` → `["email"]`
- `findByEmailAndStatus` → `["email", "status"]` (And split)
- `findByEmailOrPhone` → `["email", "phone"]` (Or split)
- `save` → `[]` (By 없음)

**4 base interface (extends 탐지)**:
- `JpaRepository<E, ID>`
- `CrudRepository<E, ID>`
- `PagingAndSortingRepository<E, ID>`
- `Repository<E, ID>`

또는 `@Repository` annotation (단, generic 정보 없으면 entity 추출 못 해 edge 안 잡힘).

**Out of scope (v1)**:
- `@OneToMany` / `@ManyToOne` 관계 엣지 (entity ↔ entity FK)
- `@Query("SELECT ...")` (이미 `NativeSqlAnalyzer` 가 처리)
- `@Entity` ↔ `@Table` cross-file 해소 → CrossFileEnricher v2 에서 향후 (target_kind="jpa_entity_simple_name" 마킹으로 표시해 둠)
- 메서드 entity 직접 emit (JavaParser 가 이미 method 엔티티 만듦)

**Slab 샘플 영향**: Slab Design Engine 은 JPA 미사용 → 12-analyzer 결과 95/177 그대로. JPA 없는 코드 안 깨지는 것 검증됨.

**활용 (데모 코드 도착 시)**:
1. 새 repo 코드 분석 → JpaRepository 자동 탐지 → 메서드별 READS/WRITES 엣지
2. Impact Analysis : "User 테이블 변경 시 어떤 메서드 영향?" → READS_TABLE 역방향 BFS
3. CONFLICTS_WITH gap : 매뉴얼이 기술하는 "User 검색 키" ↔ JPA 메서드 `findByEmail` (property_path) 비교 가능

---

## OD-11-E1-j (A1) — `scripts/dump_entities_snapshot.py` JSON 스냅샷 (2026-04-25)

데모 코드 도착 전후 비교 + 외부 도구 (jq, diff) 입력 + 회귀 baseline.

```bash
# 1. 단위 테스트
.venv/bin/python -m pytest tests/test_dump_entities_snapshot.py -v
# → 8 passed

# 2. Slab 스냅샷 실행 (기본값)
.venv/bin/python scripts/dump_entities_snapshot.py
# → [snapshot] sample-repos/slab-design-engine/.analyzed/entities.json :
#     11 files / 95 entities / 177 relations / 0 errors

# 3. 메타데이터 + 통계 확인
jq '.metadata' sample-repos/slab-design-engine/.analyzed/entities.json
# → {repo_id, repo_path, generated_at, analyzers (11종), totals}

# 4. config_property entry 만 뽑기 (E1-f 검증과 동일)
jq '.files["com/ontong/slab/config/EquipmentProperties.java"].entities[]
    | select(.kind=="config_property")
    | {qn:.qualified_name, default:.attributes.default_value, kebab:.attributes.key_kebab}' \
   sample-repos/slab-design-engine/.analyzed/entities.json

# 5. 다른 repo 에 적용 (데모 코드 도착 시)
.venv/bin/python scripts/dump_entities_snapshot.py \
    --repo /path/to/your-repo/src/main/java \
    --out  /path/to/your-repo/.analyzed/entities.json \
    --repo-id your-repo-id
```

**스키마 요약**:
```jsonc
{
  "metadata": {
    "repo_id": "slab-design-engine",
    "repo_path": "sample-repos/.../java",
    "generated_at": "2026-04-25T07:06:38+00:00",
    "analyzers": ["DIAnalyzer", "AopAnalyzer", ..., "ConfigPropertiesAnalyzer"],  // 11종
    "totals": {"files": 11, "entities": 95, "relations": 177, "errors": 0}
  },
  "files": {
    "com/ontong/slab/config/EquipmentProperties.java": {
      "language": "Java",
      "errors": [],
      "entities": [
        {"kind":"package", "qualified_name":"com.ontong.slab.config", ...},
        {"kind":"class", ...},
        {"kind":"field", "name":"maxThicknessMm", "attributes":{"field_type":"double", "initializer":"240.0", "initializer_kind":"literal_number"}, ...},
        {"kind":"config_property", "qualified_name":"slab.equipment.maxThicknessMm", "attributes":{"prefix":"slab.equipment", "key":"...", "key_kebab":"slab.equipment.max-thickness-mm", "default_value":"240.0", ...}, ...}
      ],
      "relations": [
        {"kind":"contains", "source":"com.ontong.slab.config", "target":"com.ontong.slab.config.EquipmentProperties", "line":11, "attributes":{}},
        {"kind":"has_config", "source":"...EquipmentProperties", "target":"slab.equipment.maxThicknessMm", "line":30, "attributes":{}}
      ]
    },
    ...
  }
}
```

**활용 예 (jq)**:
```bash
# 모든 매직넘버 (literal_number initializer 보유한 field) 한 줄로
jq '[.files | to_entries[] | .value.entities[] | select(.kind=="field" and .attributes.initializer_kind=="literal_number") | {fqn:.qualified_name, val:.attributes.initializer}]' \
   sample-repos/slab-design-engine/.analyzed/entities.json

# Spring stereotype 별 통계
jq '[.files | to_entries[] | .value.entities[] | select(.kind=="spring_bean") | .attributes.stereotype] | group_by(.) | map({stereotype:.[0], count:length})' \
   sample-repos/slab-design-engine/.analyzed/entities.json

# 두 스냅샷 diff (parser 변경 전후)
diff <(jq -S . old.json) <(jq -S . new.json) | less
```

**.gitignore**: `**/.analyzed/` 추가 — regenerable artifact 라 commit 안 함. parser 변경 시 `python scripts/dump_entities_snapshot.py` 재실행.

**트러블슈팅**:
- `--repo not found` → 경로가 디렉토리가 아니면 exit 2.
- 큰 repo 에서 메모리 부족 → 현재 모든 결과 in-memory dict 후 일괄 write. 향후 streaming 으로 개선 가능 (필요 시점에).
- 두 번 실행 시 `generated_at` 변경되니 diff 가 항상 한 줄 차이. 자동화 비교 시 `jq 'del(.metadata.generated_at)'` 로 제외.

---

## OD-11-E1-i (EV) — `GapCandidate.evidence` + reevaluate + GapQueue UI 검증 (2026-04-25)

D3-3 미수거 3/3 완결. gap 후보의 근거 데이터를 UI에서 펼쳐보고, CONFLICTS_WITH 만 LLM 재평가 가능.

```bash
# 1. 단위 테스트
.venv/bin/python -m pytest tests/test_gaps_api.py -v
# → 20 passed (기존 15 + 신규 5)
#   - test_scan_response_includes_evidence_for_conflicts
#   - test_reevaluate_unknown_gap_returns_404
#   - test_reevaluate_missing_in_gap_returns_422
#   - test_reevaluate_without_comparator_returns_503
#   - test_reevaluate_calls_comparator_and_updates_gap
```

**evidence dict 구조 (CONFLICTS_WITH 후보)**:
```jsonc
// stage="rule_ast" (수량 mismatch)
{
  "stage": "rule_ast",
  "rule_statement": "두께는 240mm 이하여야 한다",
  "fragment_text": "두께 250mm 이상 허용",
  "mismatch": "numbers: [240] vs [250]"
}
// stage="drift" (embedding cosine < cutoff)
{
  "stage": "drift",
  "rule_statement": "...",
  "fragment_text": "...",
  "cosine": 0.421,
  "cutoff": 0.65
}
// + LLM 재평가 후 (override 시 위에 추가)
{
  ...,
  "llm_reasoning": "재무 영향 큼: 250mm slab 거부 시 주문 손실",
  "llm_severity": "critical"
}
```

**API 시연**:
```bash
# 1. scan 실행 → gap 후보 목록 받기
curl -X POST http://localhost:8001/api/modeling/gaps/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_id":"slab-design-engine"}' | jq '.conflicts[0]'
# →
# {
#   "id": "rule_ast|...|...",
#   "direction": null,
#   "target_fqn": "...",
#   "counterpart_fqn": "...",
#   "severity": "high",
#   "evidence": {"stage":"rule_ast", "rule_statement":"...", "fragment_text":"...", "mismatch":"..."}
# }

# 2. 단일 gap LLM 재평가 (CONFLICTS_WITH 만)
GAP_ID="rule_ast|com.x.M.check#rule1|doc#sec#f0"
curl -X POST "http://localhost:8001/api/modeling/gaps/${GAP_ID}/reevaluate" | jq
# →
# {
#   ...,
#   "severity": "critical",   ← LLM 이 격상
#   "evidence": {
#     ...,
#     "llm_reasoning": "재무 영향 큼: ...",
#     "llm_severity": "critical"
#   }
# }
```

**에러 시나리오**:
```bash
# MISSING_IN gap → 422
curl -X POST http://localhost:8001/api/modeling/gaps/missing-in-gap-id/reevaluate
# → 422 {"detail":"reevaluate is only supported for CONFLICTS_WITH gaps; ..."}

# 존재 안 함 → 404
curl -X POST http://localhost:8001/api/modeling/gaps/nope/reevaluate
# → 404 {"detail":"gap nope not found"}

# Comparator 미설정 → 503 (ONTONG_LLM_COMPARATOR=openai 안 켰을 때)
# → 503 {"detail":"LLM comparator not configured (set ONTONG_LLM_COMPARATOR=openai)"}
```

**프런트 UI 시연**:
1. `localhost:3000` → "갭 큐" 탭 → "스캔 실행" 버튼 (E1-h SSE 라이브 진행 표시)
2. CONFLICTS_WITH 행 좌측 `▸` 토글 → 펼치면 `<pre>` JSON evidence panel
3. CONFLICTS_WITH 행 우측 "재평가" 버튼 (Sparkles 아이콘) → 백엔드 호출 후 in-place 갱신 (severity badge + evidence 즉시 갱신)
4. MISSING_IN 행은 evidence 비어있음 + 토글 disabled (▸ 회색)

**구현 패턴 — 백엔드 reevaluate**:
```python
# backend/modeling/api/gaps_api.py
@router.post("/{gap_id}/reevaluate")
async def reevaluate_gap(gap_id: str):
    _, store = _require_initialized()
    gap = store.get(gap_id)
    if gap is None: raise HTTPException(404, ...)
    if gap.direction is not None: raise HTTPException(422, "CONFLICTS_WITH only")
    if _llm_comparator is None: raise HTTPException(503, "comparator not configured")

    # evidence 의 텍스트로 stub 객체 재구성 — registry lookup 회피
    stub_rule = BusinessRule(qualified_name=gap.target_fqn, statement=gap.evidence["rule_statement"], ...)
    stub_fragment = ManualFragment(qualified_name=gap.counterpart_fqn, text=gap.evidence["fragment_text"], ...)

    new_severity, new_reasoning = await asyncio.to_thread(
        _llm_comparator.compare,
        rule=stub_rule, fragment=stub_fragment,
        prior_severity=gap.severity, config=ScanConfig(repo_id="<reevaluate>", ...),
    )

    updated = replace(gap,
        severity=new_severity,
        description=f"{gap.description} | reevaluate: {new_reasoning}",
        evidence={**gap.evidence, "llm_reasoning": new_reasoning, "llm_severity": new_severity.value},
    )
    store.upsert(updated)
    return GapCandidateDTO.from_candidate(updated)
```

**트러블슈팅**:
- evidence 가 빈 dict → 그 gap 은 E1-i 이전 코드로 만들어진 것 (마이그레이션 없음, 재 scan 필요).
- 토글 ▸ 가 disabled (회색) → evidence 없음. MISSING_IN gap 은 정상 동작 (의도).
- 재평가 버튼 안 보임 → MISSING_IN gap 이거나 이미 confirmed 됨. CONFLICTS_WITH + non-confirmed 만 노출.
- 재평가 후 severity 변경 안 됨 → comparator 가 prior severity 그대로 반환 (graceful degrade case 또는 LLM 이 같은 severity 판단).

---

## OD-11-E1-h (SSE) — `gaps_api.scan_stream` 진짜 stage-by-stage streaming 검증 (2026-04-25)

D3-3 미수거 2/3 완료. 기존 buffered-flush PoC 제거. 클라이언트가 각 stage 를 실시간으로 받음.

```bash
# 1. 단위 테스트
.venv/bin/python -m pytest tests/test_gaps_api.py -v
# → 15 passed (기존 12 + 신규 3)
# 핵심 신규 :
#   - test_scan_stream_pattern_pushes_stages_via_threadsafe_queue
#     → 패턴 자체가 실시간 동작 증명 (gate 5초 timeout 으로 buffered 리그레션 차단)
#   - test_scan_stream_emits_complete_event_with_payload
#   - test_scan_stream_propagates_scan_exception (worker 예외 → "error" SSE event)

# 2. 실 uvicorn 환경 E2E 시연 (manual — TestClient ASGITransport 한계 우회)
# 백엔드 띄움
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload &
sleep 2

# RuleRegistry 시드 (E1-g 활용)
.venv/bin/python -c "
import requests
# (TODO : 향후 /api/modeling/rules/seed 엔드포인트 추가되면 거기로)
# 현재는 REPL 직접 :
from pathlib import Path
from backend.main import _rule_registry  # lifespan 가 전역 노출 안 하면 import 변경
from backend.modeling.gap_detection import seed_rules_from_repo
seed_rules_from_repo(
    Path('sample-repos/slab-design-engine/src/main/java'),
    'slab-design-engine',
    _rule_registry,
)
"

# SSE 실시간 시연 — curl 로 stage 별 도착 시각 확인
curl -N -X POST http://localhost:8001/api/modeling/gaps/scan/stream \
  -H "Content-Type: application/json" \
  -d '{"repo_id":"slab-design-engine"}' \
  --no-buffer 2>&1 | while read -r line; do echo "[$(date +%H:%M:%S.%3N)] $line"; done
```

**기대 출력 (실시간 시각)**:
```
[14:30:01.123] event: scanning
[14:30:01.124] data: {"stage": "scanning"}
[14:30:01.124]
[14:30:01.135] event: stage1_missing_in
[14:30:01.135] data: {"stage": "stage1_missing_in"}
[14:30:01.135]
[14:30:03.456] event: stage2_conflicts                  ← stage1 후 ~2초 (CPU 작업)
[14:30:03.456] data: {"stage": "stage2_conflicts"}
[14:30:03.456]
[14:30:03.470] event: complete
[14:30:03.470] data: {"code_only":[...],"manual_only":[...],"conflicts":[...],"errors":[]}
[14:30:03.471]
```

**Before (buffered-flush PoC)** :
```
[14:30:03.460] event: scanning      ← 4 stage 전부 같은 시각에 한꺼번에 도착
[14:30:03.460] event: stage1_missing_in
[14:30:03.460] event: stage2_conflicts
[14:30:03.461] event: complete
```

**구현 패턴**:
```python
# backend/modeling/api/gaps_api.py scan_stream_endpoint
loop = asyncio.get_running_loop()
queue: asyncio.Queue = asyncio.Queue()

def _on_progress(stage):
    if stage == STAGE_COMPLETE:
        return  # complete 는 result payload 와 함께 별도 push
    loop.call_soon_threadsafe(queue.put_nowait, (stage, {"stage": stage}))

def _sync_scan():
    try:
        result = scanner.scan(..., on_progress=_on_progress)
        payload = json.loads(_unified_to_response(result).model_dump_json())
        loop.call_soon_threadsafe(queue.put_nowait, (STAGE_COMPLETE, payload))
    except Exception as e:
        loop.call_soon_threadsafe(queue.put_nowait, ("error", {"detail": ...}))
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

worker_task = asyncio.create_task(asyncio.to_thread(_sync_scan))

async def stream():
    try:
        while True:
            item = await queue.get()
            if item is None:
                return
            event_name, data = item
            yield _sse(event_name, data)
    finally:
        if not worker_task.done():
            await worker_task
```

**에러 시나리오 시연**:
```bash
# 빈 repo_id 보내면 422, 실제 scan 도중 예외는 SSE "error" event 로
# (예: rule_source 가 raise 한 경우)
curl -N -X POST http://localhost:8001/api/modeling/gaps/scan/stream \
  -H "Content-Type: application/json" \
  -d '{"repo_id":"non-existent"}' --no-buffer
# → event: scanning / event: stage1_missing_in / event: stage2_conflicts / event: complete (정상, errors=[])
```

**TestClient 한계 메모**:
- `httpx.AsyncClient + ASGITransport` 로 E2E 실시간 검증 시도 → ASGITransport 가 SSE chunks 를 버퍼링해 클라이언트가 stage1 을 worker 5초 timeout 후에야 받음. ASGITransport 의 sync 본질 한계.
- pytest 우회 : `test_scan_stream_pattern_pushes_stages_via_threadsafe_queue` 가 진짜 asyncio.Queue + worker thread + threading.Event gate 로 패턴 자체 검증. buffered-flush 였다면 main loop 가 stage1 못 받고 5초 timeout.
- 실 uvicorn 의 chunked transfer + curl `--no-buffer` 조합으로 manual 시연 (위 명령).

**트러블슈팅**:
- complete event 안 옴 → worker 예외 발생. log 확인 (`scan_stream worker failed`). "error" event 가 마지막에 있을 것.
- stage 가 한꺼번에 도착 → `--no-buffer` 빠짐, 또는 reverse proxy (nginx) 가 SSE 를 버퍼링. nginx 설정에 `proxy_buffering off;` 필요.
- 클라이언트 조기 끊김 → finally 에 `worker_task` 정리 있어 thread leak 없음.

---

## OD-11-E1-g (RR) — `RuleRegistry` + auto-pull 검증 (2026-04-25)

D3-3 미수거 1/3 완료. A3 BusinessRule 을 repo 단위로 보관하는 store + `gap_scan` 이 body 비어도 auto-pull. 결과: `POST /api/modeling/gaps/scan {"repo_id":"slab-design-engine"}` 단발 호출만으로 전체 gap detection 동작.

```bash
# 1. 단위 테스트 — 16 케이스
.venv/bin/python -m pytest tests/test_rule_registry.py -v
# → 16 passed in 0.11s

# 2. End-to-end : Slab repo seed → auto-pull scan
.venv/bin/python -c "
from pathlib import Path
from backend.modeling.gap_detection import (
    InMemoryRuleRegistry, seed_rules_from_repo,
    InMemoryGapStore, MissingInDetector, GapScanner,
    HierarchicalGapEngine, RuleASTDiffer, CosineDrifter, HashingTextEmbedder,
)
from backend.modeling.gap_detection.gap_models import ScanConfig
from backend.modeling.manuals.manual_models import GapMode, GapDetectedBy

reg = InMemoryRuleRegistry()
result = seed_rules_from_repo(
    Path('sample-repos/slab-design-engine/src/main/java'),
    'slab-design-engine',
    reg,
)
print(f'Seeded: {result.total_files_scanned} java files → {result.total_rules} BusinessRule')
print(f'Registry repos: {reg.repos()}')

gap_store = InMemoryGapStore()
scanner = GapScanner(
    missing_detector=MissingInDetector(gap_store=gap_store),
    gap_engine=HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(),
        drifter=CosineDrifter(embedder=HashingTextEmbedder()),
        gap_store=gap_store,
    ),
    fragment_source=None,
    rule_source=reg,
)
res = scanner.scan(
    config=ScanConfig(repo_id='slab-design-engine', gap_mode=GapMode.HIERARCHICAL, detected_by=GapDetectedBy.HIERARCHICAL),
    business_rules=None,    # ← body 미지정 → auto-pull
    fragments=[],
)
print(f'Scan: errors={res.errors}, conflicts={len(res.conflicts)}, code_only={len(res.code_only)}, manual_only={len(res.manual_only)}')
"
```

**기대 출력**:
```
Seeded: 11 java files → 16 BusinessRule
Registry repos: {'slab-design-engine'}
Scan: errors=[], conflicts=0, code_only=0, manual_only=0
```

(fragments 가 비어있으니 conflict/missing 발생 안 함이 정상 — auto-pull 자체 동작 검증.)

**Auto-pull 정책 (E1-g)**:
| body 값 | 동작 |
|---|---|
| `business_rules=None` | RuleRegistry 에서 `repo_id` 키로 auto-pull |
| `business_rules=[]` | 빈 list 그대로 사용 (auto-pull 차단) |
| `business_rules=[r1, r2]` | 명시 list 그대로 사용 |

`fragments` 와 동일한 정책. `described_in` 은 아직 전용 store 가 없어서 항상 body 명시.

**API body 변경**:
```jsonc
// 기존
POST /api/modeling/gaps/scan
{"repo_id":"slab-design-engine", "rules":[{...}], "fragments":[{...}]}

// 신규 — body 비워도 동작
POST /api/modeling/gaps/scan
{"repo_id":"slab-design-engine"}
// → rules: RuleRegistry auto-pull, fragments: ManualRegistry auto-pull
```

**운영 시드**:
- `seed_rules_from_repo()` 는 Python 함수로 노출. startup auto-seeding 안 함.
- 운영 도입 시 옵션: (i) `POST /api/modeling/rules/seed` 엔드포인트 / (ii) ENV `ONTONG_RULE_SEED_REPOS=slab-design-engine:./sample-repos/...` startup 분기 / (iii) ManualUpload 처럼 watch_folder 도입.

**트러블슈팅**:
- registry 비어있으면 (seed 안 한 repo_id) → auto-pull 결과 빈 list. scan 에러 없이 conflict 0 반환. 의도된 동작.
- 같은 repo seed 두 번 → idempotent (FQN 결정성). count 그대로.
- non-Java 파일 (README.md, .yaml) → `total_files_scanned=0` 정상 (rglob `*.java` 만 매치).

---

## OD-11-E1-f (CPA) — `ConfigPropertiesAnalyzer` 11번째 Spring analyzer 검증 (2026-04-25)

`@ConfigurationProperties` 클래스의 instance field 를 `config_property` 엔티티 + `has_config` 엣지로 emit. CONFLICTS_WITH gap 감지에서 매뉴얼 ↔ 코드 default 값 직접 비교의 핵심 입력.

```bash
# 1. 단위 테스트 — 27 케이스
.venv/bin/python -m pytest tests/test_spring_config_properties_analyzer.py -v
# → 27 passed in 0.05s

# 2. Slab 11-analyzer end-to-end — REPL
.venv/bin/python -c "
from pathlib import Path
from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.spring import (
    AopAnalyzer, BeanUtilsAnalyzer, ConfigPropertiesAnalyzer, DIAnalyzer,
    EventsAnalyzer, HttpAnalyzer, MapStructAnalyzer, NativeSqlAnalyzer,
    ProfileAnalyzer, ReflectionAnalyzer, ScheduledAnalyzer,
)
analyzers = [DIAnalyzer(), AopAnalyzer(), HttpAnalyzer(), EventsAnalyzer(),
             ScheduledAnalyzer(), ProfileAnalyzer(), ReflectionAnalyzer(),
             MapStructAnalyzer(), BeanUtilsAnalyzer(), NativeSqlAnalyzer(),
             ConfigPropertiesAnalyzer()]
parser = JavaParser(spring_analyzers=analyzers)
root = Path('sample-repos/slab-design-engine/src/main/java')
total_e, total_r = 0, 0
for fp in sorted(root.rglob('*.java')):
    pr = parser.parse_file(fp, fp.read_text())
    total_e += len(pr.entities); total_r += len(pr.relations)
    for e in pr.entities:
        if e.kind == 'config_property':
            print(f'  {e.qualified_name}: default={e.attributes.get(chr(34)+\"default_value\"+chr(34))} kebab={e.attributes.get(chr(34)+\"key_kebab\"+chr(34))}')
print(f'총합: {total_e} entities, {total_r} relations')
"
```

**기대 출력**:
```
  slab.equipment.rollingMillMaxWidthMm: default=2400.0  kebab=slab.equipment.rolling-mill-max-width-mm
  slab.equipment.furnaceMaxLengthMm:    default=12000.0 kebab=slab.equipment.furnace-max-length-mm
  slab.equipment.craneMaxLoadKg:        default=45000.0 kebab=slab.equipment.crane-max-load-kg
  slab.equipment.minThicknessMm:        default=180.0   kebab=slab.equipment.min-thickness-mm
  slab.equipment.maxThicknessMm:        default=240.0   kebab=slab.equipment.max-thickness-mm
총합: 95 entities, 177 relations
```

**비교**: 10-analyzer (CPA 제외) = 90 entities / 172 relations → CPA 추가로 정확히 +5/+5.

**3 어노테이션 형식 모두 처리**:
- `@ConfigurationProperties(prefix = "slab.equipment")`  ← keyword (Slab 의 형식)
- `@ConfigurationProperties("slab.equipment")`  ← single value
- `@ConfigurationProperties`  ← marker (prefix="")

**Field 선택 규칙**:
- 비-`static` instance field 만 (constants 제외)
- `final` 허용 (Spring Boot 2.2+ 생성자 바인딩 호환)

**attributes 8 키**:
| 키 | 의미 | 예 |
|---|---|---|
| `prefix` | 어노테이션 prefix | `"slab.equipment"` |
| `key` | canonical FQN (camelCase) | `"slab.equipment.maxThicknessMm"` |
| `key_kebab` | Spring relaxed binding alias | `"slab.equipment.max-thickness-mm"` |
| `field_name` | 필드 이름 | `"maxThicknessMm"` |
| `field_type` | 선언 타입 | `"double"` |
| `default_value` | initializer literal raw text | `"240.0"` (없으면 키 부재) |
| `bound_class_fqn` | 소속 클래스 FQN | `"com.ontong.slab.config.EquipmentProperties"` |
| `bound_field_fqn` | 백링크 FIELD FQN | `"...EquipmentProperties.maxThicknessMm"` |

**다운스트림 활용**:
- CONFLICTS_WITH : `RuleASTDiffer.find_conflicts()` 에서 매뉴얼 룰 statement ↔ config_property `default_value` 직접 비교 (`240` ≠ `250`).
- Impact Analysis : `bound_field_fqn` 로 FIELD entity 와 백링크 — config 변경 시 사용 메서드 추적.
- application.yml 검색 : `key_kebab` 으로 양쪽 표기 모두 lookup 가능.

**runtime wiring**:
- `backend/main.py` 미등록 (현재 Spring analyzer 들은 lifespan wiring 없음). Phase E 코드 분석 파이프라인을 FastAPI 로 노출할 때 11 analyzer 모두 함께 합류 예정.

---

## OD-11-E1-d (A3) — Javadoc → BusinessRule 추출 검증 (2026-04-25)

CONFLICTS_WITH gap 감지의 코드 쪽 rule 입력. 한국어 Javadoc → `BusinessRule` Pydantic + `VALIDATES` 엣지 (REALIZES 가 아님 — 명세 정정).

```bash
# 1. 단위 테스트 — TDD 23 케이스
.venv/bin/python -m pytest tests/test_javadoc_rule_extractor.py -v
# → 23 passed in 0.10s

# 2. Slab 4 파일 일괄 추출 — REPL
.venv/bin/python -c "
from pathlib import Path
from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.javadoc_rule_extractor import extract_rules_from_file

parser = JavaParser()
files = [
    'sample-repos/slab-design-engine/src/main/java/com/ontong/slab/optimizer/WeightMaximizer.java',
    'sample-repos/slab-design-engine/src/main/java/com/ontong/slab/constraint/EquipmentConstraintChecker.java',
    'sample-repos/slab-design-engine/src/main/java/com/ontong/slab/domain/Slab.java',
    'sample-repos/slab-design-engine/src/main/java/com/ontong/slab/config/EquipmentProperties.java',
]
total = 0
for fp in files:
    text = Path(fp).read_text()
    pr = parser.parse_file(Path(fp), text)
    rules, edges = extract_rules_from_file(fp, text, pr)
    print(f'{fp.split(chr(47))[-1]}: {len(rules)} rules')
    for r, e in zip(rules, edges):
        print(f'  [{r.severity.value:4}] {r.qualified_name} → {e.target}')
        print(f'         {r.statement[:80]}')
    total += len(rules)
print(f'총합: {total} BusinessRule')
"
```

**기대 출력 (요약)**:
```
WeightMaximizer.java: 7 rules                    ← 목적식 5 + 수주 사양 2 (전부 SOFT)
EquipmentConstraintChecker.java: 7 rules         ← 4 class bullets + 3 method-level
  [hard] ...rule4 — 크레인 최대 하중 초과 불가
  [hard] ...checkRollingMillWidth#rule1 — 압연 불가
  [hard] ...checkCraneLoad#rule1 — 이동 불가
Slab.java: 1 rules
  [hard] ...rule1 — IllegalArgumentException 던진다
EquipmentProperties.java: 0 rules                ← descriptive only (정상)
총합: 15 BusinessRule
```

**FQN 규칙**: `{target_fqn}#rule{N}` (1-indexed, target 별 카운터, 결정성).

**Severity 규칙**:
- HARD: `불가|금지|허용되지 않|던진다|차단|거부|초과할 수 없|IllegalArgumentException|Exception` 키워드
- SOFT: 나머지 (comparators, imperatives)

**다운스트림 활용**:
- `RuleASTDiffer.find_conflicts(rules, fragments)` 의 입력으로 직접 사용 가능. 매뉴얼 룰 ↔ 코드 룰 통합 비교.
- `terms_ref` 는 빈 list — C3 `TermResolver` 가 statement 에서 BusinessTerm FQN 매칭해 채움 (다음 단계).

**트러블슈팅**:
- 룰이 안 잡힘 → Javadoc 이 `/** */` 가 맞는지, 룰 키워드 (이상/이하/불가/이어야 한다 등) 가 있는지 확인. 단순 설명문은 자동 reject.
- 잘못된 declaration 에 매칭 → `_next_declaration_sibling()` 이 modifier 등을 만나면 None 반환. Javadoc 과 declaration 사이에 다른 코드 없는지 확인.
- field-level Javadoc 무시됨 → v1 spec. `WEIGHT_BIAS_FACTOR` 위 Javadoc 같은 것은 향후 확장.

---

## OD-11-E1-c (A2) — JavaParser field 리터럴 캡처 검증 (2026-04-25)

CONFLICTS_WITH gap 감지의 코드 쪽 입력 (매직넘버 240/1.02/50) 이 그래프에 노출되는지 확인.

```bash
# 1. 단위 테스트 — TDD 20 케이스
.venv/bin/python -m pytest tests/test_java_parser_field_attributes.py -v
# → 20 passed in 0.06s

# 2. Slab 샘플 직접 파싱 — REPL
.venv/bin/python -c "
from pathlib import Path
from backend.modeling.code_analysis.java_parser import JavaParser
parser = JavaParser()
for fp in [
    'sample-repos/slab-design-engine/src/main/java/com/ontong/slab/optimizer/WeightMaximizer.java',
    'sample-repos/slab-design-engine/src/main/java/com/ontong/slab/config/EquipmentProperties.java',
]:
    res = parser.parse_file(Path(fp), Path(fp).read_text())
    print(f'=== {fp.split(chr(47))[-1]} ===')
    for e in res.entities:
        if e.kind == 'field':
            ftype = e.attributes.get('field_type', '<none>')
            init = e.attributes.get('initializer', '<none>')
            kind = e.attributes.get('initializer_kind', '<none>')
            print(f'  {e.name}: type={ftype} init={init} kind={kind}')
"
```

**기대 출력**:
```
=== WeightMaximizer.java ===
  GRID_STEP_MM: type=double init=50.0 kind=literal_number
  WEIGHT_BIAS_FACTOR: type=double init=1.02 kind=literal_number
  checker: type=EquipmentConstraintChecker init=<none> kind=<none>   ← 초기화식 없음
=== EquipmentProperties.java ===
  rollingMillMaxWidthMm: type=double init=2400.0 kind=literal_number
  furnaceMaxLengthMm:    type=double init=12000.0 kind=literal_number
  craneMaxLoadKg:        type=double init=45000.0 kind=literal_number
  minThicknessMm:        type=double init=180.0   kind=literal_number
  maxThicknessMm:        type=double init=240.0   kind=literal_number
```

**attributes 3 키 의미**:
- `field_type` : 선언 타입 raw text (primitive `double`/`int`, reference `String`, generic `List<String>`)
- `initializer` : 초기화식 raw text (literal text 또는 expression text — 없으면 키 자체 부재)
- `initializer_kind` : 6 분류 — `literal_number` / `literal_string` / `literal_boolean` / `literal_null` / `literal_char` / `expression`

**다운스트림 활용**: CONFLICTS_WITH gap 감지 시 `initializer_kind == "literal_number"` 인 field 만 매뉴얼 룰의 수치와 비교. 표현식 초기화 (`computed = compute()`) 는 동적 값이므로 비교 대상 아님.

**트러블슈팅**:
- attrs 가 `{}` 로 비어있으면 → `backend/modeling/code_analysis/java_parser.py` 가 구버전. `_extract_field` 에 `attributes` 인자 전달 라인 / `_classify_initializer` helper 존재 여부 확인.
- `literal_number` 가 안 잡히고 `expression` 으로 분류되면 → `_NUMERIC_LITERAL_TYPES` 화이트리스트에 새 tree-sitter Java node type 추가 필요.

---

## 사전 준비

```bash
# Neo4j + ChromaDB + Redis
docker compose up -d neo4j chroma redis

# 백엔드 (반드시 새 코드로 재시작)
source venv/bin/activate && set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# 프론트엔드
cd frontend && npm run dev
```

### 헬스체크
```bash
# Engine API
curl -s http://localhost:8001/api/modeling/engine/status
# → {"repo_id":"","mapping_count":0,...,"ready":false}  (데모 로드 전)

# Source API
curl -s http://localhost:8001/api/modeling/source/tree/scm-demo
# → 데모 로드 전에는 빈 children, 로드 후 파일 트리 반환

# health에 simulation, engine_query 포함 확인
curl -s http://localhost:8001/api/modeling/health
```

---

## Part A: 분석 콘솔 + 시뮬레이션 (Engine Phase 1a)

### A-1: SCM 데모 로드

1. 브라우저에서 `http://localhost:3000` 접속
2. 상단 **Modeling** 탭 클릭
3. **확인**: 사이드바 구조
   - MAIN: 분석 콘솔 (기본 선택) / 시뮬레이션 / 매핑 워크벤치
   - 설정: 코드 분석 / 도메인 온톨로지 / 매핑 관리 / 검토 요청
4. 메인 영역에 **"SCM 데모 프로젝트 로드"** 버튼 클릭
5. **확인**:
   - Repository가 `scm-demo`로 설정됨
   - 분석 콘솔 화면으로 자동 전환
   - 예시 질의 4개 표시 (안전재고, 주문 서비스, 생산 계획, InventoryManager)
   - 사이드바에 코드분석/온톨로지/매핑 옆 녹색 체크 아이콘

```bash
curl -s http://localhost:8001/api/modeling/engine/status
# → {"repo_id":"scm-demo","simulatable_entities":9,"ready":true}
```

---

### A-2: 한국어 영향 분석 (핵심 데모)

1. 분석 콘솔의 검색창에 **"안전재고 계산 로직 변경"** 입력 → "분석" 클릭
2. **확인**:
   - 검색 대상: `SafetyStockCalculator`
   - 도메인 매핑: → `SCOR/Plan/InventoryPlanning`
   - 영향받는 프로세스 목록 (distance 표시)
   - "시뮬레이션 실행" 버튼 표시
3. 다른 예시도 테스트:
   - "주문 서비스 수정" → `OrderService`
   - "생산 계획 변경" → `ProductionPlanner`
   - "InventoryManager" → 영문 직접 매칭

```bash
curl -s -X POST http://localhost:8001/api/modeling/engine/query \
  -H "Content-Type: application/json" \
  -d '{"query":"안전재고 계산 로직 변경","repo_id":"scm-demo"}'
```

---

### A-3: 시뮬레이션 (분석 → 시뮬레이션 연결)

1. A-2에서 **"시뮬레이션 실행"** 버튼 클릭
2. **확인**:
   - "시뮬레이션" 탭이 자동 활성화
   - 드롭다운에 `SafetyStockCalculator — 안전재고 계산` 자동 선택
   - 3개 파라미터 슬라이더: `safety_factor` 1.65, `lead_time_days` 14, `service_level` 0.95
3. `safety_factor` 슬라이더를 **2.5**로 변경
4. **확인**: "실행" 버튼 활성화, 기존값 취소선 표시
5. **"실행"** 클릭
6. **확인**:
   - 안전재고 수준: 123 → 187개 (+51.5%) ↑
   - 재주문점: 823 → 887개 (+7.7%) ↑

```bash
curl -s -X POST http://localhost:8001/api/modeling/engine/simulate \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"com.ontong.scm.inventory.SafetyStockCalculator","repo_id":"scm-demo","params":{"safety_factor":"2.5"}}'
```

---

### A-4: 다른 엔티티 시뮬레이션

1. 시뮬레이션 탭 드롭다운 → **OrderService — 주문 서비스** 선택
2. **확인**: `order_batch_size` (기본 10), `auto_approve_threshold` (기본 50000)
3. `order_batch_size`를 20으로 변경 → "실행"
4. **확인**: before/after 결과 표시

---

### A-5: Term Resolution 매핑표 (9개 엔티티)

| 한국어 입력 | 기대 결과 |
|------------|-----------|
| 안전재고 계산 로직 변경 | SafetyStockCalculator |
| 재고 관리 | InventoryManager |
| 주문 서비스 수정 | OrderService |
| 생산 계획 변경 | ProductionPlanner |
| 작업 지시 | WorkOrderProcessor |
| 구매 주문 | PurchaseOrderService |
| 공급업체 평가 | SupplierEvaluator |
| 배송 추적 | ShipmentTracker |
| 창고 관리 | WarehouseController |

---

## Part B: 매핑 워크벤치 (Phase 2a)

### B-1: 워크벤치 진입 및 레이아웃 확인

1. SCM 데모가 로드된 상태에서 (Part A-1 완료 후)
2. 좌측 사이드바에서 **매핑 워크벤치** 클릭
3. **확인**:
   - 화면이 55:45 비율로 좌/우 분할
   - 좌측: React Flow 도메인 그래프 + 하단 코드 엔티티 패널
   - 우측: "소스 코드" 헤더 + 파일 트리 + 에디터 영역
   - 도메인 그래프가 화면에 맞게 자동 피팅 (fitView)
   - 분할선(리사이저)을 마우스로 드래그해서 비율 조절 가능

---

### B-2: 도메인 그래프 확인

워크벤치 화면에서:

1. 도메인 그래프에 SCOR 노드들이 트리 구조로 표시되는지 확인
   - SCOR (루트) → Plan, Source, Make, Deliver (1단계)
   - 각 하위 노드 (DemandPlanning, InventoryPlanning 등)
2. **확인**:
   - 매핑된 노드: **초록색 테두리** + "N개 코드 연결" 텍스트
   - 매핑 안 된 노드: **회색 테두리**
   - 초록 노드 7개: InventoryPlanning, DemandPlanning, Manufacturing, Purchasing, SupplierSelection, Transportation, Warehousing
   - Zoom In/Out, Fit View 컨트롤 (우측 상단)
   - 미니맵 (우측 하단)
   - "도메인 노드에 코드 엔티티를 드래그하여 매핑" 안내 (좌측 상단)

---

### B-3: 코드 엔티티 패널

1. 좌측 하단 **코드 엔티티** 패널 확인
   - class/interface만 표시 (method, field 제외)
   - 각 엔티티 옆에 상태 원형: 초록(매핑됨) / 빨강(미매핑)
   - 매핑된 엔티티 우측에 도메인 이름 표시
2. **확인**:
   - InventoryManager: 초록 원 + "InventoryPlanning"
   - Product, Supplier, Warehouse (model 패키지): 빨강 원 (미매핑)
3. 검색창에 `Order` 입력 → OrderService, OrderStatus만 필터링
4. 검색 초기화 후 `Warehouse` 입력 → WarehouseController만 표시

---

### B-4: 파일 트리 탐색 및 소스 보기

1. 우측 파일 트리에서 `src > main > java > com > ontong > scm` 확장
2. `inventory` 폴더 확장 → **InventoryManager.java** 클릭
3. **확인**:
   - Monaco 에디터에 Java 소스 코드가 syntax highlight되어 표시
   - 파일 경로 바에 `src/main/java/com/ontong/scm/inventory/InventoryManager.java`
   - "10개 엔티티" 텍스트 (파일 경로 바 우측)
   - 에디터가 read-only (편집 불가)
   - 매핑된 엔티티 라인에 좌측 세로선 마커 (초록/노랑)
4. 다른 파일 선택: `order > OrderService.java` 클릭 → 파일 전환 확인
5. 파일 검색창에 `Safety` 입력 → `SafetyStockCalculator.java`만 트리에 표시

```bash
# Source File API 직접 확인
curl -s "http://localhost:8001/api/modeling/source/file/scm-demo?path=src/main/java/com/ontong/scm/inventory/InventoryManager.java" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'entities: {len(d[\"entities\"])}, language: {d[\"language\"]}')"
# → entities: 10, language: java
```

---

### B-5: 양방향 연동 — Canvas → Viewer

1. 좌측 도메인 그래프에서 **InventoryPlanning** 노드 클릭
2. **확인**: 매핑된 코드 엔티티 확인 (InventoryManager, SafetyStockCalculator)

---

### B-6: 양방향 연동 — Viewer → Canvas

1. 우측에서 `InventoryManager.java` 파일이 열린 상태
2. 에디터의 클래스 선언부 (8번째 줄 부근) 클릭
3. **확인**:
   - 좌측 도메인 그래프에서 **InventoryPlanning** 노드에 ring 하이라이트
   - 매핑 안 된 코드 영역 클릭 시 하이라이트 없음

```bash
# Entity Location API — 양방향 연동의 백엔드
curl -s "http://localhost:8001/api/modeling/source/entity/scm-demo/com.ontong.scm.inventory.InventoryManager"
# → {"qualified_name":"...","file_path":"src/main/java/.../InventoryManager.java","line_start":8,"line_end":47}
```

---

### B-7: 드래그 & 드롭 매핑 생성

1. 엔티티 패널에서 미매핑 엔티티 (빨강 원, 예: `Product`) 를 드래그
2. 도메인 그래프의 아무 노드 위에 드롭
3. **확인**:
   - 드래그 시 커서: grab → link 아이콘
   - 해당 노드의 연결 카운트 증가
   - 엔티티의 원이 빨강 → 초록으로 변경
   - 새로고침 불필요 (즉시 반영)

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `{"detail":"Not Found"}` on `/engine/*` | 백엔드가 이전 코드로 실행 중 | uvicorn 재시작 |
| 파일 트리가 비어있음 | Seed 미실행 | "SCM 데모 프로젝트 로드" 클릭 |
| 도메인 그래프 안 보임 | 온톨로지 미로드 | Seed 다시 실행 |
| 에디터에 코드 안 나옴 | 파일 미선택 | 파일 트리에서 .java 파일 클릭 |
| 그래프 노드가 작게 보임 | fitView 미적용 | Fit View 버튼 클릭 |
| `simulatable_entities: 0` | 데모 미로드 | "SCM 데모 프로젝트 로드" 클릭 |
| 시뮬레이션 "실행" 비활성 | 파라미터 미변경 | 슬라이더를 기본값에서 변경 |
| Term resolve 실패 | fuzzy threshold 미달 | 정확한 한국어 alias 또는 영문 클래스명 사용 |
| Neo4j 연결 실패 | Docker 미실행 | `docker compose up -d neo4j` |
| 프론트엔드 API 에러 | Next.js proxy 설정 | `next.config.ts`에 `/api/modeling/*` → 8001 확인 |

---

## Part C — Method Workbench (P17 BusinessRule 검토 큐 포함)

### C-1: Workbench 진입 + 메서드 트리
1. 좌측 사이드바 → **Workbench** 클릭 (default view)
2. 가이드 배너 확인 — "Workbench 시작 가이드" (좌측 트리 → 코드+anchor → 자동 매핑 → 「LLM 보강」)
3. 좌측 메서드 트리: nested 모드 default, common prefix `com.example.slabdesign.` 헤더 표시
4. `feature.sd` → `process` → `std` → `service` 까지 펼치기

### C-2: 메서드 선택 → 4 패널 동기화
1. `CastSpecService` 클래스 노드 펼치기 → `lookup()` 메서드 클릭
2. **확인**:
   - 중앙 코드 패널: source 표시 + anchor highlight (param 보라 / local 청록)
   - C-R Ontology 패널: anchor 카드 + auto-suggest (alias matched)
   - 우측 R 패널 default tab "⚖️ 룰 검토" 자동 선택

### C-3: BusinessRule 검토 큐 (P17 신규)
1. 우측 R 패널 → "⚖️ 룰 검토" 탭 (헤더에 amber 배지 = 저장소 전체 미확정 수, 예: `62`)
2. 메서드 단위 카드 표시:
   - kind 배지 (lookup 청록 / formula 파랑 / throw 핑크 / guard 노랑 / bound 빨강 / regex 녹색 / enum 보라)
   - severity 배지 (hard 빨강 / soft 회색)
   - 미확정: amber bg + 「확정」/「편집」/「거부」 버튼
   - 확정됨: emerald bg + 「✓ 확정됨」 라벨
3. **확정** 버튼 → `POST /api/modeling/rules/<fqn>%23<kind>-<idx>/confirm` → 카드 emerald 로 전환 + 헤더 배지 `-1`
4. **편집** 버튼 → 인라인 statement (textarea) + severity 토글 → 저장 시 `PUT /rules/<fqn>` → 화면 즉시 반영
5. **거부** 버튼 → confirm dialog → `POST /rules/<fqn>/reject` (실 SQLite 행 삭제) → 카드 사라짐
6. 「미확정만 / 전체」 토글로 확정된 rule 도 표시 가능

### C-4: 검증 (curl)

```bash
# 통계
curl -s http://127.0.0.1:8001/api/modeling/repos/slab-design-real/rules/stats
# 기대 by_kind: {'throw':13, 'lookup':10, 'javadoc':38, 'formula':43, 'bound':6, 'guard':9}

# 메서드 단위 미확정 rule
curl -s "http://127.0.0.1:8001/api/modeling/repos/slab-design-real/rules?confirmed=false&source_prefix=body&limit=5"

# Q-C=C3 정책: formula/throw/regex 는 자동 확정, guard/bound/enum/lookup 은 사람 검토
```

---

## Part D — 온톨로지 그래프 (P18 신규)

### D-1: 그래프 진입
1. 좌측 사이드바 → **온톨로지 그래프** 클릭 (Share2 아이콘, Workbench 다음 위치)
2. 헤더 stats 확인 — `term N · rule M · edge K`
3. 좌측 column = BusinessTerm (파랑), 우측 4 column = BusinessRule (녹색=확정 / 노랑=미확정)

### D-2: 노드 클릭 + 새 관계 만들기
1. 좌측 term 노드 (예: `품종코드`) 클릭 → 우측 detail 패널 표시
2. 「새 관계 추가」 폼 → dst 노드 검색 (예: `열연공장코드`) → 관계 dropdown (`related_to`) → 「관계 만들기」
3. 그래프 즉시 reload, 새 엣지 표시
4. `term → rule governs` 도 같은 방식 (예: `품종코드` 가 `SdLengthRangeAction.execute#guard-0` 을 govern)

### D-3: 필터 + 정리
1. 「관계 있는 노드만」 체크 → orphan 노드 숨김 (관계 검증 시 유용)
2. 「미확정 rule 포함」 체크 → 미확정 rule 도 그래프에 노출
3. 점선 엣지 = `rule.terms_ref` 자동 inferred (DB 미저장)

### D-4: 검증 (curl)

```bash
# 그래프 전체
curl -s "http://127.0.0.1:8001/api/modeling/repos/slab-design-real/ontology-graph"

# 새 관계
curl -s -X POST http://127.0.0.1:8001/api/modeling/relations -H "Content-Type: application/json" \
  -d '{"repo_id":"slab-design-real","src_kind":"term","src_fqn":"term.품종코드",
       "dst_kind":"term","dst_fqn":"term.열연공장코드","kind":"related_to",
       "rationale":"같은 도메인","source":"manual"}'

# 삭제
curl -s -X DELETE "http://127.0.0.1:8001/api/modeling/relations/<rel_id>"
```

### D-5: RelationKind 7 종 + 색상

| kind | 색상 | 페어 | 의미 |
|---|---|---|---|
| is_a | 보라 | term-term | 상위/하위 (품종코드 is_a 코드) |
| part_of | 청록 | term-term | 구성 (슬라브 part_of 주문) |
| synonym_of | 녹색 | term-term | 동의어 |
| related_to | 회색 | term-term | 일반 연관 |
| governs | 주황 | term-rule | term 이 rule 의 대상 |
| derives | 파랑 | rule-term | rule 이 term 에서 유도 |
| conflicts | 빨강 | rule-rule | rule 간 상충 |
