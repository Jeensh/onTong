# 섹션 3 (Simulation) — 재구축 명세서

> **대상**: Claude Code
> **목적**: 기존 Section 3를 **고정 Agent 3종 + 표준화된 시뮬레이션** 구조로 재구축한다.
> **현재 상태**: 시나리오 A/B/C 에이전트 + Custom Agent Hub + Slab 3D 시뮬레이터 (모두 갈아엎을 예정)
> **선결 조건**: `ontology-modeling-spec.md` 진행 중 (병렬 진행 가능)
> **버전**: v2.0 (재구축)

---

## 0. 배경

### 0-1. 왜 갈아엎는가

지난 회의에서 **Section 3의 정체성이 재정의**되었다.

| 기존 (v1) | 신규 (v2) |
|---------|---------|
| 자유 대화형 Agent (사용자가 무엇이든 질문) | **고정 Agent 3종** (틀이 정해진 작업) |
| 시나리오 A/B/C 분리 | 단일 진입점 + 3개 메뉴 |
| 도메인 지식이 Agent에 분산 | 모든 도메인 지식은 **온톨로지에서** 가져옴 |
| Mock 데이터 기반 | **Section 2 (Modeling) 온톨로지 호출** |
| Custom Agent Hub로 사용자가 직접 빌더 | **표준화된 시뮬레이션 메뉴** |

### 0-2. 새 정체성

> **Section 3 = "기능 표준화 Agent 허브"**
> 사용자가 큰 메뉴(3개)에서 시작 → 틀이 정해진 폼으로 입력 → Section 2의 온톨로지 호출 → 결과 시각화

---

## 1. Agent 3종 정의 (회의 결과 반영)

### Agent 1 — 프로그램 영향도 파악
> "특정 값 및 소스가 바뀌었을 때 어떤 기능들이 연관되어 있는지 추출 및 기능이 어떻게 바뀌는지"

**시뮬레이션 2가지 버전:**
- **Version A**: **프로그램(소스)을 바꾸는** 시뮬레이션 — 메서드/클래스/시그니처 변경 시
- **Version B**: **데이터(기준값)를 바꾸는** 시뮬레이션 — SC기준 값, 테이블 컬럼 변경 시

### Agent 2 — 기능 테스트
> "특정 기능을 테스트하기 위한 데이터 생성 및 테스트"

테스트 데이터 자동 생성 + 테스트 케이스 스켈레톤 출력.

### Agent 3 — 비즈니스 용어 위치 파악
> "비즈니스 용어로된 요청사항에 대한 소스 위치 및 대상 파악"

자연어로 받은 업무 요청을 소스/테이블/Step 위치로 매핑.

---

## 2. UI 구조 (재설계)

### 2-1. 전체 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│ onTong  [Wiki] [Modeling] [Simulation]                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   📋 기능 표준화 Agent 허브                                  │
│                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│   │  📊 Agent 1   │  │  🧪 Agent 2  │  │  🗺 Agent 3   │    │
│   │  영향도 파악   │  │  테스트 생성  │  │  위치 파악    │    │
│   │              │  │              │  │              │    │
│   │  [시작하기]   │  │  [시작하기]   │  │  [시작하기]   │    │
│   └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2-2. Agent 1 클릭 시 화면

**자유 대화창이 아니라 폼 기반**으로 전환:

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Agent 1 — 프로그램 영향도 파악                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  변경 유형 선택:                                              │
│  ◉ 프로그램(소스) 변경 시뮬레이션                             │
│  ○ 데이터(기준값) 변경 시뮬레이션                             │
│                                                              │
│  변경 대상:                                                   │
│  ┌─────────────────────────────────────────────┐            │
│  │ 🔍 메서드/클래스/테이블 검색...                │ ← 자동완성  │
│  └─────────────────────────────────────────────┘            │
│                                                              │
│  변경 종류:                                                   │
│  ◉ 로직 변경  ○ 시그니처 변경  ○ 삭제                       │
│                                                              │
│  [영향도 분석 실행]                                           │
│                                                              │
│  ─────────────────────────────────────────────              │
│                                                              │
│  📊 분석 결과                                                 │
│  • 직접 영향: ...                                            │
│  • 간접 영향: ...                                            │
│  • 위험도: HIGH                                              │
│  • 영향받는 Step: ...                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2-3. Agent 2 클릭 시 화면

