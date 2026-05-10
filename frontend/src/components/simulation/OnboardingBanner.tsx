"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Lightbulb, X } from "lucide-react";

interface Step {
  id: string;
  title: string;
  body: string;
  cta?: { label: string; targetView: string };
}

interface Props {
  storageKey?: string;
  steps: Step[];
  onJump?: (view: string) => void;
}

/** 첫 진입 시 5단계 미니 투어. localStorage 로 dismiss 기억. */
export function OnboardingBanner({
  storageKey = "section3_onboarding_dismissed_v1",
  steps,
  onJump,
}: Props) {
  const [idx, setIdx] = useState(0);
  const [hidden, setHidden] = useState<boolean>(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const dismissed = window.localStorage.getItem(storageKey);
    setHidden(dismissed === "1");
  }, [storageKey]);

  if (hidden) {
    return (
      <button
        onClick={() => {
          window.localStorage.removeItem(storageKey);
          setHidden(false);
          setIdx(0);
        }}
        className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground underline mb-2"
      >
        <Lightbulb size={12} /> 사용 가이드 다시 보기
      </button>
    );
  }

  const cur = steps[idx];

  const dismiss = () => {
    window.localStorage.setItem(storageKey, "1");
    setHidden(true);
  };

  const next = () => {
    if (idx < steps.length - 1) setIdx(idx + 1);
    else dismiss();
  };

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3 mb-4">
      <div className="flex items-start gap-3">
        <div className="rounded-full bg-primary/10 p-2 flex-shrink-0">
          <Lightbulb size={18} className="text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <h3 className="text-sm font-semibold text-foreground">
              <span className="text-primary mr-1.5">[{idx + 1}/{steps.length}]</span>
              {cur.title}
            </h3>
            <button
              onClick={dismiss}
              className="text-muted-foreground hover:text-foreground p-0.5"
              aria-label="가이드 닫기"
            >
              <X size={14} />
            </button>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">{cur.body}</p>
          <div className="flex items-center gap-2 mt-3">
            {cur.cta && onJump && (
              <button
                onClick={() => {
                  onJump(cur.cta!.targetView);
                  next();
                }}
                className="inline-flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
              >
                {cur.cta.label} <ArrowRight size={11} />
              </button>
            )}
            <button
              onClick={next}
              className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
            >
              {idx < steps.length - 1 ? "다음" : "닫기"}
            </button>
            {idx > 0 && (
              <button
                onClick={() => setIdx(idx - 1)}
                className="inline-flex items-center gap-1 rounded text-xs text-muted-foreground hover:text-foreground px-1"
              >
                이전
              </button>
            )}
            <span className="ml-auto text-[10px] text-muted-foreground/60">
              5분 투어 — 평가 기준 매핑
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
