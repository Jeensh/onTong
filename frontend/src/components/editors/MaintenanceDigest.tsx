"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Clock,
  AlertTriangle,
  TrendingDown,
  FileText,
  Loader2,
  RefreshCw,
  Users,
  ChevronDown,
  Info,
} from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { toast } from "sonner";

interface DigestItem {
  path: string;
  title: string;
  reason: "stale" | "low_confidence" | "unresolved_conflict";
  detail: string;
  confidence_score: number;
  stale_months: number;
}

interface DigestResult {
  user: string;
  total: number;
  stale: DigestItem[];
  low_confidence: DigestItem[];
  unresolved_conflicts: DigestItem[];
}

const INITIAL_SHOW = 5;

const SECTION_CONFIG = {
  stale: {
    title: "오래된 문서",
    icon: Clock,
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-950/20",
    border: "border-amber-200 dark:border-amber-800",
    desc: "12개월 이상 수정되지 않은 문서입니다. 내용이 아직 유효한지 확인하고, 최신 정보로 업데이트하거나 폐기 처리하세요.",
    action: "문서를 열어 내용을 검토한 후 수정하거나, 더 이상 필요 없으면 상태를 'deprecated'로 변경하세요.",
  },
  low_confidence: {
    title: "신뢰도 낮은 문서",
    icon: TrendingDown,
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-950/20",
    border: "border-red-200 dark:border-red-800",
    desc: "메타데이터 부족, 오래된 내용, 또는 미설정 상태로 인해 신뢰도 점수가 40점 미만인 문서입니다.",
    action: "도메인/프로세스/태그를 채우고, 상태를 'approved'로 설정하면 신뢰도가 크게 올라갑니다.",
  },
  unresolved_conflicts: {
    title: "미해결 관련 문서",
    icon: AlertTriangle,
    color: "text-blue-600 dark:text-blue-400",
    bg: "bg-blue-50 dark:bg-blue-950/20",
    border: "border-blue-200 dark:border-blue-800",
    desc: "다른 문서와 내용이 겹치거나 충돌하는 것으로 감지되었지만 아직 처리되지 않았습니다.",
    action: "'관련 문서 관리' 대시보드에서 AI 분석을 실행하고 적절한 해결 방법을 선택하세요.",
  },
} as const;

export function MaintenanceDigest() {
  const [digest, setDigest] = useState<DigestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [userFilter, setUserFilter] = useState("");
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const openTab = useWorkspaceStore((s) => s.openTab);

  const fetchDigest = useCallback(async () => {
    setLoading(true);
    try {
      const params = userFilter ? `?user_filter=${encodeURIComponent(userFilter)}` : "";
      const res = await fetch(`/api/wiki/digest${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DigestResult = await res.json();
      setDigest(data);
    } catch (e) {
      toast.error("다이제스트 로딩 실패: " + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [userFilter]);

  useEffect(() => {
    fetchDigest();
  }, [fetchDigest]);

  const toggleExpand = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <h2 className="text-lg font-semibold">관리가 필요한 문서</h2>
            {digest && digest.total > 0 && (
              <span className="text-xs bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded-full">
                {digest.total}건
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Users className="h-3 w-3" />
              <input
                type="text"
                placeholder="작성자로 필터 (빈값 = 전체)"
                value={userFilter}
                onChange={(e) => setUserFilter(e.target.value)}
                className="w-44 h-7 rounded border bg-background px-2 text-xs"
              />
            </div>
            <button
              onClick={fetchDigest}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              새로고침
            </button>
          </div>
        </div>

        {/* Description */}
        <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 p-3 text-xs text-muted-foreground leading-relaxed flex items-start gap-2">
          <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
          <div>
            <p>
              오래되었거나 신뢰도가 낮은 문서, 미해결 관련 문서를 한눈에 확인하고 관리하는 대시보드입니다.
              각 섹션 안내를 참고하여 문서를 열고 필요한 조치를 취하세요.
            </p>
            <p className="mt-1 text-[11px]">
              작성자 필터에 이름을 입력하면 해당 사용자가 작성/수정한 문서만 표시됩니다.
            </p>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            분석 중...
          </div>
        )}

        {!loading && digest && digest.total === 0 && (
          <div className="text-center py-12 text-muted-foreground space-y-2">
            <FileText className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm font-medium">관리가 필요한 문서가 없습니다.</p>
            <p className="text-xs">모든 문서가 양호한 상태입니다. 문서가 오래되거나 신뢰도가 낮아지면 자동으로 이곳에 표시됩니다.</p>
          </div>
        )}

        {!loading && digest && digest.total > 0 && (
          <div className="space-y-6">
            {(["stale", "low_confidence", "unresolved_conflicts"] as const).map((section) => {
              const items = digest[section];
              if (items.length === 0) return null;
              const config = SECTION_CONFIG[section];
              const Icon = config.icon;
              const isExpanded = expandedSections[section];
              const visibleItems = isExpanded ? items : items.slice(0, INITIAL_SHOW);
              const hasMore = items.length > INITIAL_SHOW;

              return (
                <div key={section} className={`rounded-lg border ${config.border} ${config.bg} p-4 space-y-3`}>
                  <div className="flex items-center gap-2">
                    <Icon className={`h-4 w-4 ${config.color}`} />
                    <h3 className={`text-sm font-semibold ${config.color}`}>
                      {config.title} ({items.length}건)
                    </h3>
                  </div>

                  {/* Section description and action guidance */}
                  <div className="text-[11px] text-muted-foreground space-y-1 pl-6">
                    <p>{config.desc}</p>
                    <p className="font-medium">
                      조치 방법: {config.action}
                    </p>
                  </div>

                  <div className="space-y-2">
                    {visibleItems.map((item) => (
                      <div
                        key={`${section}-${item.path}`}
                        className="flex items-center justify-between rounded border bg-card p-3"
                      >
                        <div className="flex-1 min-w-0">
                          <button
                            onClick={() => openTab(item.path)}
                            className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline text-left"
                          >
                            <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="truncate">{item.title}</span>
                          </button>
                          <p className="text-[10px] text-muted-foreground mt-0.5 truncate" title={item.path}>
                            {item.path}
                          </p>
                        </div>
                        <div className="ml-3 text-right shrink-0">
                          <p className="text-[11px] text-muted-foreground">{item.detail}</p>
                          {item.confidence_score >= 0 && (
                            <span className={`text-[10px] font-medium ${
                              item.confidence_score >= 70 ? "text-green-600" :
                              item.confidence_score >= 40 ? "text-amber-600" :
                              "text-red-600"
                            }`}>
                              신뢰도 {item.confidence_score}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Show more / less */}
                  {hasMore && (
                    <button
                      onClick={() => toggleExpand(section)}
                      className="flex items-center gap-1 text-[11px] text-primary hover:underline pl-6"
                    >
                      <ChevronDown className={`h-3 w-3 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                      {isExpanded ? "접기" : `나머지 ${items.length - INITIAL_SHOW}건 더 보기`}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