```
┌─────────────────────────────────────────────────────────────┐
│ 🧪 Agent 2 — 기능 테스트 데이터 생성                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  테스트 대상:                                                 │
│  ◉ Step 단위  ○ 메서드 단위  ○ SC기준 단위                  │
│                                                              │
│  대상 선택:                                                   │
│  ┌─────────────────────────────────────────────┐            │
│  │ Step 2 - 1차 폭범위 계산              ▼     │            │
│  └─────────────────────────────────────────────┘            │
│                                                              │
│  테스트 케이스 유형: ☑ 정상 ☑ 경계값 ☑ 에러 ☐ 성능        │
│                                                              │
│  생성 개수: [5]건                                             │
│                                                              │
│  [테스트 데이터 생성]                                         │
│                                                              │
│  ─────────────────────────────────────────────              │
│                                                              │
│  📋 생성된 테스트 케이스                                      │
│  • TC001: 정상 케이스 (입력 폭 1040, 두께 250...)           │
│  • TC002: 경계 케이스 (입력 폭 900...)                      │
│  • TC003: 에러 케이스 (DG320 발생)                          │
│                                                              │
│  [JUnit 코드 다운로드]  [JSON 다운로드]                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2-4. Agent 3 클릭 시 화면

자연어 입력은 허용하되 **결과는 구조화된 테이블**로:

```
┌─────────────────────────────────────────────────────────────┐
│ 🗺 Agent 3 — 비즈니스 용어 위치 파악                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  찾고 싶은 업무 용어/개념:                                    │
│  ┌─────────────────────────────────────────────┐            │
│  │ Edging 기준 어디서 체크해?                    │            │
│  └─────────────────────────────────────────────┘            │
│  검색 범위: ☑ 소스 ☑ 테이블 ☑ 프로세스                    │
│                                                              │
│  [위치 파악 실행]                                             │
│                                                              │
│  ─────────────────────────────────────────────              │
│                                                              │
│  🟢 관련 프로세스:                                            │
│    ┌────┬─────────────────┬────────────────────┐            │
│    │ #  │ Step           │ 역할                │            │
│    ├────┼─────────────────┼────────────────────┤            │
│    │ 2  │ 1차 폭범위 계산  │ Edging능력 매칭     │            │
│    │ 13 │ Target폭 재계산 │ 3pass Edging 적용   │            │
│    └────┴─────────────────┴────────────────────┘            │
│                                                              │
│  🟠 관련 소스: SlabDesignService.calculatePrimaryWidthRange()│
│  💾 관련 테이블: TB_C40_050SC070                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2-5. 핵심 원칙

> **"틀이 정해진 폼 기반. 자유 채팅 없음."**
> Agent별 입력 필드가 명확히 정해져 있어, LLM이 추측하지 않아도 됨.

---

## 3. 기존 코드 처리 방침

### 3-1. 삭제 대상 (갈아엎음)

```
backend/simulation/
├── agent/
│   ├── scenario_a_agent.py           ← 삭제
│   ├── scenario_b_agent.py           ← 삭제
│   ├── scenario_c_agent.py           ← 삭제
│   └── custom_agent.py               ← 삭제
└── mock/                              ← 삭제 (Section 2 온톨로지 사용)

frontend/src/components/simulation/
├── ScenarioSelector.tsx              ← 삭제
├── SimCopilot.tsx                     ← 삭제
├── CustomAgentHub.tsx                ← 삭제
└── (Slab 3D 뷰어 관련은 유지)
```

### 3-2. 보존 대상

```
backend/simulation/
├── api/simulation.py                  ← 일부 보존 (3D 뷰어 API)
└── visualization/                     ← 보존 (시각화 유틸)

frontend/src/components/simulation/
├── SlabViewer3D.tsx                   ← 보존
├── SlabParamController.tsx            ← 보존
└── SlabImpactPanel.tsx                ← 보존 (Agent 1과 통합)
```

### 3-3. 신규 추가

```
backend/simulation/
├── agents/                             ← 신규 (3개 고정 Agent)
│   ├── __init__.py
│   ├── agent1_impact.py
│   ├── agent2_test_data.py
│   └── agent3_locator.py
├── client/
│   └── ontology_client.py              ← 신규 (Section 2 호출)
└── api/
    └── agents_router.py                ← 신규 (Agent별 엔드포인트)

frontend/src/
├── components/simulation/
│   ├── AgentHub.tsx                    ← 신규 (메인 허브)
│   ├── Agent1ImpactForm.tsx            ← 신규
│   ├── Agent2TestDataForm.tsx          ← 신규
│   ├── Agent3LocatorForm.tsx           ← 신규
│   └── shared/
│       ├── EntitySearchBox.tsx         ← 자동완성 검색
│       └── ResultTable.tsx              ← 공통 결과 테이블
└── lib/simulation/
    ├── agentApi.ts                     ← Agent API 호출
    └── types.ts                         ← 타입 정의
```

