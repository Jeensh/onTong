# Step P3-3 Summary — 자동 매핑 추천

**완료**: 2026-05-01
**범위**: P3-2 import 결과를 받아 BusinessTerm / Action / TypeRealization 후보 자동 생성. read-only 미리보기 + 옵션 영속 (`confirmed=False`).

## 결과 (slab-design-real)

| 항목 | 개수 | 비고 |
|---|---|---|
| BusinessTerm 후보 | 29 | confidence=1.0 12건 (글로서리 정확 매칭), 0.7 7건, 0.5 10건 |
| Action 후보 | 36 | 1 workflow (SdDesigner.design) + 24 effectful (대부분 *Action.execute) + 11 pure_function (validate/classify/fail/pass) |
| TypeRealization 후보 | 34 | 29 PRIMARY + 5 PARTIAL |

**핵심 자동 검출**: SDOrderEntity ⊃ {SDOrderOsJpo, SDOrderOmJpo, SDOrderChemicalJpo, SDOrderQdJpo} 4 PARTIAL + SDSlabEntity ⊃ SlabResultJpo 1 PARTIAL. p3_order_mapping.md 가 예측한 "Entity 가 다수 Jpo 평탄화 흡수" 드라마 DNA 그대로 자동 발견.

**declared_on_term 자동 추정**: 36 Action 중 29건이 `term.scm.order` (주문) 등 BusinessTerm 으로 자동 매핑. 휴리스틱 = 메서드 첫 param 의 simple type → BusinessTerm 후보 lookup.

## 신규 파일

| 파일 | 핵심 |
|---|---|
| `backend/modeling/code_layer/recommender.py` | `build_recommendations()` orchestrator + `_SLAB_GLOSSARY` 30+ 매핑 + `_action_kind_for()` 휴리스틱 + `_GENERIC_HELPER_NAMES` 필터 + Entity⊃Jpo PARTIAL 자동 검출 |
| `backend/modeling/api/recommend_api.py` | `POST /api/ontology/repos/{repo_id}/recommend?persist=&min_confidence=` — read-only 미리보기 또는 영속. 결과는 confidence DESC 정렬 |

## 수정

- `backend/main.py` — `recommend_api` router 등록.

## 검증 (curl)

```bash
# 미리보기 (≥0.7)
curl -X POST 'http://127.0.0.1:8765/api/ontology/repos/slab-design-real/recommend?min_confidence=0.7' | jq '.summary'
# → {"terms":19,"actions":22,"type_realizations":24}

# 영속
curl -X POST 'http://127.0.0.1:8765/api/ontology/repos/slab-design-real/recommend?persist=true' | jq '.persisted_counts'
# → {"terms":29,"actions":36,"type_realizations":34}

# 기존 query API 로 결과 확인
curl 'http://127.0.0.1:8765/api/ontology/terms?repo_id=slab-design-real' | jq 'length'  # 29
```

## 다음 (P3-4)

Frontend Repo Import UI:
- 사이드바 또는 modal: repo path 입력
- `POST /repos/import` → job_id 받고 SSE `/{job_id}/stream` 으로 progress bar
- import 완료 시 자동으로 `POST /repos/{id}/recommend?persist=true` 호출
- 결과 요약 카드 (Term/Action/Realization 카운트 + confirmed=False 강조 → "큐에 N건 대기")
