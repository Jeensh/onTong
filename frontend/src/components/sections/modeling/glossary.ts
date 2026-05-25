/**
 * Modeling 섹션 전용 용어 사전.
 *
 * `<HelpHint term="anchor" />` 의 인자로 쓰임. 사용자에게 친숙하지 않은 ontology /
 * mapping / verification 용어 의 짧은 설명 + 예시 1줄.
 *
 * 새 용어 추가 시: key 는 lowercase + underscore, label 은 사용자에게 보일 이름.
 */
export interface GlossaryEntry {
  label: string;
  short: string;       // 1-2 줄. tooltip 본문.
  example?: string;    // 선택. "예: ..." 한 줄.
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  // ───────── 도메인 (BusinessTerm) ─────────
  term: {
    label: "Term (BusinessTerm)",
    short: "도메인 의미 단위. 코드의 클래스/필드와 별도로 \"이 도메인에 무엇이 있는가\" 를 표현.",
    example: "예: term.scm.shared.grade (강종)",
  },
  atomic: {
    label: "Atomic (term.kind)",
    short: "더 쪼갤 수 없는 값 형식. value_type (int/float/string/bool) + unit + range + enum 으로 정의.",
    example: "예: priority (int, range [1, 5])",
  },
  composite: {
    label: "Composite (term.kind)",
    short: "여러 atomic / composite 슬롯으로 구성된 entity. 실 코드의 entity class 와 1:1 매핑되는 경우 많음.",
    example: "예: term.scm.std.customer_std (4 atomic + facets)",
  },
  root_entity: {
    label: "Root Entity",
    short: "다른 composite 의 part 가 되지 않고 독립적으로 존재하는 도메인 객체. Action 의 입력/출력으로 직접 참조됨.",
  },

  // ───────── 매핑 (Type / Action Realization) ─────────
  type_realization: {
    label: "Type Realization",
    short: "Term 이 어느 Java CodeType (class) 으로 실현되는지의 매핑. primary (1:1) 와 partial (조건부) 두 종류.",
  },
  primary: {
    label: "Primary scope",
    short: "이 매핑이 default 1:1 매칭. realization 1개만 primary 가능 (다형성 시 applies_to_subtype 으로 분기).",
  },
  partial: {
    label: "Partial scope",
    short: "primary 가 따로 있고, 본 매핑은 특정 조건 (subtype, value match 등) 에서만 적용.",
  },
  realization: {
    label: "Realization",
    short: "Action 이 어느 Java code_method 로 실 구현되는지의 매핑. 다형성 (서브타입 별 다른 method) 표현 가능.",
  },
  dispatch_source: {
    label: "Dispatch Source",
    short: "Realization 의 dispatch 를 어떻게 결정했는지. SINGLE_IMPL (구현체 1개) / ANNOTATION (@Override 등) / USER_CONFIRMED (수동) / STATIC_UNRESOLVED (모호 — 큐에서 선택) 등 9 종.",
  },

  // ───────── Action ─────────
  action: {
    label: "Action",
    short: "도메인 의미의 \"무엇을 한다\" — 코드 method 와 1:N 매핑 (다형성). params/output 은 atomic/composite term 으로 구성.",
    example: "예: action.scm.std.match_customer_limit_for_order",
  },
  pure_function: {
    label: "Action.kind = pure_function",
    short: "side-effect 없음. 같은 입력 → 같은 출력. 시뮬 / 검증 시 가장 안전한 분류.",
  },
  effectful: {
    label: "Action.kind = effectful",
    short: "DB write / 외부 호출 등 side-effect 있음. Action.effects 로 op (create/mutate/read/delete) + target_term 명시.",
  },
  workflow: {
    label: "Action.kind = workflow",
    short: "직접 method 매핑 안 갖고, sub_actions 로 다른 Action 들의 control flow 만 표현. 21-step 같은 multi-step 알고리즘.",
    example: "예: action.scm.Slab설계_실행 (workflow, sub_actions=21)",
  },
  declared_on_term: {
    label: "Declared on Term",
    short: "이 Action 이 어떤 Term 의 method 로 \"선언\" 됐는가. 다형성 dispatch 의 base 타입 결정에 사용.",
  },