---

## 4. 백엔드 구현

### 4-1. Section 2 호출 클라이언트

`backend/simulation/client/ontology_client.py`:

```python
import httpx
import os
from typing import Optional
from backend.shared.contracts.ontology import OntologyRequest, OntologyResponse

class OntologyClient:
    """Section 3 → Section 2 호출 전담"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv(
            "MODELING_API_URL", "http://localhost:8001"
        )
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def query(self, req: OntologyRequest) -> OntologyResponse:
        response = await self.client.post(
            f"{self.base_url}/api/modeling/ontology/query",
            json=req.model_dump(mode="json")
        )
        response.raise_for_status()
        return OntologyResponse(**response.json())
    
    async def search_terms(self, q: str, limit: int = 10):
        response = await self.client.get(
            f"{self.base_url}/api/modeling/ontology/term/search",
            params={"q": q, "limit": limit}
        )
        return response.json()
    
    async def close(self):
        await self.client.aclose()


_client: Optional[OntologyClient] = None

def get_ontology_client() -> OntologyClient:
    global _client
    if _client is None:
        _client = OntologyClient()
    return _client
```

### 4-2. Agent 1 — 영향도 파악

`backend/simulation/agents/agent1_impact.py`:

```python
from pydantic import BaseModel
from typing import Literal, Optional
from ..client.ontology_client import get_ontology_client
from backend.shared.contracts.ontology import OntologyRequest, Intent
import uuid

# ─── 입력 모델 ───────────────────────────────────────────────
class Agent1Request(BaseModel):
    change_kind: Literal["program", "data"]      # 프로그램 변경 vs 데이터 변경
    target_type: Literal["method", "class", "table", "column", "standard_value"]
    target_id: str                                 # 대상 ID
    modification_type: Literal["logic", "signature", "deletion", "value_change"]
    new_value: Optional[str] = None                # 데이터 변경 시 새 값

# ─── 출력 모델 ───────────────────────────────────────────────
class Agent1Result(BaseModel):
    summary: str
    direct_impact: dict
    indirect_impact: dict
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    recommended_test_scope: list[str]

# ─── 핵심 로직 ───────────────────────────────────────────────
async def execute_agent1(req: Agent1Request) -> Agent1Result:
    """Agent 1은 자체 로직 없음. Section 2 호출만."""
    client = get_ontology_client()
    
    ontology_req = OntologyRequest(
        request_id=str(uuid.uuid4()),
        intent=Intent.IMPACT_ANALYSIS,
        parameters={
            "target": {
                "kind": req.target_type,
                "id": req.target_id
            },
            "modification": req.modification_type,
            "change_kind": req.change_kind,
            "new_value": req.new_value
        }
    )
    
    response = await client.query(ontology_req)
    
    if response.status != "success":
        raise Exception(f"Ontology query failed: {response.status}")
    
    data = response.result
    return Agent1Result(
        summary=data["summary"],
        direct_impact=data["data"]["direct_impact"],
        indirect_impact=data["data"]["indirect_impact"],
        risk_level=data["risk_level"],
        recommended_test_scope=data.get("recommended_test_scope", [])
    )
```

### 4-3. Agent 2 — 테스트 데이터 생성

`backend/simulation/agents/agent2_test_data.py`:

```python
from pydantic import BaseModel
from typing import Literal, Optional, List, Dict, Any
from ..client.ontology_client import get_ontology_client
from backend.shared.contracts.ontology import OntologyRequest, Intent
import uuid

class Agent2Request(BaseModel):
    target_type: Literal["step", "method", "standard"]
    target_id: str  # 'step_2', 'method_calc_primary_width', 'std_sc070'
    case_types: List[Literal["normal", "boundary", "error", "performance"]]
    test_count: int = 5

class TestCase(BaseModel):
    case_id: str
    case_type: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]

class Agent2Result(BaseModel):
    target_summary: str
    test_cases: List[TestCase]
    code_skeleton: str  # JUnit 코드
    data_dependencies: List[str]

async def execute_agent2(req: Agent2Request) -> Agent2Result:
    client = get_ontology_client()
    
    # Section 2에서 Step의 입출력 변수, 기준, 에러 정보 가져오기
    ontology_req = OntologyRequest(
        request_id=str(uuid.uuid4()),
        intent=Intent.SIMULATE,
        parameters={
            "target": {"kind": req.target_type, "id": req.target_id},
            "test_data_request": {
                "case_types": req.case_types,
                "count": req.test_count
            }
        }
    )
    
    response = await client.query(ontology_req)
    # ... 응답 가공 후 TestCase 생성
    # 실제 값 생성은 입력 변수의 valid_range를 기반으로
```

