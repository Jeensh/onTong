"use client";

import { useState } from "react";
import { HelpCircle, X } from "lucide-react";

interface Props {
  title: string;
  body: React.ReactNode;
  className?: string;
}

/** 패널 헤더 옆 ? 아이콘 — 클릭 시 카드 형태 도움말. */
export function HelpPopover({ title, body, className = "" }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center rounded-full text-muted-foreground hover:text-primary hover:bg-muted/50 p-1 transition-colors"
        aria-label="이 메뉴 도움말"
        title="이게 뭐야?"
      >
        <HelpCircle size={16} />
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="absolute z-20 left-0 top-full mt-1 w-80 rounded-lg border border-border bg-card shadow-lg p-3 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <h4 className="text-sm font-semibold text-foreground">{title}</h4>
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="닫기"
              >
                <X size={14} />
              </button>
            </div>
            <div className="text-xs text-muted-foreground leading-relaxed space-y-2">
              {body}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
