# OD-11-B8 — Impact/BFS hops 자율 조정 API + query engine 재설계 SPEC

**작성일**: 2026-04-19
**선행**: B7 완료 (3-way 엣지 확립: `static_literal`/`static_unresolved`/`runtime`)
**후행**: B9 (Slab sample E2E)
**범위**: `backend/modeling/query/query_engine.py` + `query_models.py` **신규 설계** (OD-10 에 지워진 구버전 복원 아님 — 매뉴얼 1차 → 코드 1차 방향 전환 반영)

---

## 0. 왜 이 단계가 필요한가

B7 까지가 완료되면 그래프에는 다음 엣지들이 축적된다:

```
CALLS{source: static_literal,  confidence: 0.9}   ← B7-1 정적 리터럴
CALLS{source: static_unresolved, confidence: 0.4} ← B7-1 해소 실패
CALLS{source: runtime,         confidence: 0.95}  ← B7-2 런타임 관측
CALLS{}   (소스 속성 없는 일반 호출)               ← JavaParser 기본
PROPAGATES_TO{confidence: 1.0|0.9|0.7|0.5}        ← B6 매핑
READS_TABLE / WRITES_TABLE                         ← B6-3
MAPS_URL / PUBLISHES / HANDLES / AUTOWIRES         ← B5
REFLECTS_AS{source: runtime, 0.95}                 ← B7-2
```

**Impact Analysis 3 main feature** 는 이 그래프 위에서 "어떤 엔티티를 바꾸면 어디까지 영향?" 을 BFS 로 답해야 한다. 이때 사용자 의도에 따라 3 가지 모드가 필요:

| 모드 | 필터 | 용도 |
|---|---|---|
| **safe** | `confidence >= 0.9` | "확실히 영향 받는 곳만. 배포 전 이중 확인용" |
| **observed** | `source IN {runtime, static_literal}` | "런타임 관측 + 정적 리터럴. 실사용 기준 영향 범위" |
| **potential** | 필터 없음 | "이론적으로 닿을 수 있는 모든 곳. 감사·리팩토링 계획용" |

또한 BFS hops 는 repo 크기에 따라 성능이 급격히 달라지므로, **최대 hops 자율 조정** 이 필요 (Q6 — OD-11-PLAN.md §4).

---

## 1. 이전 `query_engine.py` 와 근본적 차이

| 항목 | 구버전 (OD-10 이전) | **B8 신버전** |
|---|---|---|
| 입력 | 자연어 `term` + `MappingFile` | code entity FQN (method/class/field) 또는 식별 힌트 (HTTP path, event type 이름) |
| 출력 | `AffectedProcess` (domain_id, domain_name) — 매뉴얼 도메인 기반 | `AffectedEntity` — METHOD/HTTP_ENDPOINT/EVENT_TYPE/DB_TABLE 등 **코드 엔티티** |
| 그래프 접근 | Neo4j 직접 쿼리 | **추상 `GraphView` 인터페이스** — in-memory (ParseResult 리스트) / Neo4j 둘 다 지원 |
| 엣지 필터 | 없음 | `edge_sources` 집합 + `min_confidence` 파라미터 |
| 도메인 매핑 | 필수 (MappingService) | **Round 1 범위에서 제외**. Round 2 에서 개념 브릿지 위에 다시 올림 |
| hops | `depth` 파라미터 고정 | **hops 자율 조정** (max_hops + 자동 shrink 휴리스틱) |

핵심 변경: **"term → domain"** 이 아니라 **"code entity → code entity"** BFS. 도메인 매핑 복원은 Phase C 로 넘김.

---

## 2. API 제안

### 2.1 DTO (pydantic)

```python
from enum import StrEnum
from pydantic import BaseModel, Field

class ImpactMode(StrEnum):
    SAFE = "safe"              # confidence >= 0.9
    OBSERVED = "observed"      # source ∈ {runtime, static_literal}
    POTENTIAL = "potential"    # no filter

class ImpactQuery(BaseModel):
    target_fqn: str            # e.g. "com.acme.OrderService.dispatch"
    mode: ImpactMode = ImpactMode.OBSERVED
    max_hops: int = Field(default=5, ge=1, le=20)
    # 자율 조정 스위치 — max_hops 는 상한. 내부 휴리스틱으로 동적 축소 가능.
    auto_hops: bool = True
    # 추가 필터 (옵션)
    edge_kinds: set[str] | None = None   # e.g. {"calls","publishes","handles"}; None = all
    entity_kinds: set[str] | None = None # 결과 entity 필터

class AffectedEntity(BaseModel):
    qualified_name: str
    kind: str                  # "method" / "http_endpoint" / "event_type" / ...
    distance: int              # BFS hops
    confidence_min: float      # 경로 상 최소 confidence (병목)
    edge_source_chain: list[str]   # 각 hop 의 source ("runtime"/"static_literal"/"static_unresolved"/None)
    path: list[str]            # source → ... → qualified_name
    reasons: list[str]         # human-readable: "calls (runtime)" / "publishes (event X)" ...

class ImpactResult(BaseModel):
    source: str                # resolved FQN (same as query.target_fqn if exists)
    mode: ImpactMode
    hops_used: int             # 실제 수행한 hops (auto_hops 가 max_hops 보다 작게 줄였을 수 있음)
    hops_shrunk_reason: str | None   # "result_too_large" / "timeout" / None
    affected: list[AffectedEntity]
    unresolved_sources: list[str]  # "<reflection-site>" 로 끊긴 엣지 수집 (diagnostic)
    message: str
```