### 4-4. Agent 3 — 위치 파악

`backend/simulation/agents/agent3_locator.py`:

```python
from pydantic import BaseModel
from typing import List, Dict
from ..client.ontology_client import get_ontology_client
from backend.shared.contracts.ontology import OntologyRequest, Intent
import uuid

class Agent3Request(BaseModel):
    natural_language_query: str
    search_scope: List[str]  # ['source', 'table', 'process']

class Agent3Result(BaseModel):
    matched_terms: List[Dict]
    process_locations: List[Dict]
    source_locations: List[Dict]
    data_locations: List[Dict]
    related_terms: List[Dict]

async def execute_agent3(req: Agent3Request) -> Agent3Result:
    client = get_ontology_client()
    
    # Section 2의 explain intent 호출
    ontology_req = OntologyRequest(
        request_id=str(uuid.uuid4()),
        intent=Intent.EXPLAIN,
        natural_language=req.natural_language_query,
        parameters={"scope": req.search_scope}
    )
    
    response = await client.query(ontology_req)
    return Agent3Result(**response.result)
```

### 4-5. API 라우터

`backend/simulation/api/agents_router.py`:

```python
from fastapi import APIRouter, HTTPException
from ..agents.agent1_impact import Agent1Request, Agent1Result, execute_agent1
from ..agents.agent2_test_data import Agent2Request, Agent2Result, execute_agent2
from ..agents.agent3_locator import Agent3Request, Agent3Result, execute_agent3

router = APIRouter(prefix="/api/simulation/agents", tags=["simulation-agents"])

@router.post("/impact", response_model=Agent1Result)
async def run_agent1(req: Agent1Request):
    try:
        return await execute_agent1(req)
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/test-data", response_model=Agent2Result)
async def run_agent2(req: Agent2Request):
    try:
        return await execute_agent2(req)
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/locator", response_model=Agent3Result)
async def run_agent3(req: Agent3Request):
    try:
        return await execute_agent3(req)
    except Exception as e:
        raise HTTPException(500, str(e))
```

---

## 5. 프론트엔드 구현

### 5-1. AgentHub (메인 허브)

`frontend/src/components/simulation/AgentHub.tsx`:

```tsx
import { useState } from 'react';
import { Agent1ImpactForm } from './Agent1ImpactForm';
import { Agent2TestDataForm } from './Agent2TestDataForm';
import { Agent3LocatorForm } from './Agent3LocatorForm';

type AgentType = null | 'impact' | 'test-data' | 'locator';

export function AgentHub() {
  const [selected, setSelected] = useState<AgentType>(null);
  
  if (selected === null) {
    return (
      <div className="agent-hub">
        <h1>📋 기능 표준화 Agent 허브</h1>
        <div className="agent-cards">
          <AgentCard
            icon="📊"
            title="Agent 1 — 영향도 파악"
            description="특정 값/소스가 바뀌었을 때 어떤 기능들이 연관되어 있는지"
            onClick={() => setSelected('impact')}
          />
          <AgentCard
            icon="🧪"
            title="Agent 2 — 테스트 데이터 생성"
            description="특정 기능을 테스트하기 위한 데이터 생성 및 테스트"
            onClick={() => setSelected('test-data')}
          />
          <AgentCard
            icon="🗺"
            title="Agent 3 — 위치 파악"
            description="비즈니스 용어로된 요청사항에 대한 소스 위치 및 대상 파악"
            onClick={() => setSelected('locator')}
          />
        </div>
      </div>
    );
  }
  
  // 각 Agent 폼 렌더링
  return (
    <div>
      <button onClick={() => setSelected(null)}>← 허브로 돌아가기</button>
      {selected === 'impact' && <Agent1ImpactForm />}
      {selected === 'test-data' && <Agent2TestDataForm />}
      {selected === 'locator' && <Agent3LocatorForm />}
    </div>
  );
}
```

