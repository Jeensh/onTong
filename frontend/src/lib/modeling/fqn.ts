/**
 * Modeling FQN formatters — 긴 fully-qualified name 을 화면에서 짧게 보여주는 헬퍼.
 *
 * 모델링 UI 전체에서 path 가 너무 길어 줄바꿈 / 정렬 깨짐 발생.
 * 모든 FQN 표시는 이 모듈의 헬퍼를 거치도록 통일.
 *
 * 컨벤션:
 *   action.scm.std.match_customer_limit_for_order        → match_customer_limit_for_order
 *   term.scm.order.order                                  → order
 *   com.example.Foo.Bar                                   → Bar
 *   com.example.Foo.Bar.doIt(String,Integer)              → Bar.doIt(...)
 *   anchor_cumul_prod_invalid_check__v2                   → cumul_prod_invalid_check
 */

export type FqnKind = "action" | "term" | "code_type" | "code_method" | "rule" | "anchor";

/** 마지막 segment (dot 기준). 메서드 fqn 의 paren-portion 은 분리해서 처리. */
export function shortName(fqn: string): string {
  if (!fqn) return "";
  // method fqn: com.x.Y.foo(A,B) → 마지막 dot 은 ( 앞 portion 안에서 찾기
  const parenIdx = fqn.indexOf("(");
  const stem = parenIdx >= 0 ? fqn.slice(0, parenIdx) : fqn;
  const tail = stem.split(".").pop() ?? stem;
  const args = parenIdx >= 0 ? fqn.slice(parenIdx) : "";
  return tail + args;
}

/** code_method: ClassName.method(args) — 마지막 2 segment + args. */
export function methodTail(fqn: string): string {
  if (!fqn) return "";
  const parenIdx = fqn.indexOf("(");
  const stem = parenIdx >= 0 ? fqn.slice(0, parenIdx) : fqn;
  const parts = stem.split(".");
  const last = parts.pop() ?? "";
  const parent = parts.pop() ?? "";
  const head = parent ? `${parent}.${last}` : last;
  const args = parenIdx >= 0 ? fqn.slice(parenIdx) : "";
  // args 가 너무 길면 (...) 로 줄임
  const shortArgs = args.length > 24 ? "(...)" : args;
  return head + shortArgs;
}

/** action/term: prefix(action./term.) 떼고 마지막 2 segment 만. */
export function ontologyTail(fqn: string): string {
  if (!fqn) return "";
  // action.scm.std.match → std.match (도메인 + 이름)
  const trimmed = fqn.replace(/^(action|term)\./, "");
  const parts = trimmed.split(".");
  if (parts.length <= 2) return trimmed;
  return parts.slice(-2).join(".");
}

/** anchor id 같은 snake_case 에서 `__vN` suffix 제거 + 너무 길면 자르기. */
export function anchorTail(fqn: string, maxLen = 40): string {
  if (!fqn) return "";
  const cleaned = fqn.replace(/__v\d+$/, "");
  if (cleaned.length <= maxLen) return cleaned;
  return cleaned.slice(0, maxLen - 1) + "…";
}

/** 종류별 default short 표시 — 화면 한 줄에 들어오는 길이. */
export function prettyFqn(fqn: string, kind: FqnKind): string {
  if (!fqn) return "";
  switch (kind) {
    case "code_method": return methodTail(fqn);
    case "code_type":   return shortName(fqn);
    case "action":
    case "term":        return ontologyTail(fqn);
    case "rule":        return ontologyTail(fqn);
    case "anchor":      return anchorTail(fqn);
  }
}

/** "com.foo.Bar.Baz" → "com.foo.Bar" (마지막 segment 떼기). */
export function fqnParent(fqn: string): string {
  if (!fqn) return "";
  const parenIdx = fqn.indexOf("(");
  const stem = parenIdx >= 0 ? fqn.slice(0, parenIdx) : fqn;
  const idx = stem.lastIndexOf(".");
  if (idx < 0) return "";
  return stem.slice(0, idx);
}

/** package 만 (마지막 simple_name 떼고). code_type 용. */
export function fqnPackage(fqn: string): string {
  return fqnParent(fqn);
}
