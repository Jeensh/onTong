"use client";

import { useEffect, useState } from "react";

export interface RenameUndoToastProps {
  auditId: string;
  oldPath: string;
  newPath: string;
  inboundDone: number;
  onDismiss: () => void;
  onUndoComplete?: (success: boolean, message: string) => void;
}

const UNDO_WINDOW_SECONDS = 5 * 60;

const userIdHeader = (): Record<string, string> => {
  if (typeof window === "undefined") return {};
  const id = localStorage.getItem("ontong_user_id") || "demo";
  return { "X-User-Id": id };
};

export function RenameUndoToast({
  auditId,
  oldPath,
  newPath,
  inboundDone,
  onDismiss,
  onUndoComplete,
}: RenameUndoToastProps) {
  const [remainingSec, setRemainingSec] = useState(UNDO_WINDOW_SECONDS);
  const [undoing, setUndoing] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setRemainingSec((s) => {
        if (s <= 1) {
          clearInterval(interval);
          onDismiss();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [onDismiss]);

  const minutes = Math.floor(remainingSec / 60);
  const seconds = remainingSec % 60;
  const timeStr = `${minutes}:${seconds.toString().padStart(2, "0")}`;

  const handleUndo = async () => {
    setUndoing(true);
    try {
      const r = await fetch(`/api/wiki/audit/${auditId}/undo`, {
        method: "POST",
        headers: userIdHeader(),
      });
      const body = await r.json();
      if (r.ok) {
        onUndoComplete?.(true, `되돌리기 완료 (${body.inbound_done}개 문서 복원)`);
      } else {
        onUndoComplete?.(false, body?.detail?.error ?? `HTTP ${r.status}`);
      }
    } catch (e: unknown) {
      onUndoComplete?.(false, String(e));
    } finally {
      setUndoing(false);
      onDismiss();
    }
  };

  return (
    <div className="fixed right-4 top-4 z-40 flex max-w-sm items-start gap-3 rounded-lg border border-emerald-300 bg-emerald-50 p-3 shadow-lg">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-emerald-900">이름 변경 완료</p>
        <p className="mt-0.5 truncate font-mono text-xs text-emerald-700">
          {oldPath} → {newPath}
        </p>
        <p className="mt-1 text-xs text-emerald-700">
          {inboundDone}개 문서가 자동 갱신됨
        </p>
      </div>
      <div className="flex flex-col items-stretch gap-1">
        <button
          type="button"
          onClick={handleUndo}
          disabled={undoing}
          className="rounded-md bg-white px-3 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-300 hover:bg-emerald-100 disabled:opacity-50"
          title="원래대로 되돌리기"
        >
          {undoing ? "복원 중…" : `↶ 되돌리기 (${timeStr})`}
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md px-3 py-0.5 text-xs text-emerald-700 hover:bg-emerald-100"
        >
          닫기
        </button>
      </div>
    </div>
  );
}