### 5-2. Agent 1 폼

`Agent1ImpactForm.tsx`:

```tsx
import { useState } from 'react';
import { EntitySearchBox } from './shared/EntitySearchBox';
import { ResultTable } from './shared/ResultTable';

export function Agent1ImpactForm() {
  const [changeKind, setChangeKind] = useState<'program' | 'data'>('program');
  const [target, setTarget] = useState<{type: string, id: string} | null>(null);
  const [modificationType, setModificationType] = useState('logic');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  
  async function handleSubmit() {
    if (!target) return;
    setLoading(true);
    
    const response = await fetch('/api/simulation/agents/impact', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        change_kind: changeKind,
        target_type: target.type,
        target_id: target.id,
        modification_type: modificationType
      })
    });
    
    setResult(await response.json());
    setLoading(false);
  }
  
  return (
    <div className="agent-form">
      <h2>📊 Agent 1 — 프로그램 영향도 파악</h2>
      
      <fieldset>
        <legend>변경 유형</legend>
        <label>
          <input type="radio" checked={changeKind === 'program'}
                 onChange={() => setChangeKind('program')} />
          프로그램(소스) 변경
        </label>
        <label>
          <input type="radio" checked={changeKind === 'data'}
                 onChange={() => setChangeKind('data')} />
          데이터(기준값) 변경
        </label>
      </fieldset>
      
      <fieldset>
        <legend>변경 대상</legend>
        <EntitySearchBox 
          allowedTypes={changeKind === 'program' 
            ? ['method', 'class'] 
            : ['table', 'column', 'standard_value']}
          onSelect={setTarget}
        />
      </fieldset>
      
      <fieldset>
        <legend>변경 종류</legend>
        <select value={modificationType} onChange={e => setModificationType(e.target.value)}>
          <option value="logic">로직 변경</option>
          <option value="signature">시그니처 변경</option>
          <option value="deletion">삭제</option>
        </select>
      </fieldset>
      
      <button onClick={handleSubmit} disabled={!target || loading}>
        {loading ? '분석 중...' : '영향도 분석 실행'}
      </button>
      
      {result && (
        <div className="result-panel">
          <h3>📊 분석 결과 (위험도: {result.risk_level})</h3>
          <p>{result.summary}</p>
          
          <ResultTable
            title="직접 영향 메서드"
            columns={['클래스', '메서드', '파일']}
            rows={result.direct_impact.methods}
          />
          
          <ResultTable
            title="영향받는 Step"
            columns={['Step #', 'Step 이름', '경유 기준']}
            rows={result.direct_impact.affected_steps}
          />
          
          <ResultTable
            title="간접 영향 (호출 체인)"
            columns={['메서드']}
            rows={result.indirect_impact.downstream_methods}
          />
        </div>
      )}
    </div>
  );
}
```

### 5-3. EntitySearchBox (자동완성)

`shared/EntitySearchBox.tsx`:

```tsx
import { useState, useEffect } from 'react';

export function EntitySearchBox({ 
  allowedTypes, 
  onSelect 
}: { 
  allowedTypes: string[];
  onSelect: (entity: {type: string, id: string}) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  
  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    
    const debounce = setTimeout(() => {
      fetch(`/api/modeling/ontology/term/search?q=${encodeURIComponent(query)}&limit=10`)
        .then(r => r.json())
        .then(data => {
          // allowedTypes에 따라 필터
          setResults(data.filter(r => allowedTypes.includes(r.type)));
        });
    }, 300);
    
    return () => clearTimeout(debounce);
  }, [query, allowedTypes]);
  
  return (
    <div className="entity-search">
      <input 
        type="text" 
        placeholder="🔍 메서드/클래스/테이블 검색..."
        value={query}
        onChange={e => setQuery(e.target.value)}
      />
      {results.length > 0 && (
        <ul className="suggestions">
          {results.map(r => (
            <li key={r.id} onClick={() => { onSelect(r); setQuery(r.name); setResults([]); }}>
              <span className="badge">{r.type}</span>
              <span>{r.name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

---

## 6. main.py 라우터 등록

```python
# backend/main.py
# 기존 simulation 라우터 제거 또는 유지
# from backend.simulation.api.simulation import router as simulation_router  # 기존
from backend.simulation.api.agents_router import router as agents_router  # 신규
app.include_router(agents_router)
```

---

## 7. 테스트 시나리오 (필수 통과)

### 7-1. Agent 1 시나리오

**Test 1**: TB_C40_050SC070 컬럼 추가
```bash
curl -X POST http://localhost:8001/api/simulation/agents/impact \
  -H "Content-Type: application/json" \
  -d '{
    "change_kind": "data",
    "target_type": "table",
    "target_id": "TB_C40_050SC070",
    "modification_type": "logic"
  }'
