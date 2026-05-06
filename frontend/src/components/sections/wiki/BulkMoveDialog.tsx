"use client";

import type { BulkMoveProgress } from "@/lib/wiki/bulkMove";

export interface BulkMoveDialogProps {
  pairs: { oldPath: string; newPath: string }[];
  targetFolder: string;
  inFlight: boolean;
  progress: BulkMoveProgress | null;
  onCancel: () => void;
  onConfirm: () => void;
}

export function BulkMoveDialog({
  pairs, targetFolder, inFlight, progress, onCancel, onConfirm,
}: BulkMoveDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <header className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {pairs.length}개 파일 이동
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            대상 폴더: <code className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs">{targetFolder || "/"}</code>
          </p>
        </header>

        <div className="flex-1 overflow-auto p-4">
          {!inFlight && (
            <ul className="max-h-64 divide-y rounded-md border border-slate-200">
              {pairs.map((p, i) => (
                <li key={i} className="flex items-center justify-between gap-2 px-3 py-1.5 text-xs">
                  <span className="truncate font-mono text-slate-700" title={p.oldPath}>
                    {p.oldPath}
                  </span>
                  <span className="shrink-0 text-slate-400">→</span>
                  <span className="truncate font-mono text-slate-900" title={p.newPath}>
                    {p.newPath}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {inFlight && progress && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>{progress.done}/{progress.total} 완료</span>
                {progress.failed > 0 && (
                  <span className="text-rose-600">{progress.failed} 실패</span>
                )}
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full bg-blue-600 transition-all"
                  style={{ width: `${(progress.done + progress.failed) / progress.total * 100}%` }}
                />
              </div>
              {progress.current && (
                <p className="truncate font-mono text-xs text-slate-500">
                  처리 중: {progress.current}
                </p>
              )}
              {progress.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-rose-600">
                    {progress.errors.length}개 오류 보기
                  </summary>
                  <ul className="mt-1 max-h-32 overflow-auto rounded border border-rose-200 bg-rose-50 p-2 text-xs">
                    {progress.errors.map((e, i) => (
                      <li key={i} className="font-mono">
                        <b>{e.path}</b>: {e.message}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={inFlight && progress?.current !== null && progress?.current !== undefined}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-50"
          >
            {inFlight ? "닫기" : "취소"}
          </button>
          {!inFlight && (
            <button
              type="button"
              onClick={onConfirm}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              {pairs.length}개 이동
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
