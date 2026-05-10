"use client";

import { useState } from "react";
import { ontologyApi } from "@/lib/api/ontology";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

/**
 * Confirmed / Draft 토글 버튼 — Term / Action / BR / Anchor 의 detail 카드에 박힘.
 *
 * - confirmed=true 일 때 클릭 → unconfirm (draft 로 되돌림)
 * - confirmed=false 일 때 클릭 → confirm
 *
 * 성공 시 onChanged() 로 부모에게 알려 detail 새로고침.
 *
 * 5-ii Stage 1.
 */
export function ConfirmToggle({
  kind,
  id,
  repoId,
  confirmed,
  onChanged,
}: {
  kind: "term" | "action" | "rule" | "anchor";
  id: string;
  repoId: string;
  confirmed: boolean;
  onChanged?: (newConfirmed: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onClick = async () => {
    setLoading(true);
    setErr(null);
    try {
      if (confirmed) {
        // unconfirm
        if (kind === "term")        await ontologyApi.unconfirmTerm(repoId, id);
        else if (kind === "action") await ontologyApi.unconfirmAction(repoId, id);
        else if (kind === "rule")   await ontologyApi.unconfirmBusinessRule(repoId, id);
        else if (kind === "anchor") await ontologyApi.unconfirmAnchorBinding(repoId, id);
        onChanged?.(false);
      } else {
        // confirm
        if (kind === "term")        await ontologyApi.confirmTerm(repoId, id);
        else if (kind === "action") await ontologyApi.confirmActionCandidate(repoId, id);
        else if (kind === "rule")   await ontologyApi.confirmBusinessRule(repoId, id);
        else if (kind === "anchor") await ontologyApi.confirmAnchorBinding(repoId, id);
        onChanged?.(true);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const label = confirmed ? "✓ confirmed" : "draft";
  const titleNext = confirmed
    ? "클릭 → draft 로 되돌림 (row 는 보존)"
    : "클릭 → confirmed 로 진급";

  return (
    <span className="inline-flex items-center gap-1">
      <button
        onClick={onClick}
        disabled={loading}
        title={titleNext}
        className={cn(
          "text-[11px] px-2 py-0.5 rounded-full border transition-colors inline-flex items-center gap-1",
          confirmed
            ? "border-emerald-400 text-emerald-700 bg-emerald-50 hover:bg-emerald-100"
            : "border-amber-400 text-amber-700 bg-amber-50 hover:bg-amber-100",
          loading && "opacity-50 cursor-wait",
        )}
      >
        {loading && <Loader2 className="w-3 h-3 animate-spin" />}
        {label}
      </button>
      {err && (
        <span className="text-[10px] text-rose-700 ml-1" title={err}>⚠</span>
      )}
    </span>
  );
}
