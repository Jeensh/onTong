"use client";

/**
 * 샌드박스 메뉴 — 테스트 데이터 생성 + Python 코드 합성 + 격리 실행.
 * UI shell 고정 — modeling.simulate API 응답 그대로 활용.
 */

import { useState } from "react";
import { Beaker, Loader2, Play } from "lucide-react";
import { runSandbox, type StreamEvent } from "@/lib/section3/api";
import { EventStreamView } from "./EventStreamView";

const CASE_TYPES: Array<{ id: "normal" | "boundary" | "error"; label: string; tone: string }> = [
  { id: "normal", label: "정상", tone: "bg-emerald-100 text-emerald-700 border-emerald-300" },
  { id: "boundary", label: "경계", tone: "bg-amber-100 text-amber-700 border-amber-300" },
  { id: "error", label: "오류", tone: "bg-red-100 text-red-700 border-red-300" },
];

export function SandboxPanel() {
  const [targetKind, setTargetKind] = useState<"step" | "method" | "class">("step");
  const [targetId, setTargetId] = useState("1");
  const [selected, setSelected] = useState<Array<"normal" | "boundary" | "error">>(["normal", "boundary", "error"]);
  const [runAfter, setRunAfter] = useState(true);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [running, setRunning] = useState(false);

  const submit = async () => {
    if (running || !targetId.trim()) return;
    setRunning(true);
    setEvents([]);
    const collected: StreamEvent[] = [];
    try {
      await runSandbox(
        { target_kind: targetKind, target_id: targetId.trim(), case_types: selected, run_after_generate: runAfter },
        (ev) => {
          collected.push(ev);
          setEvents([...collected]);
        },
      );
    } catch (e) {
      collected.push({ type: "error", payload: { message: String(e) }, timestamp: new Date().toISOString() });
      setEvents([...collected]);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Beaker size={18} className="text-primary" />
          샌드박스 — 테스트 데이터 + 안전 가상 실행
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          modeling.simulate API 가 ontology 메타로 normal/boundary/error 케이스 생성 → LLM 으로 Python 합성 → 격리 subprocess 실행.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-4 p-4 flex-1 overflow-hidden">
        {/* Inputs */}
        <section className="space-y-3 overflow-y-auto pr-2">
          <div>
            <label className="block text-xs font-medium mb-1">대상 종류</label>
            <select
              value={targetKind}
              onChange={(e) => setTargetKind(e.target.value as any)}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="step">Step (ontology Step 번호)</option>
              <option value="method">Method (실험적 — modeling 미지원)</option>
              <option value="class">Class (실험적 — modeling 미지원)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">대상 ID</label>
            <input
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder={targetKind === "step" ? "Step 번호 (예: 1)" : "id"}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1">케이스 유형</label>
            <div className="flex flex-wrap gap-1.5">
              {CASE_TYPES.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelected((sel) => sel.includes(c.id) ? sel.filter((x) => x !== c.id) : [...sel, c.id])}
                  className={`px-2.5 py-1 rounded border text-xs ${selected.includes(c.id) ? c.tone : "border-border bg-background text-muted-foreground"}`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={runAfter} onChange={(e) => setRunAfter(e.target.checked)} />
            <span>코드 합성 후 sandbox 실행까지 진행</span>
          </label>

          <button
            onClick={submit}
            disabled={running || !targetId.trim() || selected.length === 0}
            className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            실행
          </button>
        </section>

        {/* Output stream */}
        <section className="overflow-y-auto rounded-lg border border-border bg-card p-3">
          {events.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-12">대상을 선택하고 실행을 누르세요.</div>
          ) : (
            <EventStreamView events={events} />
          )}
        </section>
      </div>
    </div>
  );
}