  // ───────── Anchor ─────────
  anchor: {
    label: "Anchor (AnchorBinding)",
    short: "Java method body 안의 특정 fragment (literal, branch, expression) 를 Action 의 slot path 에 연결하는 fragment-level 매핑. 코드 가독성을 ontology 와 묶는 핵심.",
    example: "예: matches.isEmpty() → null (line 35) → action.metadata.fallback_kind",
  },
  anchor_locator: {
    label: "Anchor Locator",
    short: "Java 의 어느 fragment 인지 텍스트로 식별. \"matches.get(0)\" / \"literal:0.10\" / \"param[0]\" 등 free-form 문자열.",
  },
  target_slot: {
    label: "Anchor Target Slot",
    short: "이 anchor 가 가리키는 Action 의 slot path. params[0]<X>.spec.y 같은 구조화 path syntax.",
    example: "예: action.metadata.fallback_kind / params[0]<RushOrder>.spec.diameter.range[1]",
  },

  // ───────── BusinessRule ─────────
  business_rule: {
    label: "BusinessRule",
    short: "도메인 제약. \"X 는 Y 범위여야 한다\" 같은 invariant. enforced_by 로 코드 가드 위치, operational_history 로 운영 사고 추적.",
    example: "예: rule.scm.order.no_stock_order — P-2018-0098 Slab 중복 사고",
  },
  severity: {
    label: "BR Severity",
    short: "hard = 위반 시 즉시 fail / soft = 경고. 시뮬 verdict 의 verdict 6 조건에 영향.",
  },
  enforced_by: {
    label: "BR.enforced_by",
    short: "이 BR 을 코드에서 enforce 하는 method_fqn list. method 안의 throw / return null / fail() 등 가드 패턴.",
  },
  operational_history: {
    label: "BR.operational_history",
    short: "이 BR 이 위반되어 발생한 운영 사고 history (incident_id + summary + occurred_at). drama DNA 의 출처.",
  },
  violated_at_call: {
    label: "BR.violated_at_call",
    short: "위반 가능 call site list. enforced_by method 를 호출하는 caller 중 BR 을 미리 검사 안 한 곳.",
  },

  // ───────── Verification ─────────
  verification_level: {
    label: "Verification Level",
    short: "Action 의 신뢰 단계. UNMAPPED → DRAFT → SIGNATURE_LOCKED → BODY_ANCHORED → SIM_VERIFIED → PR_PROVEN. 자동 진급 + 외부 신호.",
  },
  unmapped: {
    label: "UNMAPPED",
    short: "아직 어떤 Java code_method 에도 매핑되지 않은 Action. 초기 추천 단계 또는 사용자가 직접 추가한 후 매핑 대기 상태.",
  },
  signature_locked: {
    label: "SIGNATURE_LOCKED",
    short: "Action 의 입력/출력 type 이 코드 method signature 와 정합. params_json + output_json 채워짐. (현 Phase 의 default 진급 단계.)",
  },
  body_anchored: {
    label: "BODY_ANCHORED",
    short: "method body 안의 anchor 들이 Action slot 에 매핑됨. Split mode 의 anchor marker 가 표시되는 단계.",
  },
  sim_verified: {
    label: "SIM_VERIFIED",
    short: "시뮬레이션 (Section 3) 이 Action 을 실 코드와 동일하게 dispatch 시뮬 통과. 운영 사고 회귀 통과.",
  },
  pr_proven: {
    label: "PR_PROVEN",
    short: "실 PR 의 변경이 ontology 변경과 정합 — anchor invalidation 없음 + verdict 통과. 가장 신뢰 높은 단계.",
  },
  confirmed: {
    label: "Confirmed",
    short: "사용자가 직접 합의/검수한 상태 (vs draft = 자동 추천 + 합의 대기). 매핑 큐에서 confirm/reject 로 진급.",
  },

