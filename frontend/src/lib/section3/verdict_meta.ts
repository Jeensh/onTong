/**
 * Phase 16S — HypothesisVerdict 신호등 메타 (공용 util).
 *
 * 이전: `GateExecutedReadOnlyCard.tsx` 의 로컬 `VERDICT_META`. 16P 패턴 적용.
 * 향후 verdict 시각화가 필요한 다른 컴포넌트 (dashboard 등) 가 재사용.
 */
import {
  CheckCircle2, AlertCircle, HelpCircle,
  type LucideIcon,
} from "lucide-react";
import type { HypothesisVerdict } from "./multiturn";

export interface VerdictMeta {
  label: string;
  cls: string;
  Icon: LucideIcon;
}

export const VERDICT_META: Record<HypothesisVerdict, VerdictMeta> = {
  yes: {
    label: "예",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-300",
    Icon: CheckCircle2,
  },
  likely_yes: {
    label: "예 (추정)",
    cls: "bg-emerald-50/70 text-emerald-700 border-emerald-200",
    Icon: CheckCircle2,
  },
  likely_no: {
    label: "아니오 (추정)",
    cls: "bg-amber-50 text-amber-700 border-amber-200",
    Icon: AlertCircle,
  },
  no: {
    label: "아니오",
    cls: "bg-rose-50 text-rose-700 border-rose-300",
    Icon: AlertCircle,
  },
  unknown: {
    label: "불명",
    cls: "bg-gray-100 text-gray-700 border-gray-300",
    Icon: HelpCircle,
  },
};

export function getVerdictMeta(verdict: HypothesisVerdict): VerdictMeta {
  return VERDICT_META[verdict];
}
