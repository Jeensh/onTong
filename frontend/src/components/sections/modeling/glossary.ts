/**
 * Modeling 섹션 전용 용어 사전.
 *
 * `<HelpHint term="anchor" />` 의 인자로 쓰임. 사용자에게 친숙하지 않은 ontology /
 * mapping / verification 용어 의 짧은 설명 + 상세 + 예시 + 관련 용어.
 *
 * 새 용어 추가 시:
 *   - key: lowercase + underscore (예: `anchor_locator`)
 *   - label: 사용자에게 보일 이름 (한국어 OK)
 *   - summary: 1-2 줄 핵심 설명 (한국어)
 *   - detail: 2-4 개 bullet (선택, 추가 맥락)
 *   - example: 1 줄 구체 예시 (선택, code identifier 포함)
 *   - related: 다른 glossary key 들 (선택, 2-3 개 권장)
 *
 * 한국어 설명 / 영어 코드 identifier 가 원칙. 짧고 스캔 가능하게.
 */

/**
 * 신형 (Wave: glossary v2) — structured entry.
 *
 * - summary 가 있으면 popup body 의 메인 카피 (큰 글씨, 진하게).
 * - detail 은 bullet list 로 렌더 (작은 글씨, muted).
 * - example 은 mono + 살짝 강조된 배경의 한 줄.
 * - related 는 작은 chip 으로 — 같은 glossary 에 정의된 key 면 클릭해 다른 entry 로 swap.
 *
 * Backward compat: 옛 string 또는 `{label, short, example}` 모두 지원.
 */
export interface GlossaryEntryV2 {
  /** popup 헤더 — 사용자에게 보일 이름. */
  label: string;
  /** 1-2 줄 핵심 — 큰 글씨 본문. */
  summary: string;
  /** 추가 맥락 — bullet list. */
  detail?: string[];
  /** 구체 예시 — 한 줄, mono 강조. */
  example?: string;
  /** 관련 glossary key 들 — chip 으로 렌더. */
  related?: string[];
  /** 색조 — 카테고리별 강조 (선택). */
  tone?: "term" | "action" | "code" | "anchor" | "rule" | "verify" | "queue" | "neutral";
}

/** Legacy entry — 옛 코드와의 호환을 위해 유지. */
export interface GlossaryEntryLegacy {
  label: string;
  short: string;
  example?: string;
}

/** Public type — string (label only) | legacy | v2. */
export type GlossaryEntry = string | GlossaryEntryLegacy | GlossaryEntryV2;

/** Type guard — v2 인지. */
export function isGlossaryV2(e: GlossaryEntry): e is GlossaryEntryV2 {
  return typeof e === "object" && "summary" in e;
}

/** Type guard — legacy 인지. */
export function isGlossaryLegacy(e: GlossaryEntry): e is GlossaryEntryLegacy {
  return typeof e === "object" && "short" in e;
}

