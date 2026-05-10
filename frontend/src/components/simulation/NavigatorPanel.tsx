"use client";

import { useState } from "react";
import {
  Compass,
  ExternalLink,
  Loader2,
  Search,
  Sparkles,
  Zap,
} from "lucide-react";
import { runAgent3, type Agent3Result } from "@/lib/simulation/agentApi";

interface Props {
  onHandoffToSandbox?: (stepId: string) => void;
}

const QUICK_QUERIES = [
  "단중상한이 어디서 결정돼?",
  "누적 실수율 계산 위치",
  "Slab 매수 산정 로직",
  "분할수 범위 계산",
  "Slab 두께 결정",
  "PRODUCT_TYPE_CD 사용처",
  "주문 정합성 검증 (DG001~005)",
];

export function NavigatorPanel({ onHandoffToSandbox }: Props) {
  const [query, setQuery] = useState("단중상한이 어디서 결정돼?");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent3Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  const submit = async (q?: string) => {
    const text = (q ?? query).trim();
    if (!text) return;
    if (q) setQuery(q);
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveIdx(0);
    try {
      const r = await runAgent3({
        natural_language_query: text,
        include_preview: true,
        preview_lines: 20,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const activeLocation = result?.source_locations?.[activeIdx];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Compass size={20} className="text-primary" />
          코드 내비게이터
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          비즈니스 용어를 자연어로 입력하면 ontology + slab-design 키워드 매핑으로 소스 코드 위치를 찾고 미리보기를 제공합니다.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[400px_1fr]">
        <section className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">검색어 (자연어)</label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm font-mono"
              placeholder="예: 단중상한이 어디서 결정돼?"
            />
          </div>

          <div>
            <div className="text-xs font-medium text-foreground mb-1.5 flex items-center gap-1.5">
              <Sparkles size={12} className="text-amber-500" />
              빠른 질의
            </div>
            <div className="flex flex-wrap gap-1">
              {QUICK_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => submit(q)}
                  className="rounded border border-border bg-muted/40 px-2 py-1 text-[11px] text-foreground/80 hover:bg-muted"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          <button
            disabled={loading}
            onClick={() => submit()}
            className="w-full inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                검색 중
              </>
            ) : (
              <>
                <Search size={14} />
                위치 검색
              </>
            )}
          </button>

          {error && (
            <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          {result && result.extracted_keywords?.length > 0 && (
            <div>
              <div className="text-xs font-medium text-foreground mb-1.5">매칭 키워드</div>
              <div className="flex flex-wrap gap-1">
                {result.extracted_keywords.map((k, i) => (
                  <span key={i} className="rounded bg-primary/10 text-primary px-2 py-0.5 text-[11px] font-mono">
                    {k}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="space-y-4">
          {!result && !loading && (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              <Compass size={28} className="mx-auto mb-2 opacity-30" />
              검색어를 입력하면 매칭 코드 위치 + 미리보기 + 시뮬레이션 핸드오프가 표시됩니다.
            </div>
          )}

          {loading && (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
              <Loader2 size={28} className="mx-auto mb-2 animate-spin text-primary" />
              ontology + 키워드 매핑 검색 중...
            </div>
          )}

          {result && result.source_locations.length === 0 && !loading && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-6 text-center text-sm text-amber-700 dark:text-amber-300">
              매칭된 위치가 없습니다. 다른 키워드를 시도해보세요.
            </div>
          )}

          {result && result.source_locations.length > 0 && (
            <>
              <div className="rounded-lg border border-border bg-card p-4 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-foreground">{result.summary}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {result.source_locations.length}개 위치
                    {result.matched_terms.length > 0 && ` · ${result.matched_terms.length}개 용어 매칭`}
                    <span className="ml-1 text-muted-foreground/60">· {result.extraction_method}</span>
                  </div>
                </div>
                {result.handoff_step_id && onHandoffToSandbox && (
                  <button
                    onClick={() => onHandoffToSandbox(result.handoff_step_id!)}
                    className="shrink-0 inline-flex items-center gap-1.5 rounded-md bg-purple-600 px-3 py-2 text-xs font-medium text-white hover:bg-purple-700"
                    title={`샌드박스 패널로 이동하여 step "${result.handoff_step_id}" 실행`}
                  >
                    <Zap size={12} />
                    이 step 시뮬
                  </button>
                )}
              </div>

              <div className="rounded-lg border border-border bg-card overflow-hidden">
                <div className="border-b border-border px-3 py-1.5 flex flex-wrap gap-1 bg-muted/40">
                  {result.source_locations.map((loc, idx) => (
                    <button
                      key={idx}
                      onClick={() => setActiveIdx(idx)}
                      className={`rounded px-2 py-1 text-[11px] font-mono transition-colors ${
                        idx === activeIdx
                          ? "bg-background border border-border text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {loc.class_name ?? "(unknown)"}
                      {loc.method_name && <span className="text-muted-foreground/60">.{loc.method_name}</span>}
                    </button>
                  ))}
                </div>
                {activeLocation && (
                  <div className="p-4 space-y-3">
                    <div className="text-[11px] text-muted-foreground font-mono flex items-center gap-2">
                      <ExternalLink size={11} />
                      <span className="truncate">
                        {activeLocation.file_path?.replace(/^.*\/sample-repos\//, "sample-repos/")}
                      </span>
                      {activeLocation.line && <span>:line {activeLocation.line}</span>}
                    </div>
                    {activeLocation.preview ? (
                      <pre className="rounded bg-zinc-950 text-zinc-100 px-3 py-2 text-xs overflow-x-auto leading-relaxed font-mono">
                        <code>{activeLocation.preview}</code>
                      </pre>
                    ) : (
                      <div className="text-sm text-muted-foreground/60">미리보기 없음</div>
                    )}
                    {activeLocation.step_id && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>관련 sandbox step:</span>
                        <code className="rounded bg-purple-500/10 text-purple-700 dark:text-purple-300 px-2 py-0.5 font-mono">
                          {activeLocation.step_id}
                        </code>
                        {onHandoffToSandbox && (
                          <button
                            onClick={() => onHandoffToSandbox(activeLocation.step_id!)}
                            className="text-purple-600 dark:text-purple-300 hover:underline"
                          >
                            이 step으로 시뮬 →
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
