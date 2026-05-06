# Step P3-2 Summary — Repo Import Pipeline 백엔드

**완료**: 2026-05-01
**범위**: Java repo path → CodeType/CodeMethod/CallSite 적재까지의 백엔드 파이프라인 + REST API.

## 결과

slab-design-real (122 Java 파일) 을 REST 한 번 호출로 import:
- 123 CodeType (framework 6 / domain 76 / infra 41)
- 956 CodeMethod (business 42 / helper 10 / adapter 890 / unknown 14)
- 1018 CallSite
- errors=0, duration ~150ms (parsing 비중 ~80%)
- **idempotent**: 같은 repo_id 재실행 시 깨끗하게 교체

## 신규/수정

| 파일 | 종류 | 핵심 |
|---|---|---|
| `backend/modeling/api/repo_import.py` | 신규 | `POST /import` job 시작, `GET /{job_id}` 상태, `GET /{job_id}/stream` SSE, `GET /import` list. background thread + in-memory job registry. |
| `backend/main.py` | 수정 | `repo_import_api` import + router 등록 |
| `backend/modeling/persistence/database.py` | 수정 | SQLite `PRAGMA foreign_keys = ON` connect 이벤트로 enforce. `delete_repo` 의 ON DELETE CASCADE 가 실제 동작하도록. |
| `backend/modeling/code_layer/role_classifier.py` | 수정 | INFRA 이름 패턴 (`*Jpo`, `*PK`, `*Repository` 등) 이 `@Entity` annotation 보다 우선. |
| `backend/modeling/code_layer/importer.py` | 수정 | `_normalize_caller_fqns` — parser 의 raw caller fqn 을 저장된 signature-suffixed fqn 으로 line 매칭. CallSite FK 정합. |

## 발견 + 처리한 이슈 3종

1. **첫 import 는 통과, 두 번째부터 PK 충돌**
   - 원인: SQLite 가 기본적으로 FK 미enforce. `delete(CodeTypeRow).where(repo_id==...)` 가 cascade 발동 못 시켜서 orphan `code_methods` 잔류 → 다음 insert 가 UNIQUE constraint 충돌.
   - 처리: connect 이벤트에서 `PRAGMA foreign_keys=ON`.

2. **Jpo 클래스가 DOMAIN 으로 분류**
   - 원인: `@Entity` annotation 매핑이 이름 패턴보다 먼저 발화.
   - 처리: INFRA 이름 패턴을 annotation 매핑 앞으로 이동. slab-design 컨벤션 (Jpo=raw row, *Entity=rich domain) 정합.

3. **CallSite insert 시 FOREIGN KEY 위반**
   - 원인: parser 가 emit 하는 `r.source` 는 signature 없음 (`Pkg.Class.method`), 우리 schema 는 오버로드 구분 위해 signature-suffixed (`Pkg.Class.method(int,String)`).
   - 처리: importer 단계에서 `_normalize_caller_fqns` — base fqn 일치 + line 포함 매칭. 매칭 실패 시 seed drop.

## 검증 방법 (재현)

```bash
uvicorn backend.main:app --port 8765 --log-level warning &
JOB=$(curl -s -X POST http://127.0.0.1:8765/api/ontology/repos/import \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"slab-design-real","repo_path":"sample-repos/slab-design-real"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
curl -N http://127.0.0.1:8765/api/ontology/repos/import/$JOB/stream
curl http://127.0.0.1:8765/api/ontology/code-types?repo_id=slab-design-real | jq 'length'
# → 123
```

## 다음 (P3-3)

자동 매핑 추천:
- `Method.role=business` → Action 후보 (kind 추정: void+sink → effectful, return + 무mutation → pure_function, 호출 chain orchestrator → workflow)
- `CodeType.role=domain` + name 정규화 (camel/snake/Korean glossary alias) → BusinessTerm 후보
- `TypeRealization` 자동 제시 — Entity 가 N 개 Jpo 를 평탄화 흡수하면 PRIMARY 1 + PARTIAL N
