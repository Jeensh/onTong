/**
 * Description placeholder 핸들링 — backend 가 description 끝에 "자동 추천 — <FQN>"
 * 형식의 placeholder 를 붙여놓는 경우가 있음. 진짜 도메인 설명을 사용자가 채우기 전까지의
 * fallback 으로 의도된 것인데, UI 에 그대로 보이면 noise.
 *
 * 패턴 (R3-4 / R4-3):
 *   "<real text>\n\n자동 추천 — com.example.X.method(...)"
 *   "자동 추천 — com.example.X.method(...)"  (placeholder only)
 *   "<real text> 자동 추론 — ..."  (드물지만 가능)
 *
 * stripPlaceholderTrailer: 뒤쪽에 붙은 placeholder 제거. real text 만 남으면 그대로 반환,
 *   placeholder 만이면 빈 문자열.
 * isPurePlaceholder: 전체가 placeholder 인 경우 (=stripPlaceholderTrailer 결과가 빈 경우).
 */

// "자동 추(천|론) — ..." 패턴 — \s* 로 앞쪽 whitespace 흡수.
// `.` flag 없이 `[\s\S]*` 로 multi-line content 매칭.
const PLACEHOLDER_TRAILER_RE = /\s*자동\s*추[천론]\s*—[\s\S]*$/;

export function stripPlaceholderTrailer(desc: string | null | undefined): string {
  if (!desc) return "";
  return desc.replace(PLACEHOLDER_TRAILER_RE, "").trim();
}

export function isPurePlaceholder(desc: string | null | undefined): boolean {
  if (!desc) return false;
  return stripPlaceholderTrailer(desc) === "";
}
