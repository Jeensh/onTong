"use client";

import { useMemo, useState } from "react";
import { ConflictPayload } from "@/lib/wiki/saveWithOCC";
import { threeWayMerge, applyResolutionByIndex } from "@/lib/wiki/threeWayMerge";

export type ConflictAction =
  | { type: "merged"; content: string; baseVersion: string }
  | { type: "cancel" };

export function ConflictResolutionModal(props: {
  conflict: ConflictPayload;
  baseContent: string;     // client-captured at load time
  myContent: string;
  onAction: (action: ConflictAction) => void;
}) {
  const { conflict, baseContent, myContent, onAction } = props;

  const initialMerge = useMemo(
    () => threeWayMerge(baseContent, myContent, conflict.server_content),
    [baseContent, myContent, conflict.server_content]
  );

  const [merged, setMerged] = useState<string>(initialMerge.merged);
  const conflictBlocks = useMemo(
    () => threeWayMerge(baseContent, myContent, conflict.server_content).conflicts,
    [baseContent, myContent, conflict.server_content]
  );

  const remainingConflicts = useMemo(() => {
    return (merged.match(/^<<<<<<< MINE$/gm) ?? []).length;
  }, [merged]);

  const myLines = myContent.split("\n").length;
  const serverLines = conflict.server_content.split("\n").length;
  const baseLines = baseContent.split("\n").length;

  const resolveBlock = (idx: number, action: "ours" | "theirs" | "both") => {
    setMerged((m) => applyResolutionByIndex(m, idx, action));
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="flex max-h-[90vh] w-full max-w-7xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <header className="border-b border-amber-200 bg-amber-50 px-6 py-3">
          <h2 className="text-lg font-semibold text-amber-900">
            ⚠️ 동시 편집 충돌 — 3-way 머지
          </h2>
          <p className="mt-0.5 text-sm text-amber-800">
            <code className="font-mono text-xs">{conflict.path}</code> 이/가 당신이 불러온 이후
            {conflict.server_updated_by ? <> <b>{conflict.server_updated_by}</b>에 의해</> : <> 다른 사용자에 의해</>}
            {" "}변경되었습니다. 자동 머지 후 충돌 부분을 수동으로 해결하세요.
          </p>
          {remainingConflicts > 0 && (
            <p className="mt-1 text-xs font-semibold text-rose-700">
              해결 필요: {remainingConflicts}개 충돌 블록
            </p>
          )}
        </header>

        <div className="grid flex-1 grid-cols-3 gap-px overflow-hidden bg-slate-200">
          <Column title={`기준 (Base, ${baseLines}줄)`} content={baseContent} variant="base" />
          <Column title={`내 변경 (Mine, ${myLines}줄)`} content={myContent} variant="mine" />
          <Column
            title={`서버 (Server, ${serverLines}줄, v${conflict.server_version.slice(0, 8)})`}
            content={conflict.server_content}
            variant="server"
          />
        </div>

        <div className="flex h-1/3 flex-col border-t border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-1.5">
            <h3 className="text-sm font-semibold text-slate-800">머지 결과 (저장될 내용)</h3>
            {conflictBlocks.length > 0 && (
              <div className="flex gap-1">
                {conflictBlocks.map((_, i) => (
                  <ConflictBlockButtons
                    key={i}
                    index={i}
                    onResolve={(action) => resolveBlock(i, action)}
                  />
                ))}
              </div>
            )}
          </div>
          <textarea
            value={merged}
            onChange={(e) => setMerged(e.target.value)}
            className="flex-1 resize-none p-3 font-mono text-xs text-slate-900 focus:outline-none"
            spellCheck={false}
          />
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-2">
          <button
            type="button"
            onClick={() => onAction({ type: "cancel" })}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-100"
          >
            취소 (편집 계속)
          </button>
          <button
            type="button"
            onClick={() => onAction({ type: "merged", content: merged, baseVersion: conflict.server_version })}
            disabled={remainingConflicts > 0}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            title={remainingConflicts > 0 ? "모든 충돌 블록을 해결하세요" : ""}
          >
            머지 결과로 저장
          </button>
        </footer>
      </div>
    </div>
  );
}

function Column({ title, content, variant }: { title: string; content: string; variant: "base" | "mine" | "server" }) {
  const tint = variant === "base" ? "bg-slate-50" : variant === "mine" ? "bg-blue-50" : "bg-emerald-50";
  return (
    <section className="flex flex-col overflow-hidden bg-white">
      <div className={`border-b border-slate-200 px-3 py-1.5 ${tint}`}>
        <h3 className="truncate text-xs font-semibold text-slate-700">{title}</h3>
      </div>
      <pre className="flex-1 overflow-auto p-2 font-mono text-[11px] leading-snug text-slate-800">
        {content}
      </pre>
    </section>
  );
}

function ConflictBlockButtons({ index, onResolve }: { index: number; onResolve: (action: "ours" | "theirs" | "both") => void }) {
  return (
    <div className="flex gap-0.5 rounded border border-slate-300 bg-white">
      <span className="border-r border-slate-300 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
        충돌 {index + 1}
      </span>
      <button
        type="button"
        onClick={() => onResolve("ours")}
        className="px-2 py-0.5 text-[10px] hover:bg-blue-100"
        title="내 변경 채택"
      >
        내 것
      </button>
      <button
        type="button"
        onClick={() => onResolve("theirs")}
        className="px-2 py-0.5 text-[10px] hover:bg-emerald-100"
        title="서버 변경 채택"
      >
        서버
      </button>
      <button
        type="button"
        onClick={() => onResolve("both")}
        className="px-2 py-0.5 text-[10px] hover:bg-amber-100"
        title="둘 다 유지"
      >
        둘 다
      </button>
    </div>
  );
}
