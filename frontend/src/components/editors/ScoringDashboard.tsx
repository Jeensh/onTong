"use client";

import { useEffect, useState } from "react";
import { Loader2, Info } from "lucide-react";

interface WeightMap {
  [key: string]: string;
}

interface TierMap {
  [key: string]: string;
}

interface ScoringSection {
  description: string;
  formula?: string;
  weights?: WeightMap;
  tiers?: TierMap;
  stale_threshold?: string;
  composite_formula?: string;
  min_similarity?: number;
  auto_suggest?: string;
  ui_default_visible?: number;
  effect?: string;
  similarity_threshold?: number;
}

type ScoringConfig = Record<string, ScoringSection>;

const SECTION_META: Record<string, { title: string; icon: string; color: string }> = {
  confidence: { title: "문서 신뢰도 점수", icon: "🎯", color: "green" },
  related_documents: { title: "관련 문서 발견", icon: "🔗", color: "purple" },
  rag_boost: { title: "AI 검색 순위 보정", icon: "🤖", color: "blue" },
  conflict_detection: { title: "유사 문서 감지", icon: "⚡", color: "amber" },
};

export function ScoringDashboard() {
  const [config, setConfig] = useState<ScoringConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const isLocal = typeof window !== "undefined" && window.location.hostname === "localhost";
    const base = isLocal ? "http://localhost:8001" : "";
    fetch(`${base}/api/wiki/scoring-config`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        <span className="text-sm">스코어링 설정 로딩 중...</span>
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <p className="text-sm">설정을 불러올 수 없습니다: {error}</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-lg font-bold">신뢰도 설정</h1>
          <p className="text-sm text-muted-foreground mt-1">
            문서 신뢰도 점수, 관련 문서 발견, AI 검색 보정, 유사 문서 감지에 사용되는 모든 가중치와 임계값입니다.
            각 파라미터를 조정하여 시스템 동작을 튜닝할 수 있습니다.
          </p>
        </div>

        {/* Info banner */}
        <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-sm">
          <Info className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
          <div className="text-blue-700 dark:text-blue-300">
            <div className="font-medium">점수는 어떻게 활용되나요?</div>
            <ul className="mt-1 space-y-0.5 text-xs list-disc list-inside">
              <li><strong>신뢰도 점수</strong>: 문서를 열 때 상단 pill로 표시. 높을수록 믿을 수 있는 문서</li>
              <li><strong>관련 문서</strong>: 편집 시 사이드바에 "참고할 만한 문서" 표시. 중복 작성 예방</li>
              <li><strong>AI 검색 보정</strong>: AI 답변에서 신뢰도 높은 문서를 우선 인용</li>
              <li><strong>유사 문서 감지</strong>: 임베딩 유사도 기반으로 중복/충돌 후보 탐지</li>
            </ul>
          </div>
        </div>

        {/* Sections */}
        {Object.entries(config).map(([sectionKey, section]) => {
          const meta = SECTION_META[sectionKey] || { title: sectionKey, icon: "📊", color: "gray" };
          return (
            <div key={sectionKey} className="border rounded-lg overflow-hidden">
              {/* Section header */}
              <div className="px-4 py-3 bg-muted/50 border-b">
                <div className="flex items-center gap-2">
                  <span className="text-base">{meta.icon}</span>
                  <h2 className="font-semibold text-sm">{meta.title}</h2>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{section.description}</p>
              </div>

              <div className="p-4 space-y-3">
                {/* Formula */}
                {section.formula && (
                  <div>
                    <div className="text-[11px] font-medium text-muted-foreground uppercase mb-1">공식</div>
                    <code className="text-xs bg-muted px-2 py-1 rounded block">{section.formula}</code>
                  </div>
                )}

                {section.composite_formula && (
                  <div>
                    <div className="text-[11px] font-medium text-muted-foreground uppercase mb-1">복합 정렬 공식</div>
                    <code className="text-xs bg-muted px-2 py-1 rounded block">{section.composite_formula}</code>
                  </div>
                )}

                {/* Weights table */}
                {section.weights && (
                  <div>
                    <div className="text-[11px] font-medium text-muted-foreground uppercase mb-1">가중치</div>
                    <div className="space-y-1">
                      {Object.entries(section.weights).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-2 text-xs">
                          <div className="w-24 font-medium text-foreground capitalize">{k.replace(/_/g, " ")}</div>
                          <div className="flex-1 text-muted-foreground">{v}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tiers */}
                {section.tiers && (
                  <div>
                    <div className="text-[11px] font-medium text-muted-foreground uppercase mb-1">등급 기준</div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-green-500" />
                        높음: {section.tiers.high}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-yellow-500" />
                        보통: {section.tiers.medium}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-gray-400" />
                        낮음: {section.tiers.low}
                      </span>
                    </div>
                  </div>
                )}

                {/* Stale threshold */}
                {section.stale_threshold && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium">오래된 문서 기준:</span>
                    <span className="text-muted-foreground">{section.stale_threshold} 미수정</span>
                  </div>
                )}

                {/* Related-specific fields */}
                {section.min_similarity !== undefined && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium">최소 유사도:</span>
                    <span className="font-mono">{section.min_similarity}</span>
                    <span className="text-muted-foreground">— 이 이하는 표시하지 않음</span>
                  </div>
                )}

                {section.auto_suggest && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium">자동 제안:</span>
                    <span className="text-muted-foreground">{section.auto_suggest}</span>
                  </div>
                )}

                {section.ui_default_visible !== undefined && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium">기본 표시 개수:</span>
                    <span className="font-mono">{section.ui_default_visible}</span>
                    <span className="text-muted-foreground">건 (나머지는 "더 보기")</span>
                  </div>
                )}

                {/* RAG boost */}
                {section.effect && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium">효과:</span>
                    <span className="text-muted-foreground">{section.effect}</span>
                  </div>
                )}

                {/* Conflict threshold */}
                {section.similarity_threshold !== undefined && !section.weights && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-medium">유사도 임계값:</span>
                    <span className="font-mono">{section.similarity_threshold}</span>
                    <span className="text-muted-foreground">— 이 이상이면 충돌 후보로 표시</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Footer */}
        <div className="text-[11px] text-muted-foreground text-center pb-4">
          설정 변경은 <code className="bg-muted px-1 rounded">backend/application/trust/scoring_config.py</code>에서 수정 가능합니다.
          변경 후 서버 재시작 없이 즉시 반영됩니다.
        </div>
      </div>
    </div>
  );
}
