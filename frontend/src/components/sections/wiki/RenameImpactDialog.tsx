"use client";

import { useEffect, useState } from "react";
import type { RenamePlanResponse } from "@/lib/wiki/renameWithPreview";

export interface RenameImpactDialogProps {
  oldPath: string;
  newPath: string;
  plan: RenamePlanResponse | null;
  loading: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}

export function RenameImpactDialog({
  oldPath, newPath, plan, loading, error, onCancel, onConfirm,
}: RenameImpactDialogProps) {
  const [confirmAcknowledged, setConfirmAcknowledged] = useState(false);

  // Reset acknowledgement when plan changes
  useEffect(() => { setConfirmAcknowledged(false); }, [plan?.audit_id]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rename-dialog-title"
    >
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <header className="border-b border-slate-200 px-6 py-4">
          <h2 id="rename-dialog-title" className="text-lg font-semibold text-slate-900">
            이름 변경 영향도 확인
          </h2>
          <p className="mt-1 truncate font-mono text-xs text-slate-600">
            <span className="text-rose-600">{oldPath}</span>
            <span className="mx-2 text-slate-400">→</span>
            <span className="text-emerald-700">{newPath}</span>
          </p>
        </header>

        <div className="flex-1 overflow-auto p-6 text-sm">
          {loading && (
            <p className="text-slate-500">영향도 분석 중…</p>
          )}

          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-red-800">
              {error}
            </div>
          )}

          {plan && (
            <>
              <SummaryRow label="인용 중인 문서" value={`${plan.unique_inbound_sources} 개`} highlight={plan.unique_inbound_sources > 0} />
              <SummaryRow label="총 참조 개수" value={`${plan.inbound_count} 건`} />
              <SummaryRow label="예상 소요" value={`${plan.estimated_seconds.toFixed(1)} 초`} />

              {plan.confirm_required && (
                <div className="mt-4 rounded-md border border-amber-400 bg-amber-50 p-3 text-amber-900">
                  <p className="font-semibold">⚠️ 영향 범위가 큽니다</p>
                  <p className="mt-1 text-xs">
                    이 변경은 {plan.unique_inbound_sources} 개 문서를 자동 수정합니다.
                    되돌리려면 이름 변경 후 5분 안에 undo 를 실행해야 합니다.
                  </p>
                  <label className="mt-2 flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={confirmAcknowledged}
                      onChange={(e) => setConfirmAcknowledged(e.target.checked)}
                    />
                    위 내용을 확인했습니다.
                  </label>
                </div>
              )}

              {plan.impact_items.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 font-semibold text-slate-700">자동 수정될 문서 (상위 {plan.impact_items.length} 개):</p>
                  <ul className="max-h-48 divide-y overflow-auto rounded-md border border-slate-200 bg-slate-50">
                    {plan.impact_items.map((it, i) => (
                      <li key={i} className="flex items-center justify-between px-3 py-1.5 text-xs">
                        <span className="truncate font-mono text-slate-700">{it.source_path}</span>
                        <span className="ml-2 shrink-0 rounded bg-slate-200 px-2 py-0.5 text-slate-600">
                          {it.ref_count} ref
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {plan.unique_inbound_sources === 0 && (
                <p className="mt-2 text-xs text-slate-500">
                  이 파일을 인용하는 문서가 없습니다. 이름 변경은 단순 파일 이동만 수행합니다.
                </p>
              )}
            </>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={
              loading ||
              !!error ||
              !plan ||
              (plan.confirm_required && !confirmAcknowledged)
            }
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            이름 변경 진행
          </button>
        </footer>
      </div>
    </div>
  );
}

function SummaryRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2">
      <span className="text-slate-600">{label}</span>
      <span className={`font-mono text-sm ${highlight ? "font-semibold text-blue-700" : "text-slate-800"}`}>
        {value}
      </span>
    </div>
  );
}