# 기대: 직접 영향 메서드 1개 이상, 영향 Step에 Step 2 포함, risk_level = HIGH
```

### 7-2. Agent 2 시나리오

**Test 2**: Step 2 테스트 데이터 5건
```bash
curl -X POST http://localhost:8001/api/simulation/agents/test-data \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "step",
    "target_id": "step_2",
    "case_types": ["normal", "boundary", "error"],
    "test_count": 5
  }'
# 기대: 5개 테스트 케이스, JUnit 스켈레톤 포함, DG320 에러 케이스 1개 이상
```

### 7-3. Agent 3 시나리오

**Test 3**: "Edging 로직 어디 있어?"
```bash
curl -X POST http://localhost:8001/api/simulation/agents/locator \
  -H "Content-Type: application/json" \
  -d '{
    "natural_language_query": "Edging 로직 어디 있어?",
    "search_scope": ["source", "table", "process"]
  }'
# 기대: matched_terms에 Edging 포함, process_locations에 Step 2/13 포함
```

### 7-4. Frontend E2E

1. Section 3 탭 클릭 → AgentHub 표시
2. "Agent 1 시작하기" 클릭 → 폼 표시
3. EntitySearchBox에 'sc070' 입력 → 자동완성 결과 1개 이상
4. 선택 → "영향도 분석 실행" → 결과 테이블 표시
5. ← 버튼 → 허브로 복귀

---

## 8. 작업 진행 순서

### Day 1-2: 기존 코드 제거 + 신규 폴더 구조
1. 기존 `agent/`, `mock/`, Custom Agent Hub 삭제
2. 신규 `agents/`, `client/` 폴더 생성
3. 기존 보존 컴포넌트 정리

### Day 3: Section 2 클라이언트
1. `client/ontology_client.py` 작성
2. Section 2가 동작하는지 통합 테스트

### Day 4-5: 3개 Agent 백엔드
1. `agent1_impact.py` 구현 + 테스트
2. `agent2_test_data.py` 구현 + 테스트
3. `agent3_locator.py` 구현 + 테스트
4. `agents_router.py` 작성

### Day 6: 프론트엔드 (1)
1. `AgentHub.tsx` 메인 허브
2. `EntitySearchBox.tsx` 공통 컴포넌트
3. `ResultTable.tsx` 공통 컴포넌트

### Day 7: 프론트엔드 (2)
1. `Agent1ImpactForm.tsx`
2. `Agent2TestDataForm.tsx`
3. `Agent3LocatorForm.tsx`
4. E2E 테스트

---

## 9. 산출물 체크리스트

- [ ] 기존 시나리오 A/B/C, Custom Agent Hub 제거
- [ ] `backend/simulation/client/ontology_client.py`
- [ ] `backend/simulation/agents/` 3개 Agent
- [ ] `backend/simulation/api/agents_router.py`
- [ ] `frontend/src/components/simulation/AgentHub.tsx`
- [ ] `frontend/src/components/simulation/Agent1ImpactForm.tsx`
- [ ] `frontend/src/components/simulation/Agent2TestDataForm.tsx`
- [ ] `frontend/src/components/simulation/Agent3LocatorForm.tsx`
- [ ] 공통 컴포넌트 (`EntitySearchBox`, `ResultTable`)
- [ ] 검증 시나리오 4개 모두 통과
- [ ] 기존 SlabViewer3D는 보존되었는가

---

## 10. 주의사항

- **자유 채팅 UI 만들지 말 것**. 회의에서 명확히 "틀이 정해진 것"으로 결정됨.
- **Agent 자체에 도메인 로직 박지 말 것**. 모든 도메인 지식은 온톨로지에서 옴.
- **Section 2가 미준비 상태에서도 개발 가능하도록**, OntologyClient에 Mock 모드 옵션 제공:
  ```python
  USE_MOCK_ONTOLOGY=true  # Section 2 미완성 시
  ```
- **기존 SlabViewer3D는 보존**. Agent 1의 결과를 시각화할 수 있게 통합 가능.
- **Custom Agent Hub는 완전히 제거**. 사용자가 직접 Agent를 만드는 기능은 v2에서 빠짐.
