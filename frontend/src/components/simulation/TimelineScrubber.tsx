"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronFirst,
  ChevronLast,
  Clock,
  Pause,
  Play,
  Rewind,
} from "lucide-react";
import type { CaseDoneEvent } from "@/lib/simulation/useAgent2Stream";
import { JsonTable } from "./JsonTable";

type Case = CaseDoneEvent["data"];

interface Props {
  /** 샌드박스 SSE 로 누적된 케이스 array. */
  cases: Case[];
}

const PLAY_INTERVAL_MS = 60; // 케이스당 60ms — 100건 기준 6초

/**
 * Time-travel scrubber — 1000건 케이스를 영상처럼 스크럽.
 *
 * 슬라이더 = "처음 K건까지만 본 시점". 각 위치에서:
 *   - 그 시점까지 누적 통계 (matched / failed / by_type / avg_elapsed)
 *   - 마지막 케이스 1건의 입력/결과 미리보기
 *
 * 자동재생: 60ms 간격으로 cursor++ — 결과 시계열을 영상처럼 시각화.
 */
export function TimelineScrubber({ cases }: Props) {
  const [cursor, setCursor] = useState(cases.length > 0 ? cases.length - 1 : 0);
  const [playing, setPlaying] = useState(false);
  const playTimer = useRef<number | null>(null);

  // 새로 케이스가 도착하면 cursor 를 끝으로 이동 (실행 진행 중에는 자동으로 끝까지 따라감)
  const prevLen = useRef(cases.length);
  useEffect(() => {
    if (cases.length > prevLen.current) {
      setCursor(cases.length - 1);
    }
    prevLen.current = cases.length;
  }, [cases.length]);

  // 자동 재생 타이머
  useEffect(() => {
    if (!playing) {
      if (playTimer.current !== null) {
        window.clearInterval(playTimer.current);
        playTimer.current = null;
      }
      return;
    }
    playTimer.current = window.setInterval(() => {
      setCursor((prev) => {
        if (prev >= cases.length - 1) {
          setPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, PLAY_INTERVAL_MS);
    return () => {
      if (playTimer.current !== null) {
        window.clearInterval(playTimer.current);
        playTimer.current = null;
      }
    };
  }, [playing, cases.length]);

  const stats = useMemo(() => {
    const slice = cases.slice(0, cursor + 1);
    const total = slice.length;
    const matched = slice.filter((c) => c.matches_expectation).length;
    const failed = total - matched;
    const byType: Record<string, { matched: number; failed: number; total: number }> = {};
    for (const c of slice) {
      if (!byType[c.case_type]) byType[c.case_type] = { matched: 0, failed: 0, total: 0 };
      byType[c.case_type].total++;
      if (c.matches_expectation) byType[c.case_type].matched++;
      else byType[c.case_type].failed++;
    }
    const avgElapsed =
      total > 0 ? slice.reduce((a, c) => a + (c.elapsed_ms ?? 0), 0) / total : 0;
    return { total, matched, failed, byType, avgElapsed };
  }, [cases, cursor]);

  if (cases.length === 0) return null;

  const current = cases[cursor];
  const matchPct = stats.total > 0 ? (stats.matched / stats.total) * 100 : 0;
  const failPct = 100 - matchPct;

  const playBtn = playing ? (
    <button
      onClick={() => setPlaying(false)}
      className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-2.5 py-1 text-xs font-medium hover:bg-primary/90"
    >
      <Pause size={12} /> 일시정지
    </button>
  ) : (
    <button
      onClick={() => {
        if (cursor >= cases.length - 1) setCursor(0); // 끝이면 처음부터
        setPlaying(true);
      }}
      className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-2.5 py-1 text-xs font-medium hover:bg-primary/90"
      disabled={cases.length === 0}
    >
      <Play size={12} /> 재생
    </button>
  );

  const TYPE_TONE: Record<string, string> = {
    normal: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
    boundary: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
    error: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
    performance: "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30",
  };

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <Clock size={14} className="text-primary" />
          Time-travel — 케이스 스크럽
          <span className="text-[10px] text-muted-foreground font-normal ml-1">
            슬라이더로 시점 이동 + 자동 재생
          </span>
        </h4>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setCursor(0)}
            className="inline-flex items-center rounded border border-border px-1.5 py-1 text-xs hover:bg-muted"
            title="처음으로"
          >
            <ChevronFirst size={12} />
          </button>
          <button
            onClick={() => setCursor(Math.max(0, cursor - 5))}
            className="inline-flex items-center rounded border border-border px-1.5 py-1 text-xs hover:bg-muted"
            title="-5"
          >
            <Rewind size={12} />
          </button>
          {playBtn}
          <button
            onClick={() => setCursor(cases.length - 1)}
            className="inline-flex items-center rounded border border-border px-1.5 py-1 text-xs hover:bg-muted"
            title="끝으로"
          >
            <ChevronLast size={12} />
          </button>
        </div>
      </div>

      {/* 슬라이더 + 진행 표시 */}
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between text-[11px]">
          <span className="text-muted-foreground">
            시점:{" "}
            <span className="font-mono text-foreground">
              {cursor + 1}/{cases.length}
            </span>
          </span>
          <span className="text-muted-foreground">
            평균 실행: <span className="font-mono text-foreground">{stats.avgElapsed.toFixed(1)}ms</span>
          </span>
        </div>

        {/* 진행 바 (matched/failed 분포 시각화) */}
        <div className="relative h-2 rounded-full overflow-hidden bg-muted">
          <div
            className="absolute inset-y-0 left-0 bg-emerald-500/60"
            style={{ width: `${matchPct}%` }}
          />
          <div
            className="absolute inset-y-0 right-0 bg-red-500/60"
            style={{ width: `${failPct}%`, left: "auto" }}
          />
        </div>

        <input
          type="range"
          min={0}
          max={Math.max(0, cases.length - 1)}
          step={1}
          value={cursor}
          onChange={(e) => setCursor(parseInt(e.target.value, 10))}
          className="w-full accent-primary"
        />
      </div>

      {/* 누적 통계 */}
      <div className="grid grid-cols-3 gap-2">
        <Stat label="누적 케이스" value={String(stats.total)} tone="text-foreground" />
        <Stat
          label="기대 일치"
          value={`${stats.matched} (${matchPct.toFixed(1)}%)`}
          tone="text-emerald-700 dark:text-emerald-300"
        />
        <Stat
          label="기대 불일치"
          value={`${stats.failed} (${failPct.toFixed(1)}%)`}
          tone="text-red-700 dark:text-red-300"
        />
      </div>

      {/* 케이스 유형 별 진행 */}
      {Object.keys(stats.byType).length > 0 && (
        <div className="flex flex-wrap gap-1.5 text-[10px]">
          {Object.entries(stats.byType).map(([type, t]) => (
            <span
              key={type}
              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono ${
                TYPE_TONE[type] ?? "border-border bg-muted/30 text-muted-foreground"
              }`}
            >
              <span>{type}</span>
              <span className="font-bold">
                {t.matched}/{t.total}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* 현재 cursor 케이스 미리보기 */}
      {current && (
        <div className="rounded border border-border bg-card p-2 space-y-1.5">
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`font-mono ${
                current.matches_expectation
                  ? "text-emerald-700 dark:text-emerald-300"
                  : "text-red-700 dark:text-red-300"
              }`}
            >
              {current.case_id}
            </span>
            <span
              className={`text-[10px] rounded px-1.5 py-0.5 border ${
                TYPE_TONE[current.case_type] ??
                "border-border bg-muted/30 text-muted-foreground"
              }`}
            >
              {current.case_type}
            </span>
            <span className="text-muted-foreground flex-1 truncate">
              {current.description || "(설명 없음)"}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {current.elapsed_ms ?? 0}ms
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 mt-1">
            <JsonTable data={current.input_data} caption="입력 (input)" maxRows={8} maxValueLen={80} />
            <JsonTable
              data={current.actual_output}
              caption={current.matches_expectation ? "결과 (기대 일치)" : "결과 (기대 불일치)"}
              maxRows={10}
              maxValueLen={80}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded border border-border bg-card p-2">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`text-base font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}
