"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Sparkles, MessageSquareQuote, CheckCircle2, AlertCircle } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { getCurrentUserName } from "@/lib/auth/currentUser";

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

interface TrustBannerProps {
  filePath: string;
}

const SIGNAL_DEFS = [
  { key: "freshness", label: "최신성", weight: 30, desc: "최근 수정일 기준" },
  { key: "status", label: "문서 상태", weight: 25, desc: "approved/review/draft 등" },
  { key: "metadata_completeness", label: "메타데이터", weight: 15, desc: "domain, process, tags, 작성자" },
  { key: "backlinks", label: "역참조", weight: 15, desc: "다른 문서에서 참조 횟수" },
  { key: "owner_activity", label: "작성자 활동", weight: 15, desc: "최근 90일 편집 이력" },
];

function getApiBase() {
  return typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8001" : "";
}

function timeAgo(ts: number): string {
  if (!ts) return "";
  const diff = (Date.now() / 1000) - ts;
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

export function TrustBanner({ filePath }: TrustBannerProps) {
  const [data, setData] = useState<ConfidenceData | null>(null);
  const [feedback, setFeedback] = useState<FeedbackData | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [showSignals, setShowSignals] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null);
  const openTab = useWorkspaceStore((s) => s.openTab);

  useEffect(() => {
    if (!filePath) return;
    let cancelled = false;
    const base = getApiBase();
    // Fetch confidence and feedback in parallel
    Promise.all([
      fetch(`${base}/api/wiki/confidence/${encodeURIComponent(filePath)}`).then((r) => r.ok ? r.json() : null),
      fetch(`${base}/api/wiki/feedback/${encodeURIComponent(filePath)}`).then((r) => r.ok ? r.json() : null),
    ]).then(([conf, fb]) => {
      if (cancelled) return;
      if (conf && typeof conf.score === "number") setData(conf);
      if (fb) setFeedback(fb);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [filePath]);

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
        setFeedback(result.feedback);
        // Refresh confidence score (it may have changed)
        const confRes = await fetch(`${base}/api/wiki/confidence/${encodeURIComponent(filePath)}`);
        if (confRes.ok) {
          const conf = await confRes.json();
          if (conf && typeof conf.score === "number") setData(conf);
        }
      }
    } catch {}
    setFeedbackLoading(false);
  }, [filePath]);

  // Close popover on click outside
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

  if (!data) return null;

  const tierColor =
    data.tier === "high"
      ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50"
      : data.tier === "medium"
      ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 hover:bg-yellow-200 dark:hover:bg-yellow-900/50"
      : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700";

  const dotColor =
    data.tier === "high" ? "bg-green-500" : data.tier === "medium" ? "bg-yellow-500" : "bg-gray-400";

  return (
    <div className="border-b text-xs space-y-0">
      {/* Row 1: Confidence pill + citation count */}
      <div ref={pillRef} className="flex items-center gap-2 px-4 py-1 relative">
        <span
          onClick={() => setShowSignals((v) => !v)}
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium cursor-pointer select-none transition-colors ${tierColor}`}
        >
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} />
          신뢰도 {data.score}
          {data.tier === "medium" && " — 검증 필요"}
          {data.tier === "low" && " — 최신 정보가 아닐 수 있습니다"}
        </span>

        {data.citation_count > 0 && (
          <span className="inline-flex items-center gap-1 text-muted-foreground" title="AI 답변에서 이 문서가 소스로 인용된 횟수">
            <MessageSquareQuote className="h-3 w-3" />
            AI 답변에서 {data.citation_count}회 인용
          </span>
        )}

        {/* Signal detail popover */}
        {showSignals && (
          <div className="absolute left-4 top-full mt-1 z-50 bg-popover border rounded-lg shadow-lg p-3 w-72 text-xs">
            <div className="font-semibold mb-2 text-foreground">신뢰도 점수 상세</div>
            <div className="text-[11px] text-muted-foreground mb-2">
              5개 시그널의 가중 합산으로 계산됩니다.
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
                      <span
                        className={`font-mono font-medium ${
                          val >= 70
                            ? "text-green-600 dark:text-green-400"
                            : val >= 40
                            ? "text-yellow-600 dark:text-yellow-400"
                            : "text-gray-500"
                        }`}
                      >
                        {Math.round(val)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            val >= 70 ? "bg-green-500" : val >= 40 ? "bg-yellow-500" : "bg-gray-400"
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
              <div className="mt-2 pt-2 border-t text-muted-foreground">
                AI 답변에서 {data.citation_count}회 인용됨
              </div>
            )}
            <div className="mt-2 pt-2 border-t text-[10px] text-muted-foreground">
              클릭하여 닫기
            </div>
          </div>
        )}
      </div>

      {/* Row 2: Stale warning banner */}
      {data.stale && (
        <div className="flex items-center gap-1.5 px-4 py-1.5 bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          <span>{data.stale_months}개월 이상 수정되지 않았습니다 — 최신 정보가 아닐 수 있습니다</span>
        </div>
      )}

      {/* Row 3: Newer alternatives */}
      {data.newer_alternatives && data.newer_alternatives.length > 0 && (
        <div className="px-4 py-1.5 bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-300">
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles className="h-3 w-3 shrink-0" />
            <span>이 주제의 최신 문서:</span>
          </div>
          <div className="space-y-0.5 pl-4">
            {data.newer_alternatives.map((alt) => (
              <div key={alt.path} className="flex items-center gap-1.5">
                <span
                  className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${
                    alt.confidence_tier === "high"
                      ? "bg-green-500"
                      : alt.confidence_tier === "medium"
                      ? "bg-yellow-500"
                      : "bg-gray-400"
                  }`}
                />
                <button
                  onClick={() => openTab(alt.path)}
                  className="text-blue-600 dark:text-blue-400 hover:underline truncate max-w-[200px]"
                >
                  {alt.title}
                </button>
                <span className="text-[10px] text-blue-500/70">신뢰도 {alt.confidence_score}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Row 4: User feedback */}
      <div className="flex items-center gap-2 px-4 py-1.5 border-t">
        <button
          disabled={feedbackLoading}
          onClick={() => submitFeedback("verified")}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/40 transition-colors disabled:opacity-50"
          title="이 문서의 내용이 정확하다고 확인합니다"
        >
          <CheckCircle2 className="h-3 w-3" />
          확인했음
        </button>
        <button
          disabled={feedbackLoading}
          onClick={() => submitFeedback("needs_update")}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-orange-700 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 hover:bg-orange-100 dark:hover:bg-orange-900/40 transition-colors disabled:opacity-50"
          title="이 문서의 내용을 업데이트해야 합니다"
        >
          <AlertCircle className="h-3 w-3" />
          수정 필요
        </button>

        {feedback && (feedback.verified_count > 0 || feedback.needs_update_count > 0) && (
          <span className="text-muted-foreground ml-1">
            {feedback.verified_count > 0 && `확인 ${feedback.verified_count}회`}
            {feedback.verified_count > 0 && feedback.needs_update_count > 0 && ", "}
            {feedback.needs_update_count > 0 && `수정 요청 ${feedback.needs_update_count}회`}
            {feedback.last_verified_by && (
              <span className="ml-1">
                (마지막 확인: {feedback.last_verified_by}, {timeAgo(feedback.last_verified_at)})
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}
