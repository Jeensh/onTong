"use client";

import { ConflictPayload } from "@/lib/wiki/saveWithOCC";

export type ConflictAction =
  | { type: "reload" }      // discard local, load server
  | { type: "overwrite" }   // force-save my version (no If-Match)
  | { type: "cancel" };     // close modal, keep editing locally

export function ConflictResolutionModal(props: {
  conflict: ConflictPayload;
  myContent: string;
  onAction: (action: ConflictAction) => void;
}) {
  const { conflict, myContent, onAction } = props;
  const myLines = myContent.split("\n").length;
  const serverLines = conflict.server_content.split("\n").length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="conflict-title"
    >
      <div className="flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <header className="border-b border-amber-200 bg-amber-50 px-6 py-4">
          <h2 id="conflict-title" className="text-lg font-semibold text-amber-900">
            ⚠️ 다른 사용자가 먼저 저장했습니다
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            <code className="font-mono text-xs">{conflict.path}</code> 이/가 당신이 불러온 이후
            {conflict.server_updated_by ? (
              <> <b>{conflict.server_updated_by}</b> 에 의해</>
            ) : (
              <> 다른 누군가에 의해</>
            )}
            {" "}변경되었습니다. 진행 방식을 선택하세요.
          </p>
        </header>

        <div className="grid flex-1 grid-cols-2 gap-px overflow-hidden bg-slate-200">
          <section className="flex flex-col overflow-hidden bg-white">
            <div className="border-b border-slate-200 px-4 py-2">
              <h3 className="text-sm font-semibold text-slate-700">내 변경 사항</h3>
              <p className="text-xs text-slate-500">{myLines} 줄</p>
            </div>
            <pre className="flex-1 overflow-auto p-3 font-mono text-xs text-slate-800">
              {myContent}
            </pre>
          </section>

          <section className="flex flex-col overflow-hidden bg-white">
            <div className="border-b border-slate-200 px-4 py-2">
              <h3 className="text-sm font-semibold text-slate-700">서버의 현재 버전</h3>
              <p className="text-xs text-slate-500">
                {serverLines} 줄 · version{" "}
                <code className="font-mono">{conflict.server_version.slice(0, 8)}</code>
              </p>
            </div>
            <pre className="flex-1 overflow-auto p-3 font-mono text-xs text-slate-800">
              {conflict.server_content}
            </pre>
          </section>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button
            type="button"
            onClick={() => onAction({ type: "cancel" })}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            취소 (편집 계속)
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onAction({ type: "reload" })}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            >
              서버 버전으로 새로고침 (내 변경 폐기)
            </button>
            <button
              type="button"
              onClick={() => onAction({ type: "overwrite" })}
              className="rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700"
            >
              내 변경으로 덮어쓰기
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
