"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Network,
  MessageSquareQuote,
} from "lucide-react";
import type { DocumentMetadata } from "@/types";

interface ConfidenceData {
  score: number;
  tier: string;
  stale: boolean;
  stale_months: number;
  signals: Record<string, number>;
  citation_count: number;
  newer_alternatives: Array<{
    path: string;
    title: string;
    confidence_score: number;
    confidence_tier: string;
  }>;
}

interface FeedbackData {
  verified_count: number;
  needs_update_count: number;
  last_verified_at: number;
  last_verified_by: string;
}

interface LinkedDocsCounts {
  total: number;
}

export interface DocumentInfoBarProps {
  filePath: string;
  metadata: DocumentMetadata;
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  onOpenDrawerTab: (tab: string) => void;
  // Shared state lifted up so drawer can use it
  confidenceData: ConfidenceData | null;
  feedbackData: FeedbackData | null;
  onConfidenceUpdate: (data: ConfidenceData) => void;
  onFeedbackUpdate: (data: FeedbackData) => void;
  linkedDocsCounts: LinkedDocsCounts;
}

const SIGNAL_DEFS = [
  { key: "freshness", label: "최신성", weight: 25, desc: "최근 수정일 기준" },
  { key: "status", label: "문서 상태", weight: 25, desc: "approved/review/draft 등" },
  { key: "metadata_completeness", label: "메타데이터", weight: 15, desc: "domain, process, tags, 작성자" },
  { key: "backlinks", label: "역참조", weight: 10, desc: "다른 문서에서 참조 횟수" },
  { key: "owner_activity", label: "작성자 활동", weight: 10, desc: "최근 90일 편집 이력" },
  { key: "user_feedback", label: "사용자 피드백", weight: 15, desc: "확인/수정요청 비율" },
];

function getApiBase() {
  return typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8001" : "";
}

