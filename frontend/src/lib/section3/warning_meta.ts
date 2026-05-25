/**
 * Phase 16P — integrity_warning 신호등 메타 (공용 util).
 *
 * 이전: GateExecutedReadOnlyCard (16E) + DashboardPanel (16L) 양쪽에 같은
 * WARNING_META 정의 중복. 향후 warning kind 추가 시 두 곳 sync 부담.
 *
 * 단일 source 로 추출:
 *   - WARNING_META: kind → { label / Icon / cls }
 *   - RED_KINDS / YELLOW_KINDS / YELLOW_GROUP_THRESHOLD (16I 그룹화 기준)
 *   - parseIntegrityWarnings: Provenance[] 에서 발화 kind 추출 (정규식 + dedupe)
 *
 * Provenance 는 카드 payload 의 sources 배열. detail 에 `integrity_warning=KIND`.
 */
import {
  AlertTriangle, FlaskConical, Languages,
  type LucideIcon,
} from "lucide-react";
import type { Provenance } from "./multiturn";

export type IntegrityWarningKind =
  | "target_is_test"
  | "body_unsupported_alias_gap"
  | "body_unsupported_no_rule"
  | "body_unsupported_rule_only"
  | "no_strong_evidence"
  | "cross_evidence_mismatch"
  | string;  // future-proof: 알려지지 않은 kind 도 surface

export interface WarningMeta {
  label: string;
  Icon: LucideIcon;
  cls: string;
}

export interface WarningSpec extends WarningMeta {
  kind: string;
}

/**
 * 16E 신호등 색상 정책:
 *  - target_is_test: 빨강 (production 대신 Test/Mock 선택 가능성 — verdict 신뢰 불가)
 *  - body_unsupported_alias_gap: 주황 (alias 보강 root cause)
 *  - body_unsupported_no_rule / _rule_only / no_strong_evidence: 노랑 (근거 약함)
 *  - cross_evidence_mismatch: 노랑 (근거 충돌)
 */
export const WARNING_META: Record<string, WarningMeta> = {
  target_is_test: {
    label: "Test 의심",
    Icon: FlaskConical,
    cls: "bg-rose-50 text-rose-700 border-rose-300",
  },
  body_unsupported_alias_gap: {
    label: "Alias gap",
    Icon: Languages,
    cls: "bg-orange-50 text-orange-700 border-orange-300",
  },
  body_unsupported_no_rule: {
    label: "근거 약함",
    Icon: AlertTriangle,
    cls: "bg-amber-50 text-amber-700 border-amber-200",
  },
  body_unsupported_rule_only: {
    label: "rule 추정",
    Icon: AlertTriangle,
    cls: "bg-amber-50 text-amber-700 border-amber-200",
  },
  no_strong_evidence: {
    label: "evidence 약함",
    Icon: AlertTriangle,
    cls: "bg-amber-50 text-amber-700 border-amber-200",
  },
  cross_evidence_mismatch: {
    label: "근거 충돌",
    Icon: AlertTriangle,
    cls: "bg-yellow-50 text-yellow-700 border-yellow-300",
  },
};

/** unknown kind 발화 시 fallback. */
export const UNKNOWN_WARNING_META: WarningMeta = {
  label: "unknown",
  Icon: AlertTriangle,
  cls: "bg-gray-100 text-gray-700 border-gray-300",
};

/** 16I 신호등 카테고리. */
export const RED_KINDS: ReadonlySet<string> = new Set(["target_is_test"]);
export const YELLOW_KINDS: ReadonlySet<string> = new Set([
  "body_unsupported_no_rule",
  "body_unsupported_rule_only",
  "no_strong_evidence",
  "cross_evidence_mismatch",
]);

/** 16I 노랑 N+ 그룹화 threshold (≥3 시 단일 그룹 칩). */
export const YELLOW_GROUP_THRESHOLD = 3;

/** Provenance[] 에서 integrity_warning kind 추출 (정규식 + dedupe). */
export function parseIntegrityWarnings(sources: Provenance[]): WarningSpec[] {
  const found: WarningSpec[] = [];
  const seen = new Set<string>();
  for (const s of sources) {
    const m = s.detail.match(/integrity_warning=([a-z_]+)/);
    if (!m) continue;
    const kind = m[1];
    if (seen.has(kind)) continue;
    seen.add(kind);
    const meta = WARNING_META[kind] ?? UNKNOWN_WARNING_META;
    found.push({ kind, ...meta });
  }
  return found;
}

/** kind → meta lookup (graceful fallback). */
export function getWarningMeta(kind: string): WarningMeta {
  return WARNING_META[kind] ?? UNKNOWN_WARNING_META;
}
