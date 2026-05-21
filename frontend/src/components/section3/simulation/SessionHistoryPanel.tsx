"use client";

/** 시뮬레이션 대화 이력 viewer — 좌측 chat 상단 collapsible. */
import { useEffect, useState } from "react";
import { History, RotateCcw } from "lucide-react";

interface SessionSummary {
  session_id: string;
  repo_id: string;
  intent: string | null;
  status: string;
  user_query: string | null;
  created_at: string;
  last_activity_at: string;
}

const INTENT_COLOR: Record<string, string> = {
  simulate: "text-emerald-700 bg-emerald-100",
  impact:   "text-amber-700 bg-amber-100",
  locate:   "text-sky-700 bg-sky-100",
  explain:  "text-violet-700 bg-violet-100",
  hypothesis: "text-rose-700 bg-rose-100",
};

export function SessionHistoryPanel({ currentSid, onPick }: {
  currentSid: string | null;
  onPick: (sid: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  async function refresh() {
    try {
      const r = await fetch("/api/section3/simulation/sessions?limit=20");
      if (r.ok) setSessions(await r.json());
    } catch {}
  }
  useEffect(() => {
    refresh();
  }, [currentSid]);

  return (
    <div className="border-b border-gray-200">
      <button
        onClick={() => { setOpen((o) => !o); if (!open) refresh(); }}
        className="w-full px-4 py-2 flex items-center gap-2 text-xs text-gray-600 hover:bg-gray-50"
      >
        <History size={13} />
        <span>대화 이력 ({sessions.length})</span>
        <button onClick={(e) => { e.stopPropagation(); refresh(); }} className="ml-auto text-gray-400 hover:text-emerald-700">
          <RotateCcw size={11} />
        </button>
        <span className="text-gray-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ul className="max-h-48 overflow-y-auto bg-white">
          {sessions.length === 0 && <li className="px-4 py-2 text-[11px] text-gray-400">이력 없음</li>}
          {sessions.map((s) => {
            const isCurrent = s.session_id === currentSid;
            const date = new Date(s.last_activity_at);
            return (
              <li key={s.session_id}>
                <button
                  onClick={() => onPick(s.session_id)}
                  className={
                    "w-full text-left px-3 py-1.5 text-[11px] hover:bg-emerald-50 border-l-2 " +
                    (isCurrent ? "bg-emerald-50/40 border-emerald-500" : "border-transparent")
                  }
                >
                  <div className="flex items-center gap-1.5">
                    {s.intent && (
                      <span className={"px-1 rounded text-[9px] " + (INTENT_COLOR[s.intent] ?? "bg-gray-100 text-gray-600")}>
                        {s.intent}
                      </span>
                    )}
                    <span className={
                      "text-[9px] " + (
                        s.status === "done" ? "text-emerald-600" :
                        s.status === "aborted" ? "text-red-500" : "text-amber-500"
                      )
                    }>{s.status}</span>
                    <span className="text-gray-400 ml-auto">{date.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <div className="text-gray-800 truncate mt-0.5" title={s.user_query ?? ""}>
                    {s.user_query ?? "(no query)"}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