export function DocumentInfoBar({
  filePath,
  metadata,
  drawerOpen,
  onToggleDrawer,
  onOpenDrawerTab,
  confidenceData,
  feedbackData,
  onConfidenceUpdate,
  onFeedbackUpdate,
  linkedDocsCounts,
}: DocumentInfoBarProps) {
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [showSignals, setShowSignals] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null);

  const submitFeedback = useCallback(async (action: "verified" | "needs_update") => {
    setFeedbackLoading(true);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/wiki/feedback/${encodeURIComponent(filePath)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const result = await res.json();
        onFeedbackUpdate(result.feedback);
        const confRes = await fetch(`${base}/api/wiki/confidence/${encodeURIComponent(filePath)}`);
        if (confRes.ok) {
          const conf = await confRes.json();
          if (conf && typeof conf.score === "number") onConfidenceUpdate(conf);
        }
      }
    } catch {}
    setFeedbackLoading(false);
  }, [filePath, onConfidenceUpdate, onFeedbackUpdate]);

  // Close signal popover on click outside
  useEffect(() => {
    if (!showSignals) return;
    const handler = (e: MouseEvent) => {
      if (pillRef.current && !pillRef.current.contains(e.target as Node)) {
        setShowSignals(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showSignals]);

  const data = confidenceData;

  const statusColors: Record<string, string> = {
    approved: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    deprecated: "bg-destructive/10 text-destructive",
    draft: "bg-muted text-muted-foreground",
  };

  const tierColor = data
    ? data.tier === "high"
      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
      : data.tier === "medium"
      ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
      : "bg-muted text-muted-foreground"
    : "";

  const dotColor = data
    ? data.tier === "high" ? "bg-emerald-500" : data.tier === "medium" ? "bg-amber-500" : "bg-muted-foreground/50"
    : "bg-muted-foreground/30";

  return (
    <div data-info-bar className="flex items-center gap-1.5 px-3 py-1 border-b text-xs min-h-[32px] bg-background">
      {/* Status badge */}
      {metadata.status && (
        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium shrink-0 ${statusColors[metadata.status] || statusColors.draft}`}>
          {metadata.status}
        </span>
      )}

      {/* Domain / Process */}
      {(metadata.domain || metadata.process) && (
        <span className="text-muted-foreground truncate max-w-[180px] shrink-0">
          {metadata.domain}{metadata.process && ` · ${metadata.process}`}
        </span>
      )}

      {/* Tags count (detail in drawer) */}
      {metadata.tags.length > 0 && (
        <button
          onClick={() => onOpenDrawerTab("metadata")}
          className="text-muted-foreground/60 hover:text-muted-foreground transition-colors shrink-0"
          title={metadata.tags.join(", ")}
        >
          {metadata.tags.length}태그
        </button>
      )}

      {/* Confidence pill */}
      {data && (
        <div ref={pillRef} className="relative shrink-0">
          <span
            onClick={() => setShowSignals((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium cursor-pointer select-none transition-colors ${tierColor}`}
          >
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} />
            {data.score}
          </span>

          {/* Signal detail popover */}
          {showSignals && (
            <div className="absolute left-0 top-full mt-1 z-50 bg-popover border rounded-lg shadow-lg p-3 w-72 text-xs">
              <div className="font-semibold mb-2 text-foreground">신뢰도 점수 상세</div>
              <div className="text-[11px] text-muted-foreground mb-2">
                6개 시그널의 가중 합산으로 계산됩니다.
              </div>
              <div className="space-y-1.5">
                {SIGNAL_DEFS.map(({ key, label, weight, desc }) => {
                  const val = data.signals[key] ?? 0;
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between">
                        <span className="text-foreground">
                          {label} <span className="text-muted-foreground">({weight}%)</span>
                        </span>
                        <span className={`font-mono font-medium ${
                          val >= 70 ? "text-emerald-600 dark:text-emerald-400"
                            : val >= 40 ? "text-amber-600 dark:text-amber-400"
                            : "text-muted-foreground"
                        }`}>
                          {Math.round(val)}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 mt-0.5">
                        <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              val >= 70 ? "bg-emerald-500" : val >= 40 ? "bg-amber-500" : "bg-muted-foreground/40"
                            }`}
                            style={{ width: `${Math.min(val, 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-muted-foreground w-24 text-right">{desc}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              {data.citation_count > 0 && (
                <div className="mt-2 pt-2 border-t text-muted-foreground flex items-center gap-1">
                  <MessageSquareQuote className="h-3 w-3" />
                  AI 답변에서 {data.citation_count}회 인용됨
                </div>
              )}
              <div className="mt-2 pt-2 border-t text-[10px] text-muted-foreground">
                클릭하여 닫기
              </div>
            </div>
          )}
        </div>
      )}

      {/* Stale indicator */}
      {data?.stale && (
        <span
          className="inline-block h-2 w-2 rounded-full bg-amber-500 shrink-0 cursor-pointer"
          title={`${data.stale_months}개월 이상 미수정`}
          onClick={() => onOpenDrawerTab("trust")}
        />
      )}

      {/* Connected docs count */}
      {linkedDocsCounts.total > 0 && (
        <button
          onClick={() => onOpenDrawerTab("connections")}
          className="inline-flex items-center gap-0.5 text-muted-foreground hover:text-foreground transition-colors shrink-0"
          title="연결된 문서"
        >
          <Network className="h-3 w-3" />
          <span>{linkedDocsCounts.total}</span>
        </button>
      )}

      {/* Spacer — click empty area to toggle drawer */}
      <div
        className="flex-1 min-h-[24px] cursor-pointer"
        onClick={onToggleDrawer}
        title="상세 정보 (⌘I)"
      />

      {/* Compact feedback buttons */}
      <button
        disabled={feedbackLoading}
        onClick={() => submitFeedback("verified")}
        className="p-1 rounded text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10 transition-colors disabled:opacity-50 shrink-0"
        title="확인했음"
      >
        <CheckCircle2 className="h-3.5 w-3.5" />
      </button>
      <button
        disabled={feedbackLoading}
        onClick={() => submitFeedback("needs_update")}
        className="p-1 rounded text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 transition-colors disabled:opacity-50 shrink-0"
        title="수정 필요"
      >
        <AlertCircle className="h-3.5 w-3.5" />
      </button>

      {/* Feedback count (detail in drawer) */}

      {/* Expand/collapse drawer */}
      <button
        onClick={onToggleDrawer}
        className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
        title="상세 정보 (⌘I)"
      >
        {drawerOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}