/** GlossaryEntry → 통일된 v2 로 변환. HelpHint 내부 렌더링용. */
export function toV2(e: GlossaryEntry, fallbackLabel: string): GlossaryEntryV2 {
  if (typeof e === "string") {
    return { label: fallbackLabel, summary: e };
  }
  if (isGlossaryV2(e)) return e;
  return { label: e.label, summary: e.short, example: e.example };
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  // ───────── 도메인 (BusinessTerm) ─────────
  term: {
    label: "Term (BusinessTerm)",
    summary: "도메인 의미 단위. 코드의 클래스/필드와 별도로 \"이 도메인에 무엇이 있는가\" 를 표현.",
    detail: [
      "코드 → ontology 의 첫 번째 매핑 layer.",
      "kind = atomic (값) 또는 composite (entity).",
      "fqn 은 `term.<domain>.<name>` 형식.",
    ],
    example: "term.scm.shared.grade (강종)",
    related: ["atomic", "composite", "term_kind", "type_realization"],
    tone: "term",
  },
  term_kind: {
    label: "Term.kind",
    summary: "Term 의 종류 — atomic (값 형식) 또는 composite (entity 객체).",
    detail: [
      "atomic = 더 못 쪼개는 값 (int / String / enum 등).",
      "composite = 여러 part 가 모여 만들어진 entity.",
      "종류에 따라 표시되는 facet 이 다름.",
    ],
    related: ["atomic", "composite"],
    tone: "term",
  },
  atomic: {
    label: "Atomic Term",
    summary: "더 쪼갤 수 없는 값 형식. value_type + unit + range + enum 으로 정의.",
    detail: [
      "value_type: int / float / String / boolean 등.",
      "unit: 단위 (mm, kg, °C 등) — 선택.",
      "range = [min, max] 로 허용 범위.",
      "enum_values 는 enum 일 때만.",
    ],
    example: "priority (int, range [1, 5])",
    related: ["term", "composite", "term_kind"],
    tone: "term",
  },
  composite: {
    label: "Composite Term",
    summary: "여러 atomic / composite 슬롯으로 구성된 entity. 실 코드의 entity class 와 1:1 매핑되는 경우 많음.",
    detail: [
      "Composition (parent.role_name → child term + cardinality).",
      "Inheritance (extends / implements) 가능.",
      "is_root_entity 면 Action 의 입출력으로 직접 참조.",
    ],
    example: "term.scm.std.customer_std (4 atomic + facets)",
    related: ["term", "atomic", "composition", "is_root_entity", "effective_parts"],
    tone: "term",
  },
  root_entity: {
    label: "Root Entity",
    summary: "다른 composite 의 part 가 되지 않고 독립적으로 존재하는 도메인 객체.",
    detail: [
      "Action 의 입력/출력으로 직접 참조됨.",
      "Order / Customer / Slab 등 \"덩어리\" 단위.",
      "non-root composite 는 root 의 part 로만 등장.",
    ],
    related: ["composite", "term", "composition"],
    tone: "term",
  },
  is_root_entity: {
    label: "is_root_entity (Term flag)",
    summary: "이 Term 이 root entity 인지의 boolean flag.",
    detail: [
      "true = 독립 entity, Action I/O 로 참조 가능.",
      "false = composite 의 part 로만 등장.",
    ],
    related: ["root_entity", "composite"],
    tone: "term",
  },
  struct_like_hint: {
    label: "struct_like_hint (Term flag)",
    summary: "Java struct 처럼 단순 데이터 묶음 hint — getter/setter 위주의 POJO.",
    detail: [
      "ontology recommender 가 entity vs DTO 구분에 활용.",
      "Action 매핑 우선순위 결정에 영향.",
    ],
    related: ["composite"],
    tone: "term",
  },

  // ───────── 매핑 (Type / Action Realization) ─────────
  type_realization: {
    label: "Type Realization",
    summary: "Term 이 어느 Java CodeType (class) 으로 실현되는지의 매핑.",
    detail: [
      "primary (1:1) — 기본 매칭.",
      "partial — 특정 조건에서만 적용 (subtype, value match 등).",
      "한 Term 은 primary realization 1 개 + partial 다수 가능.",
    ],
    related: ["primary", "partial", "code_type", "term"],
    tone: "code",
  },
  primary: {
    label: "Primary scope",
    summary: "이 매핑이 default 1:1 매칭. realization 1 개만 primary 가능.",
    detail: [
      "다형성 시 applies_to_subtype 으로 분기.",
      "Term 은 primary realization 을 통해 \"기본 코드 타입\" 을 가짐.",
    ],
    related: ["partial", "type_realization"],
    tone: "code",
  },
  partial: {
    label: "Partial scope",
    summary: "primary 가 따로 있고, 본 매핑은 특정 조건에서만 적용.",
    detail: [
      "조건: subtype, value match, annotation 등.",
      "여러 partial realization 공존 가능.",
    ],
    related: ["primary", "type_realization"],
    tone: "code",
  },
  realization: {
    label: "Realization",
    summary: "Action 이 어느 Java code_method 로 실 구현되는지의 매핑. 다형성 표현 가능.",
    detail: [
      "한 Action → 여러 method (서브타입 별).",
      "applies_to_code_type_fqn 으로 dispatch 분기.",
      "scope = primary | partial.",
      "dispatch_source 로 \"어떻게 결정했나\" 추적.",
    ],
    example: "MatchCustomerLimit → CustomerService.matchLimit() (primary)",
    related: ["dispatch_source", "primary", "partial", "code_method"],
    tone: "action",
  },
  realization_for_input: {
    label: "Realization for Input",
    summary: "특정 입력 타입에 대해 dispatch 될 realization 들 — 다형성 query.",
    detail: [
      "입력 타입의 subtype / 인터페이스 위계를 따라 매칭.",
      "primary 1 개 + applicable partial 들이 결과.",
    ],
    related: ["realization", "dispatch_source"],
    tone: "action",
  },
  dispatch_source: {
    label: "Dispatch Source",
    summary: "Realization 의 dispatch 를 어떻게 결정했는지의 9 종 출처.",
    detail: [
      "SINGLE_IMPL — 구현체 1 개.",
      "ANNOTATION — @Override 등 정적 단서.",
      "USER_CONFIRMED — 수동 합의.",
      "STATIC_UNRESOLVED — 모호, 큐로.",
    ],
    related: ["realization", "ambiguous_call_site"],
    tone: "action",
  },
  dispatch: {
    label: "Dispatch",
    summary: "런타임에 어느 method 가 실제 호출될지를 결정하는 과정.",
    detail: [
      "Java 의 가상 함수 호출 (virtual dispatch).",
      "interface 다중 구현 시 모호 — 사용자 confirm.",
      "정적 분석으로 SINGLE_IMPL / 모호 분류.",
    ],
    related: ["dispatch_source", "ambiguous_call_site", "call_site"],
    tone: "action",
  },
  mapping: {
    label: "Mapping",
    summary: "코드 ↔ ontology 의 모든 연결 — Term/Action/Realization/Anchor 의 통칭.",
    detail: [
      "TypeRealization (Term ↔ CodeType).",
      "Realization (Action ↔ CodeMethod).",
      "AnchorBinding (fragment ↔ Action slot).",
    ],
    related: ["type_realization", "realization", "anchor", "binding"],
    tone: "code",
  },
  binding: {
    label: "Binding",
    summary: "코드의 한 fragment / method 를 ontology 의 정확한 위치에 \"묶는\" 행위.",
    detail: [
      "AnchorBinding = method body 의 fragment ↔ Action slot.",
      "Realization = method ↔ Action 1:N.",
      "fragment 단위까지 내려가야 시뮬레이션 가능.",
    ],
    example: "matches.isEmpty() → action.metadata.fallback_kind",
    related: ["anchor", "realization", "anchor_locator", "target_slot"],
    tone: "anchor",
  },
  matching: {
    label: "Matching",
    summary: "추천 / 자동 분석으로 도출된 \"이게 저것에 해당할 가능성\" 의 후보 — 큐에서 confirm.",
    detail: [
      "Recommender 의 점수 + 근거 산출.",
      "사용자 confirm = matching → mapping 으로 승격.",
    ],
    related: ["mapping", "binding", "draft", "confidence"],
    tone: "queue",
  },

  // ───────── Action ─────────
  action: {
    label: "Action",
    summary: "도메인 의미의 \"무엇을 한다\" — 코드 method 와 1:N 매핑 (다형성).",
    detail: [
      "params / output 은 atomic / composite term 으로 구성.",
      "kind = pure_function / effectful / workflow.",
      "다형성: Realization 으로 서브타입별 method 분기.",
    ],
    example: "action.scm.std.match_customer_limit_for_order",
    related: ["pure_function", "effectful", "workflow", "realization", "declared_on_term"],
    tone: "action",
  },
  pure_function: {
    label: "Action.kind = pure_function",
    summary: "side-effect 없음. 같은 입력 → 같은 출력. 시뮬 / 검증 시 가장 안전한 분류.",
    detail: [
      "DB write / 외부 호출 ❌.",
      "재실행해도 안전.",
    ],
    related: ["action", "effectful", "workflow"],
    tone: "action",
  },
  effectful: {
    label: "Action.kind = effectful",
    summary: "DB write / 외부 호출 등 side-effect 있음.",
    detail: [
      "Action.effects 로 op (create/mutate/read/delete) + target_term 명시.",
      "시뮬 시 상태 mutation 추적 필요.",
    ],
    related: ["action", "pure_function", "workflow"],
    tone: "action",
  },
  workflow: {
    label: "Action.kind = workflow",
    summary: "직접 method 매핑 안 갖고, sub_actions 로 다른 Action 들의 control flow 만 표현.",
    detail: [
      "21-step 같은 multi-step 알고리즘에 사용.",
      "leaf Action 들이 실 구현.",
    ],
    example: "action.scm.슬랩설계_실행 (workflow, sub_actions=21)",
    related: ["action", "pure_function", "effectful"],
    tone: "action",
  },
  declared_on_term: {
    label: "Declared on Term",
    summary: "이 Action 이 어떤 Term 의 method 로 \"선언\" 됐는가.",
    detail: [
      "다형성 dispatch 의 base 타입 결정에 사용.",
      "Term.actions[] 의 역방향.",
    ],
    related: ["action", "term", "realization"],
    tone: "action",
  },

  // ───────── Anchor ─────────
  anchor: {
    label: "Anchor (AnchorBinding)",
    summary: "Java method body 안의 특정 fragment 를 Action 의 slot path 에 연결하는 fragment-level 매핑.",
    detail: [
      "코드 가독성을 ontology 와 묶는 핵심.",
      "literal / branch / expression 등 어떤 fragment 든 anchor 가능.",
      "신뢰도 0-1, user_confirmed=true 시 확정.",
    ],
    example: "matches.isEmpty() → null (line 35) → action.metadata.fallback_kind",
    related: ["anchor_locator", "target_slot", "code_method", "binding"],
    tone: "anchor",
  },
  anchor_locator: {
    label: "Anchor Locator",
    summary: "Java 의 어느 fragment 인지 텍스트로 식별. free-form 문자열.",
    detail: [
      "if-stmt@line-42 / literal:0.10 / param[0] 등.",
      "AnchorBinding.id 의 일부.",
      "코드 변경 시 anchor invalidation 의 단위.",
    ],
    example: "if-stmt@line-42",
    related: ["anchor", "target_slot"],
    tone: "anchor",
  },
  target_slot: {
    label: "Anchor Target Slot",
    summary: "이 anchor 가 가리키는 Action 의 slot path. 구조화 path syntax.",
    detail: [
      "params[i]<T>.spec.attr.range[1] 형식.",
      "Term.composition 트리를 따라 navigate.",
      "잘못된 path 는 backend resolve_path 가 reject.",
    ],
    example: "params[0]<RushOrder>.spec.diameter.range[1]",
    related: ["anchor", "anchor_locator", "composition"],
    tone: "anchor",
  },

  // ───────── BusinessRule ─────────
  business_rule: {
    label: "BusinessRule",
    summary: "도메인 제약. \"X 는 Y 범위여야 한다\" 같은 invariant.",
    detail: [
      "enforced_by 로 코드 가드 위치.",
      "operational_history 로 운영 사고 추적 — drama DNA.",
      "severity = hard | soft.",
    ],
    example: "rule.scm.order.no_stock_order — P-2018-0098 슬랩 중복 사고",
    related: ["severity", "enforced_by", "operational_history", "violated_at_call"],
    tone: "rule",
  },
  severity: {
    label: "BR Severity",
    summary: "hard = 위반 시 즉시 fail / soft = 경고.",
    detail: [
      "시뮬 verdict 6 조건 중 fail 분류에 영향.",
      "hard BR 위반 = 코드 머지 차단 권장.",
    ],
    related: ["business_rule"],
    tone: "rule",
  },
  enforced_by: {
    label: "BR.enforced_by",
    summary: "이 BR 을 코드에서 enforce 하는 method_fqn list.",
    detail: [
      "method 안의 throw / return null / fail() 등 가드 패턴.",
      "추가는 manual 또는 자동 검출 큐 통해.",
    ],
    related: ["business_rule", "code_method", "violated_at_call"],
    tone: "rule",
  },
  operational_history: {
    label: "BR.operational_history",
    summary: "이 BR 이 위반되어 발생한 운영 사고 history.",
    detail: [
      "incident_id + summary + occurred_at.",
      "drama DNA — \"왜 이 룰이 중요한가\" 의 출처.",
      "회귀 시뮬 시 ground truth 케이스로 활용.",
    ],
    related: ["business_rule", "violated_at_call"],
    tone: "rule",
  },
  violated_at_call: {
    label: "BR.violated_at_call",
    summary: "위반 가능 call site list.",
    detail: [
      "enforced_by method 를 호출하는 caller 중 BR 을 미리 검사 안 한 곳.",
      "코드 리팩토링 후보.",
    ],
    related: ["business_rule", "call_site", "enforced_by"],
    tone: "rule",
  },

  // ───────── Verification ─────────
  verification_level: {
    label: "Verification Level",
    summary: "Action 의 신뢰 단계 — 6 단계 자동 진급 + 외부 신호.",
    detail: [
      "UNMAPPED → DRAFT → SIGNATURE_LOCKED → BODY_ANCHORED → SIM_VERIFIED → PR_PROVEN.",
      "각 단계마다 진급 조건 자동 체크.",
      "PR_PROVEN 이 가장 신뢰 높음.",
    ],
    related: ["draft", "signature_locked", "body_anchored", "sim_verified", "pr_proven"],
    tone: "verify",
  },
  signature_locked: {
    label: "SIGNATURE_LOCKED",
    summary: "Action 의 입력/출력 type 이 코드 method signature 와 정합.",
    detail: [
      "params_json + output_json 채워짐.",
      "현 Phase 의 default 진급 단계.",
    ],
    related: ["verification_level", "draft", "body_anchored"],
    tone: "verify",
  },
  body_anchored: {
    label: "BODY_ANCHORED",
    summary: "method body 안의 anchor 들이 Action slot 에 매핑됨.",
    detail: [
      "Split mode 의 anchor marker 가 표시되는 단계.",
      "최소 1 개의 confirmed anchor 필요.",
    ],
    related: ["verification_level", "anchor", "signature_locked", "sim_verified"],
    tone: "verify",
  },
  sim_verified: {
    label: "SIM_VERIFIED",
    summary: "시뮬레이션 (Section 3) 이 Action 을 실 코드와 동일하게 dispatch 시뮬 통과.",
    detail: [
      "운영 사고 (operational_history) 회귀 통과.",
      "Section 3 시뮬레이션 산출.",
    ],
    related: ["verification_level", "body_anchored", "pr_proven", "operational_history"],
    tone: "verify",
  },
  pr_proven: {
    label: "PR_PROVEN",
    summary: "실 PR 의 변경이 ontology 변경과 정합 — 가장 신뢰 높은 단계.",
    detail: [
      "anchor invalidation 없음.",
      "verdict 6 조건 모두 통과.",
      "draft PR 머지 게이트.",
    ],
    related: ["verification_level", "sim_verified"],
    tone: "verify",
  },
  confirmed: {
    label: "Confirmed",
    summary: "사용자가 직접 합의/검수한 상태 (vs draft = 자동 추천 + 합의 대기).",
    detail: [
      "매핑 큐에서 confirm/reject 로 진급.",
      "audit_log 에 user_id + ts 기록.",
    ],
    related: ["draft", "audit_log"],
    tone: "queue",
  },

  // ───────── Code 쪽 ─────────
  code_type: {
    label: "CodeType",
    summary: "Java 의 class / interface / abstract class / enum / record 의 mirror.",
    detail: [
      "role 로 도메인/프레임워크/인프라 분류.",
      "ontology 의 Term 과 type_realization 으로 매핑.",
    ],
    related: ["role", "code_method", "type_realization", "term"],
    tone: "code",
  },
  code_method: {
    label: "CodeMethod",
    summary: "Java 의 method mirror. body_text + line_start/end + role 보유.",
    detail: [
      "role = business / helper / adapter / unknown.",
      "ontology 의 Action 과 realization 으로 매핑.",
      "anchors[] 는 정적 추출된 fragment marker.",
    ],
    related: ["code_type", "role", "realization", "anchor"],
    tone: "code",
  },
  role: {
    label: "Role",
    summary: "CodeType / Method 의 분류.",
    detail: [
      "domain = 도메인 핵심.",
      "framework = Spring / JPA 등 인프라 라이브러리.",
      "infra = 외부 의존 (DB / REST 클라이언트).",
      "unknown = 분류 보류.",
    ],
    related: ["code_type", "code_method"],
    tone: "code",
  },
  call_site: {
    label: "Call Site",
    summary: "method A 가 method B 를 호출하는 위치.",
    detail: [
      "static analysis 로 추출.",
      "dispatch 가 모호 (interface 다중 구현 등) 하면 user_queue 로.",
    ],
    related: ["ambiguous_call_site", "dispatch", "code_method"],
    tone: "code",
  },
  ambiguous_call_site: {
    label: "Ambiguous Call Site",
    summary: "정적 분석으로 어느 구현체가 호출될지 결정 안 됨.",
    detail: [
      "interface / abstract method + 다중 구현체.",
      "사용자가 가능한 runtime type 중 하나를 confirm.",
    ],
    related: ["call_site", "dispatch", "dispatch_source"],
    tone: "code",
  },

  // ───────── 신뢰도 / 메타 ─────────
  confidence: {
    label: "Confidence",
    summary: "0.0 ~ 1.0 매핑 신뢰도.",
    detail: [
      "1.0 = 사용자 confirm 또는 단일 구현 명확.",
      "0.5 미만 = 추천 단계, queue 로.",
      "근거는 rationale 필드.",
    ],
    related: ["draft", "confirmed"],
    tone: "queue",
  },
  draft: {
    label: "Draft",
    summary: "추천 또는 자동 생성 직후 상태. 사용자 합의 대기.",
    detail: [
      "confirmed=false 와 동의어로 쓰임.",
      "큐에서 confirm 시 verification_level 진급.",
    ],
    related: ["confirmed", "matching", "verification_level"],
    tone: "queue",
  },

  // ───────── Composition / Inheritance ─────────
  composition: {
    label: "Composition",
    summary: "composite term 의 part 관계.",
    detail: [
      "parent.role_name = child term + cardinality.",
      "cardinality: 1:1 / 0:1 / 1:N / 0:N.",
      "required true = 필수 part.",
    ],
    example: "Order.customer (1:1, required) → Customer",
    related: ["composite", "composition_part", "effective_parts", "inheritance"],
    tone: "term",
  },
  composition_part: {
    label: "Composition Part",
    summary: "composite term 안의 한 슬롯. role_name + child term + cardinality + required.",
    detail: [
      "여러 part 가 모여 composite 의 구조 정의.",
      "inheritance 통해 부모 part 도 상속.",
    ],
    related: ["composition", "effective_parts", "composite"],
    tone: "term",
  },
  effective_parts: {
    label: "Effective Parts",
    summary: "이 composite term 이 실제 가지는 모든 part — 자기 + 상속된 부모 part 들의 집합.",
    detail: [
      "Inheritance chain 따라 parent.parts 합산.",
      "API: GET /terms/{fqn}/effective-parts.",
    ],
    related: ["composition", "composition_part", "inheritance"],
    tone: "term",
  },
  inheritance: {
    label: "Inheritance",
    summary: "term 간 extends / implements 관계.",
    detail: [
      "atomic 은 가질 수 없음 (composite 만).",
      "사이클 금지.",
      "effective_parts 계산에 사용.",
    ],
    related: ["composite", "composition", "effective_parts"],
    tone: "term",
  },

  // ───────── Audit / History (신규) ─────────
  audit_log: {
    label: "Audit Log",
    summary: "entity 의 모든 변경 이력 — 누가, 언제, 무엇을 어떻게 바꿨는가.",
    detail: [
      "action: created / patched / confirmed / unconfirmed / deleted.",
      "field-level diff (before / after) 보존.",
      "RightPanel 의 \"이력\" 탭에서 표시.",
    ],
    related: ["before_after", "diff", "confirmed"],
    tone: "neutral",
  },
  before_after: {
    label: "Before / After",
    summary: "audit_log 의 변경 전후 값. JSON 직렬화 보존.",
    detail: [
      "field-level patch: { field: \"label\", before: \"X\", after: \"Y\" }.",
      "row-level (created / deleted) 은 entity 전체 snapshot.",
    ],
    related: ["audit_log", "diff"],
    tone: "neutral",
  },
  diff: {
    label: "Diff",
    summary: "before → after 의 변경 요약 — UI 에서 한 줄로 표시.",
    detail: [
      "field 단위 변경은 line-through (before) + 강조 (after).",
      "row-level 은 created / deleted 표시.",
    ],
    related: ["audit_log", "before_after"],
    tone: "neutral",
  },

  // ───────── Misc — UI / Storage ─────────
  peek: {
    label: "Peek (Code Peek)",
    summary: "현재 selection 을 잃지 않고 코드 본문을 모달로 잠깐 들여다보기.",
    detail: [
      "Eye 아이콘 클릭 또는 code_method primary click.",
      "Esc 또는 backdrop 클릭으로 닫기.",
      "Detail navigation 과 별개.",
    ],
    related: ["code_method", "code_type"],
    tone: "neutral",
  },
  extras: {
    label: "Extras (metadata)",
    summary: "DTO 의 free-form metadata 필드. 정형화되지 않은 추가 정보.",
    detail: [
      "key-value dict (Record<string, unknown>).",
      "추가 분석 결과 / 외부 시스템 ref 보관.",
    ],
    related: [],
    tone: "neutral",
  },
  metadata: {
    label: "Metadata",
    summary: "entity 에 부착된 부가 정보 — extras 와 유사.",
    detail: [
      "정형화된 schema 외의 보조 필드.",
      "extras / extra / annotations 등 구현마다 명칭 다름.",
    ],
    related: ["extras"],
    tone: "neutral",
  },
  repo: {
    label: "Repo (Repository)",
    summary: "온톨로지가 부착된 코드 저장소 단위.",
    detail: [
      "한 repo 는 한 ontology 인스턴스.",
      "repo_id 로 모든 entity 를 partition.",
    ],
    related: ["repo_id"],
    tone: "neutral",
  },
  repo_id: {
    label: "repo_id",
    summary: "repository 식별자. 모든 ontology entity 의 partition key.",
    detail: [
      "URL slug 형식 (예: slab-design-real).",
      "다중 repo 시 query 격리.",
    ],
    related: ["repo"],
    tone: "neutral",
  },
};

/**
 * 한 용어의 entry 조회. case-insensitive lookup.
 */
export function explain(term: string): GlossaryEntry | null {
  return GLOSSARY[term.toLowerCase()] ?? null;
}
