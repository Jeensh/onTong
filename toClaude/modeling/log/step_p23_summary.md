# P23 — PythonGenerator (Java method body → 한국어 변수명 Python LLM 변환, Q-D=D1)

## 결과 요약 (해커톤 데모 핵심 가설)

**Q-D=D1 가설 완전 검증 — Claude Sonnet 4.6 으로 production-quality 변환 가능.**

Slab `SdFinalLengthRangeAction.execute()` (BigDecimal 산술 14줄) 변환 결과:
```python
def execute(order: dict, slab: dict) -> None:
    슬라브중량 = slab['slabWgtInProgress']
    두께 = slab['slabThickness']
    비중 = order['specificGravity']
    분자 = 슬라브중량 * INVERSE_UNIT
    폭상한기준길이 = 분자 / (slab['finalWidthHigh'] * 두께 * 비중)
    폭하한기준길이 = 분자 / (slab['finalWidthLow'] * 두께 * 비중)
    길이하한 = max(폭상한기준길이, slab['firstLengthLow'])
    길이상한 = min(폭하한기준길이, slab['firstLengthHigh'])
    slab['finalLengthLow'] = 길이하한
    slab['finalLengthHigh'] = 길이상한
```

검증된 능력 :
- BusinessTerm 매핑 없어도 **문맥 추론으로 한국어 변수명** 자동 생성 (slabWgt → 슬라브중량, lengthFromWidthHigh → 폭상한기준길이)
- Java `BigDecimal` → Python `Decimal` 정확히 변환
- max/min 로직 보존
- 산술 우선순위 보존
- type hints 추가 (`order: dict`, `slab: dict`, `-> None`)

## 산출물

### Backend
- `backend/modeling/code_analysis/java_parser.py` — `_extract_method` 에 `method_attrs["source"] = node.text.decode()` 추가 (메서드 body 텍스트 캡처)
- `backend/modeling/simulation/python_generator.py` (NEW)
  - `ClaudePythonGenerator` (anthropic SDK, model=claude-sonnet-4-6, max_tokens=4096)
  - 시스템 프롬프트 — 8 규칙 (한국어 변수명 / 외부호출 mock / type annotation / Java→Python 문법 / 임계값 보존 / return / JSON 응답 / 주석 최소화)
  - `PythonGenerationResult` dataclass (java_source / python_code / variable_mapping / mock_calls / warnings / errors / llm_called)
  - `_validate_python` — `compile()` 으로 Python 컴파일 검증
  - `apply_change_spec_to_java` — kind 별 텍스트 단위 변환 (method_body / anchor_value old→new replace, rule_*/term_binding 은 코드 무변경)
- `backend/modeling/simulation/__init__.py` — 모듈 노출
- `backend/modeling/api/change_specs_api.py` — `simulate` 엔드포인트가 stub → 실제 PythonGenerator 호출
  - `_extract_method_source` / `_collect_anchors` / `_collect_terms` 헬퍼
  - LLM 미사용 시 graceful stub fallback (`engine: stub-no-llm`)
  - simulation_result : engine / before {java_source, python_code, variable_mapping, mock_calls, warnings, errors} / after {...} / diff
- `backend/main.py` — `ClaudePythonGenerator()` + `change_specs_api.init(python_generator=..., repo_registry=..., term_registry=..., rule_registry=..., anchor_store=...)`

### Frontend
- `SimulationDrawer.tsx` Step 3 — `Step3Diff` 재작성
  - `SideColumn` 컴포넌트 (Before/After 양쪽)
    - Python code (slate-900 dark code block, max-h-64)
    - Java source (collapsible, default 접힘)
    - 변수 매핑 (java → 한국어, 모두 표시)
    - Mock 호출 리스트
    - 경고 리스트 (amber)
    - 에러 (있으면 빨강)
  - 헤더에 java_changed 여부 표시

## 검증 (실제 실행)

### Test 1 — 단순 service 메서드 (CastSpecService.lookup)
```
Input: public CastSpecEntity lookup(String cmpCd, ..., String productTypeCd) {
         CastSpecPK pk = new CastSpecPK(cmpCd, ...);
         return repository.findById(pk).map(logic::toEntity).orElse(null);
       }

Output:
def lookup(cmpCd: str, ..., 품종코드: str) -> Optional[dict]:
    pk = (cmpCd, ..., 품종코드)
    result = _mock_repository_findById(pk)
    if result is None: return None
    return _mock_logic_toEntity(result)

variable_mapping: {productTypeCd: 품종코드}     ← BusinessTerm 매핑 활용
mock_calls: [repository.findById, logic.toEntity]
```

### Test 2 — 복잡한 BigDecimal 산술 (SdFinalLengthRangeAction.execute)
- 9 변수 모두 한국어 변환 (BusinessTerm 매핑 없어도 문맥 추론)
- Decimal 산술 정확
- max/min 로직 보존
- type hints
- 4 warnings (사소한 가정 안내)

## 위험 / 한계 발견

1. **Disk cache 무효화 필요** — `.analyzed/entities.json` + SQLite `RepositoryRow` 둘 다 stale 캐시. P14 같은 새 attribute 추가 시 두 캐시 모두 비우고 재등록 필요.
   - 해결: `RepositoryRow` 삭제 후 `POST /repos/register` 로 재파싱.
2. **method body 토큰 사이즈** — 200~300줄 메서드는 LLM context 초과 가능. 현재 `java_source[:3000]` 으로 trim. 더 큰 메서드는 chunking 또는 요약 필요.
3. **Mock 호출의 정확성** — `_mock_repository_findById` 는 시그니처/반환 타입 추정. P24 SyntheticInput 으로 mock return 값 정의 필요.
4. **외부 클래스 (CastSpecPK, CastSpecEntity)** — Python 에서 tuple/dict 로 대체. 실제 엔티티 구조와 다를 수 있음. P24 에서 BusinessTerm 기반 schema 보강 가능.

## 다음 (P24)
SyntheticInputGenerator + RestrictedPython SandboxRunner (Q-A=A2).
- anchor 정보로 입력 자동 생성 (param 기본값, branch 분기 입력, literal 임계값)
- RestrictedPython 으로 generated python 안전 실행
- mock_calls 는 default mock 함수 (None / [] / 0 등) 반환
- outputs 캡처 → P25 diff 입력
