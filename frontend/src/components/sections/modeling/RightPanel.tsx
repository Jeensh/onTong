"use client";

import { useEffect, useRef, useState } from "react";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "code", label: "📄 코드" },
  { id: "manual", label: "📖 매뉴얼" },
  { id: "callsite", label: "📞 호출지점" },
  { id: "impact", label: "🌊 영향" },
];

export function RightPanel() {
  const { rightWidth, setRightWidth, setMainMode } = useWorkbench();
  const [activeTab, setActiveTab] = useState<string>("code");
  const dragRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = dragRef.current;
    if (!handle) return;
    let dragging = false;
    const onDown = (e: MouseEvent) => {
      dragging = true;
      document.body.style.cursor = "col-resize";
      e.preventDefault();
    };
    const onMove = (e: MouseEvent) => {
      if (!dragging) return;
      setRightWidth(window.innerWidth - e.clientX);
    };
    const onUp = () => {
      dragging = false;
      document.body.style.cursor = "";
    };
    handle.addEventListener("mousedown", onDown);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      handle.removeEventListener("mousedown", onDown);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [setRightWidth]);

  return (
    <aside
      className="bg-card border-l border-border flex flex-col overflow-hidden relative"
      style={{ gridArea: "right", width: rightWidth }}
    >
      <div
        ref={dragRef}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary z-10"
        title="드래그로 너비 조정"
      />
      <div className="flex border-b border-border px-2 pt-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={cn(
              "rounded-t px-2.5 py-1 text-[11.5px] border-b-2",
              activeTab === t.id
                ? "text-foreground border-primary"
                : "text-muted-foreground border-transparent hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="px-2.5 py-1 border-b border-border bg-muted/40 flex gap-1.5">
        <button
          onClick={() => setMainMode("split")}
          className="text-[10.5px] px-2 py-0.5 rounded border border-primary text-primary hover:bg-primary/10"
        >
          ↕ Split mode 로
        </button>
        <div className="flex-1" />
        <button title="resize" className="text-[10.5px] px-1.5 py-0.5 text-muted-foreground">
          ↔
        </button>
        <button title="별창" className="text-[10.5px] px-1.5 py-0.5 text-muted-foreground">
          ⤢
        </button>
      </div>
      <div className="overflow-y-auto flex-1 p-3 text-xs">
        {activeTab === "code" && (
          <div>
            <h4 className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
              코드 본체
            </h4>
            <p className="text-muted-foreground">(선택된 Action 의 realizations 코드 — backend 데이터 필요)</p>
          </div>
        )}
        {activeTab === "manual" && (
          <p className="text-muted-foreground">매뉴얼 fragment 표시 (DESCRIBED_IN 통한)</p>
        )}
        {activeTab === "callsite" && (
          <p className="text-muted-foreground">호출 사이트 + 모호 dispatch 큐</p>
        )}
        {activeTab === "impact" && (
          <p className="text-muted-foreground">변경 영향 미리보기 (Backward 모드와 연계)</p>
        )}
      </div>
    </aside>
  );
}