### 2.2 Engine

```python
class GraphView(Protocol):
    """In-memory / Neo4j 모두 구현 가능. 엣지 스트림만 노출."""
    def outgoing(self, fqn: str) -> list[EdgeRow]: ...
    def incoming(self, fqn: str) -> list[EdgeRow]: ...
    def entity(self, fqn: str) -> EntityRow | None: ...

@dataclass(frozen=True)
class EdgeRow:
    source: str
    target: str
    kind: str
    confidence: float
    edge_source: str | None     # "runtime" / "static_literal" / ... / None
    attributes: dict[str, object]

class QueryEngine:
    def __init__(self, graph: GraphView) -> None: ...
    def impact(self, query: ImpactQuery) -> ImpactResult: ...
    def reverse_lookup(self, term: str) -> list[AffectedEntity]: ...  # B8 에서는 스텁
```

### 2.3 In-memory 어댑터

```python
class InMemoryGraphView:
    """ParseResult 리스트로부터 인덱스 구축."""
    def __init__(self, parse_results: list[ParseResult]) -> None: ...
```

Neo4j 어댑터는 B9 또는 별도 서브스텝에서 추가.

---

## 3. BFS 알고리즘

### 3.1 Core 루프 (의사코드)

```
visited: set[str] = {target_fqn}
frontier: list[(fqn, distance, min_conf, sources, path)] = [(target_fqn, 0, 1.0, [], [target_fqn])]
results: list[AffectedEntity] = []

while frontier and current_distance < effective_hops:
    next_frontier = []
    for fqn, d, mc, sources, path in frontier:
        for edge in graph.incoming(fqn):   # 영향 "역방향" — 누가 이 엔티티를 참조하는가
            if not passes_filter(edge, mode):
                continue
            nxt = edge.source
            if nxt in visited:
                continue
            visited.add(nxt)
            new_mc = min(mc, edge.confidence)
            new_sources = sources + [edge.edge_source]
            new_path = path + [nxt]
            results.append(make_affected(nxt, d+1, new_mc, new_sources, new_path, edge))
            next_frontier.append((nxt, d+1, new_mc, new_sources, new_path))
    frontier = next_frontier
    current_distance += 1
    if auto_hops and should_shrink(results):
        break
```

### 3.2 필터 `passes_filter`

```
mode == SAFE:        return edge.confidence >= config.safe_min_confidence
mode == OBSERVED:    return edge.edge_source in config.observed_sources
                     # 기본 {None, "static_literal", "runtime"} (static_unresolved 제외)
mode == POTENTIAL:   return True
```

Q1 결정 반영: `None` 은 JavaParser 가 직접 해소한 엣지 (IMPORTS/EXTENDS/일반 CALLS) → OBSERVED 에 포함.

### 3.3 영향 "방향"

- Impact Analysis 는 **역방향** — "X 를 바꾸면 누가 영향?" → X 를 참조하는 caller 들.
- `graph.incoming(fqn)` 로 역방향 엣지 수집.
- Reverse Lookup 은 정방향 (X 가 닿는 엔티티들) — `graph.outgoing(fqn)`. B8 에서는 스텁만.

### 3.4 경로 다중 발견

같은 엔티티를 2 경로로 도달하면? `visited` 로 한 번만 기록. 최단 경로 우선 (BFS 순서).

### 3.5 Cycle

`visited` 가 사이클 자연 차단.

---

## 4. hops 자율 조정 휴리스틱

### 4.1 조정 신호

| 신호 | 임계치 | 액션 |
|---|---|---|
| 현재까지 결과 수 | `len(results) > 200` | 다음 hop 중단 (`result_too_large`) |
| 누적 BFS 시간 | `elapsed > 2s` | 현재 hop 완료 후 중단 (`timeout`) |
| frontier 크기 | `len(frontier) > 500` | **경고만** — hops 는 max 까지. 사용자가 max_hops 낮추도록 유도 |
| 엣지 평균 confidence 낮음 | `avg(new_edges.conf) < 0.5` | **무시**. potential 모드에서는 정상 |

### 4.2 자동 축소 비활성화

`auto_hops=False` 면 max_hops 까지 완주. 테스트·감사 시나리오용.

### 4.3 결과 리포팅

`hops_used` + `hops_shrunk_reason` 로 투명하게 노출. UI 는 "결과가 너무 많아 자동으로 3 hops 까지만 탐색했습니다. 더 보려면 mode 를 safe 로 좁히거나 max_hops 를 직접 지정하세요." 같은 메시지 생성.

---

## 5. 설계 결정 (사용자 승인 완료 — 2026-04-19)