  // ───────── Code 쪽 ─────────
  code_type: {
    label: "CodeType",
    short: "Java 의 class / interface / abstract class / enum / record 의 mirror. role 로 도메인/프레임워크/인프라 분류.",
  },
  code_method: {
    label: "CodeMethod",
    short: "Java 의 method mirror. body_text + line_start/end + role (business/helper/adapter) 보유.",
  },
  role: {
    label: "Role",
    short: "CodeType / Method 의 분류. domain (도메인 핵심) / framework (Spring/JPA 등) / infra (외부 의존) / unknown.",
  },
  call_site: {
    label: "Call Site",
    short: "method A 가 method B 를 호출하는 위치. dispatch 가 모호 (interface 다중 구현 등) 하면 user_queue 로.",
  },
  ambiguous_call_site: {
    label: "Ambiguous Call Site",
    short: "정적 분석으로 어느 구현체가 호출될지 결정 안 됨. 사용자가 가능한 runtime type 중 하나를 confirm.",
  },

  // ───────── 신뢰도 / 메타 ─────────
  confidence: {
    label: "Confidence",
    short: "0.0 ~ 1.0 매핑 신뢰도. 1.0 = 사용자 confirm 또는 단일 구현 명확. 0.5 미만 = 추천 단계, queue 로.",
  },
  draft: {
    label: "Draft",
    short: "추천 또는 자동 생성 직후 상태. 사용자 합의 대기 중. confirmed=false 와 동의어로 쓰임.",
  },

  // ───────── 매핑 큐 (좌측 ‘큐’ 탭) ─────────
  queue_term: {
    label: "큐 · Term",
    short: "이 repo 에 자동 추천된 BusinessTerm 중 사용자 confirm 대기 중인 항목. confirm 시 즉시 온톨로지에 편입되고 큐에서 빠짐. reject 하면 draft 가 제거됨.",
    example: "예: term.scm.shared.grade 추천 → confirm → 다른 Action 에서 참조 가능",
  },
  queue_action: {
    label: "큐 · Action",
    short: "Java method 분석으로 추출된 Action 후보. realization (어떤 method 가 이 Action 의 구현인지) 까지 함께 추천. confirm 시 verification_level 이 draft → signature_locked 으로 진급.",
  },
  queue_realization: {
    label: "큐 · Type Realization",
    short: "Term ↔ CodeType (Java class) 자동 매핑 후보. primary (1:1 default 매칭) 와 partial (특정 subtype/조건만) 두 종류. confidence 높은 순으로 정렬.",
  },
  queue_legacy_code: {
    label: "큐 · Code (legacy)",
    short: "정적 분석으로 결정 못 한 코드 큐. (1) Unmapped Method — 어떤 Action 으로도 매핑 안 된 method, (2) Ambiguous Call Site — interface 다중 구현 등으로 dispatch 모호한 호출. 사용자가 수동 결정.",
  },
  recommend: {
    label: "추천 (Recommend) 재실행",
    short: "자동 매핑 추천 알고리즘을 다시 돌립니다. confirmed=True 인 entity 는 보존 (idempotent). 새로 import 한 코드 / glossary 수정 / 매핑 보정 후 큐 재생성 용도.",
    example: "예: 코드 import 직후 → 추천 → 큐 차오름 → confirm 반복",
  },

  // ───────── Composition / Inheritance ─────────
  composition: {
    label: "Composition",
    short: "composite term 의 part 관계. parent.role_name = child term + cardinality (1:1 / 0:1 / 1:N / 0:N) + required.",
  },
  inheritance: {
    label: "Inheritance",
    short: "term 간 extends / implements 관계. atomic 은 가질 수 없음 (composite 만). 사이클 금지.",
  },
};

export function explain(term: string): GlossaryEntry | null {
  return GLOSSARY[term.toLowerCase()] ?? null;
}
