# P21 — Ontology Editor 카드 인라인 + 외부 매뉴얼 LLM 자동 link

## 목적
P17~P20 까지는 *조회/검토* 위주. P21 은 사용자가 매핑/term/매뉴얼 link 를
*Workbench 안에서 직접 수정* 가능하도록 만든다. 매핑 기능 80% → 100% (기능적).

3 sub-task :
- **P21a** Anchor 카드 인라인 「확정」 버튼 (auto-suggest 결과 → 즉시 confirmed binding)
- **P21b** BusinessTerm 인라인 편집 (Ontology 패널 상단 collapsible)
- **P21c** Rule ↔ Manual fragment LLM auto-link 결과 노출 (R 「📚 참고」 활성화)

## 산출물

### Backend
- `backend/modeling/api/rules_api.py` — `GET /rules/{rule_fqn:path}/manual-fragments` 추가
  - `gaps_api._auto_described_in` (startup auto-linker 결과) 에서 source_fqn=rule_fqn 매칭 fragment 반환
  - `manual_registry.get_fragment` 으로 본문 텍스트 + doc_fqn 채움
  - response : `LinkedFragmentDto` (rule_fqn / fragment_fqn / fragment_text[:300] / fragment_doc / confidence / source ∈ manual / name_match / embedding / llm / manual_directive)

### Frontend
- `frontend/src/lib/api/modeling.ts`
  - `LinkedFragmentDto` 타입 + `getLinkedFragments(ruleFqn)` 함수
- `frontend/src/components/sections/modeling/MethodWorkbench.tsx`
  - **AnchorCard** 확장 (P21a)
    - `repoId`, `methodFqn`, `onConfirmed` props 추가
    - 「확정」 버튼 (Loader2 + Check 아이콘) — `createManualBinding(repo_id, term_fqn, code_fqn=method@locator, scope=primary, confidence, decided_by="workbench-inline")`
    - 확정 후 카드 emerald-100 배경 + 「✓ 매핑 확정됨 → 라벨」 표시
    - 에러 시 빨강 박스 (≤80자)
    - suggestion 은 confirm 시 onConfirmed 콜백으로 부모 state 에서 제거 (visual)
  - **TermManagerPanel** 신규 (P21b)
    - Ontology 패널 최상단 collapsible (default 접힘)
    - `listTerms(repoId)` → 모든 BusinessTerm 표시 (라벨 / 도메인 / 확정 배지 / aliases)
    - 행별 「편집」 / 「삭제」 버튼 — `updateTerm(repoId, qualified_name, …)` / `deleteTerm(repoId, qualified_name)`
    - 인라인 편집 : canonical_label / aliases (콤마 split) / domain
    - 「+ 새 BusinessTerm 추가」 — qualified_name + canonical_label + aliases + domain
  - **ReferencePanel** 신규 (P21c)
    - R 「📚 참고」 placeholder 제거, 이 컴포넌트로 교체
    - `methodRules` 각각에 대해 `getLinkedFragments` 병렬 호출
    - rule 단위 그룹핑 (kind 배지 + statement[:80])
    - 각 fragment : source 배지 (manual_directive 파랑 / embedding 보라 / etc) + confidence % + doc 파일명 + 본문 line-clamp-3
    - 0건일 때 안내 (「매뉴얼 directive 또는 임베딩 매칭 후 노출」)
    - hoveredAnchor 정보 유지

## 검증 (curl, slab-design-real demo loaded)

```
GET /terms?repo_id=slab-design-real
→ 2 terms (열연공장코드 + aliases:[열연,hr_plant,hr_cd,hr_plant_cd], 품종코드 + aliases)

POST /bindings/manual
body: {term_fqn:..., code_fqn:method@anchor_locator, scope:primary, confidence:.., decided_by:workbench-inline}
→ confirmed binding 즉시 생성

GET /rules/{fqn}/manual-fragments
→ 119 rule 중 7 개에 fragment link (source=embedding, confidence ~0.6+)
  예: SdTargetWidthAction#rule1 → 1 frag (embedding)
```

## UI 변화
- **C-R Ontology 패널 상단** : 「📋 BusinessTerm 관리 (N개) 펼치기로 편집」 collapsible
- **anchor 카드 (auto-suggest 있을 때)** : 「→ 라벨 (source N%) [확정]」 inline 액션
- **R 패널 「📚 참고」** : placeholder 제거, 메서드 rule 들의 매뉴얼 fragment auto-link 표시 (rule 단위 그룹)

## "기능 100%" 의미
- 인라인 confirm (anchor → term 매핑) ✓
- 인라인 term CRUD (canonical / aliases / domain / 신규 추가) ✓
- 매뉴얼 fragment auto-link 노출 ✓
- 남은 「100% 자동화」 본질적 한계 :
  - GIGO (매뉴얼 부정확 → 매핑 부정확)
  - LLM 환각 (95~98% 한계)
  - 도메인 진화 (일회성 X, 지속적 작업)

## 다음 (P22)
ChangeSpec model + 시뮬레이션 bottom drawer 3 단계 (Q-U5).
또는 P23 spike (PythonGenerator 가설 검증) 우선 권장.