| # | 결정 | 근거 |
|---|---|---|
| Q1 | **A 채택** — OBSERVED = `source ∈ {None, static_literal, runtime}`. `static_unresolved` 만 제외. | `None` 은 JavaParser 가 한 번에 해소한 정적 엣지 (IMPORTS/EXTENDS/직접 CALLS). 제외하면 OBSERVED 가 리플렉션/DI 샘플만 보여 무용. |
| Q2 | **B 채택** — `direction: "incoming"|"outgoing" = "incoming"` 파라미터. | Impact = incoming (역방향) 기본. Reverse Lookup = outgoing. 같은 엔진으로 둘 다 처리 → C1 Test Gen 재사용 가능. |
| Q3 | **A 채택** — `<reflection-site>` BFS skip + `unresolved_sources` 에 수집. | 가상 노드는 "바꿀 수 있는 대상" 이 아님. 진단 정보로만 노출. |
| Q4 | **B 채택** — 기본 `entity_kinds = {"method", "constructor", "http_endpoint", "event_type", "db_table", "scheduled_task"}`. `class`/`field`/`package` 는 명시 지정 시에만. | 사용자 관심 단위 우선. class 레벨은 noise. |
| Q5 | **설정 외부화** — 임계값은 `ImpactConfig` dataclass 로 분리. SPEC 에는 기본값만 명시. | 슬랩 샘플 측정 후 설정 파일/환경변수로 튜닝 가능하도록. 하드코딩 금지. |
| Q6 | **A 채택** — `InMemoryGraphView` 만 B8 범위. `Neo4jGraphView` 는 B9 이후. | Slab 규모 검증 전 읽기 어댑터 스키마 고정 불필요. |
| Q7 | **A 채택** — 4-way 서브스텝. | B6/B7 패턴 유지, 각 단계 크기 균일. |

### 5.1 `ImpactConfig` 기본값 (Q5 반영)

```python
@dataclass(frozen=True)
class ImpactConfig:
    shrink_result_threshold: int = 200   # len(results) > N → 중단
    timeout_seconds: float = 2.0          # elapsed > N → 중단
    frontier_warn_threshold: int = 500    # len(frontier) > N → 경고만
    observed_sources: frozenset[str | None] = frozenset({None, "static_literal", "runtime"})
    safe_min_confidence: float = 0.9
    default_entity_kinds: frozenset[str] = frozenset({
        "method", "constructor", "http_endpoint", "event_type", "db_table", "scheduled_task"
    })
```

엔진은 `QueryEngine(graph, config=ImpactConfig())` 로 주입. 환경변수/설정파일 오버라이드는 CLI/API 레이어가 담당.

### 5.2 서브스텝 분할 확정

- **B8-0** : DTO (`ImpactQuery`/`ImpactMode`/`AffectedEntity`/`ImpactResult`/`EdgeRow`/`EntityRow`) + `GraphView` Protocol + `InMemoryGraphView` + `ImpactConfig`
- **B8-1** : `QueryEngine.impact` BFS core (incoming 방향) + 3-mode 필터 + 12 테스트 케이스
- **B8-2** : hops 자율 축소 + 타임아웃 + `hops_shrunk_reason` 리포팅
- **B8-3** : Reverse Lookup 스텁 (direction="outgoing") + `<reflection-site>` 진단

각 서브스텝 7-item 완료 후 다음 진행.

---

## 6. 테스트 계획 초안 (B8-1 기준)

1. Impact SAFE — confidence≥0.9 엣지만 통과 (static_unresolved skip)
2. Impact OBSERVED — runtime + static_literal + static_direct (None) 통과
3. Impact POTENTIAL — 모든 엣지 통과 (static_unresolved 포함)
4. max_hops 제한 — 3 hops 깊이에서 멈춤
5. visited cycle — 자기 자신으로 돌아오는 그래프에서 무한 루프 방지
6. 같은 엔티티 2 경로 — 최단 경로만 결과에 포함
7. edge_kinds 필터 — calls 만, publishes/handles 제외
8. entity_kinds 필터 — method 만 리턴, class 노이즈 제거
9. `<reflection-site>` skip + `unresolved_sources` 에 수집
10. unknown target_fqn — `message` 에 "not found", affected=[]
11. path 역추적 — source → hop1 → hop2 순서 올바름
12. confidence_min 계산 — 경로 상 최소값 (병목 엣지) 정확

---

## 7. 인계 포인트

- **B9 Slab E2E** 는 B8 완료 후 실 repo 로 Impact 쿼리 돌려 UX 검증.
- **Round 2 (Phase C)** 에서 domain 매핑이 얹히면 `AffectedEntity` 를 `AffectedProcess` 로 확장 (방향 전환 전 구버전 시맨틱 복원).
- **Reverse Lookup (B8-3)** + **Test Generation (Phase D/E)** 은 본 엔진 재사용.

---

## 8. 승인 요청

위 Q1~Q7 응답 주시면 그 기반으로:
1. `OD-11-B8-decisions.html` 시각화 업데이트
2. B8-0 (DTO + Protocol + InMemoryGraphView) TDD red 착수
3. 이후 B8-1~B8-3 순차 진행
