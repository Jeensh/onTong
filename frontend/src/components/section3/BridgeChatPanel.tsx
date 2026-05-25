"use client";

/**
 * 온톨로지 브릿지 — chat UI.
 *
 * Rich assistant message:
 * - 진행 중: phase pulse + 현재 step 명시
 * - 완료: RichResultCard (graph + 테이블 + 트리 + 코드)
 * - 다음 질문 chip
 *
 * UI 특징:
 * - 좌측 chat history (좁은 영역)
 * - 우측 — 사용자가 마지막 turn 펼치면 그 turn 의 full trace + result 표시
 */

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, MessageSquare, Sparkles, Lightbulb, User, Bot, Trash2, AlertTriangle, ArrowRight } from "lucide-react";
import { chat, getStats, termSearch, type StreamEvent, type AgentFinalPayload } from "@/lib/section3/api";
import { StreamTimeline } from "./rich/StreamTimeline";
import { RichResultCard } from "./rich/RichResultCard";

interface ChatTurn {
  id: number;
  role: "user" | "assistant";
  content: string;
  events?: StreamEvent[];
  finalPayload?: AgentFinalPayload;
  followups?: string[];
  intent?: string;
  needsMoreInfo?: boolean;
}

/** 도메인 어휘 0건의 generic 안내 — 어떤 ontology 든 적용 가능한 패턴. */
const GENERIC_PATTERNS = [
  { label: "용어 검색", template: "ontology 에 등록된 용어 중 ___ 비슷한 것 찾아줘" },
  { label: "method 영향 분석", template: "___ method 를 바꾸면 무엇이 영향받아?" },
  { label: "기준값 영향 분석", template: "기준값 ___ 을(를) 바꾸면 어디가 영향받아?" },
  { label: "Step 시뮬", template: "Step ___ 의 테스트 케이스를 만들어줘" },
  { label: "위치 찾기", template: "___ 은(는) 어디서 계산되나요?" },
];

export function BridgeChatPanel() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [activeEvents, setActiveEvents] = useState<StreamEvent[]>([]);
  const [expandedTurn, setExpandedTurn] = useState<number | null>(null);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);

  useEffect(() => {
    // modeling.graph_stats 로 노드 카운트 동적 가져옴
    getStats().then((s) => setStats(s.nodes)).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, activeEvents]);

  const submit = async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text || running) return;
    if (!override) setInput("");
    setRunning(true);
    setActiveEvents([]);

    const userId = ++idRef.current;
    const newTurns = [...turns, { id: userId, role: "user" as const, content: text }];
    setTurns(newTurns);

    abortRef.current = new AbortController();
    const collected: StreamEvent[] = [];
    let finalSummary = "";
    let finalPayload: AgentFinalPayload | undefined;
    let followups: string[] = [];
    let intent: string | undefined;
    let needsMoreInfo = false;

    try {
      await chat(
        {
          message: text,
          history: newTurns.slice(0, -1).map((t) => ({ role: t.role, content: t.content })),
        },
        (ev) => {
          collected.push(ev);
          setActiveEvents([...collected]);
          if (ev.type === "intent_classification") {
            followups = ev.payload.suggested_followups ?? [];
            intent = ev.payload.modeling_intent;
          }
          if (ev.type === "final") {
            finalSummary = ev.payload.summary;
            finalPayload = ev.payload as AgentFinalPayload;
          }
          if (ev.type === "error") finalSummary = "⚠ " + ev.payload.message;
          if (ev.type === "need_more_info") {
            finalSummary = "ℹ " + ev.payload.missing_info.reason;
            needsMoreInfo = true;
          }
        },
        abortRef.current.signal,
      );
    } catch (e) {
      finalSummary = `요청 실패: ${e instanceof Error ? e.message : String(e)}`;
    }

    const assistantId = ++idRef.current;
    setTurns((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: finalSummary || "(응답 없음)",
        events: collected,
        finalPayload,
        followups,
        intent,
        needsMoreInfo,
      },
    ]);
    setExpandedTurn(assistantId);
    setActiveEvents([]);
    setRunning(false);
  };

  const reset = () => {
    setTurns([]);
    setActiveEvents([]);
    setExpandedTurn(null);
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-background to-muted/20">
      {/* ── Deprecation Banner ────────────────────────── */}
      <DeprecationBanner />

      {/* ── Header ────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary to-primary/60 text-primary-foreground flex items-center justify-center">
              <Sparkles size={14} />
            </div>
            온톨로지 브릿지 <span className="text-[10px] text-muted-foreground font-normal">agent</span>
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5 ml-9">
            자연어 → LLM 의도 분석 → modeling API → 결과 시각화
          </p>
        </div>
        {turns.length > 0 && (
          <button
            onClick={reset}
            className="text-[11px] inline-flex items-center gap-1 text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted"
          >
            <Trash2 size={12} /> 새 대화
          </button>
        )}
      </div>

      {/* ── Body ─────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-5">
        {turns.length === 0 && <EmptyState onPick={submit} stats={stats} />}

        {turns.map((t) => (
          <TurnView
            key={t.id}
            turn={t}
            expanded={expandedTurn === t.id}
            onToggleExpand={() => setExpandedTurn(expandedTurn === t.id ? null : t.id)}
            onFollowup={(q) => submit(q)}
            running={running}
          />
        ))}

        {activeEvents.length > 0 && <ActiveStreamCard events={activeEvents} />}
      </div>

      {/* ── Input ────────────────────────────────────── */}
      <div className="border-t border-border bg-card/80 backdrop-blur-sm p-3">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <div className="flex-1 relative">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
              disabled={running}
              placeholder="자연어로 ontology 에 물어보세요..."
              className="w-full rounded-xl border border-border bg-background pl-4 pr-10 py-2.5 text-sm focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all"
            />
            <Sparkles size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          </div>
          <button
            onClick={() => submit()}
            disabled={running || !input.trim()}
            className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-40 transition-all shadow-sm"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {running ? "처리 중" : "전송"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── deprecation banner ─────────────────────────────

function DeprecationBanner() {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800 px-4 py-2.5">
      <div className="flex items-start gap-2 max-w-5xl mx-auto">
        <AlertTriangle size={16} className="text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 text-[12px] text-amber-800 dark:text-amber-200">
          <div className="font-semibold mb-0.5">
            v1 chat 은 더 이상 권장되지 않음 (2026-05-18 deprecated · Phase 1~6 완료)
          </div>
          <div className="text-[11px] opacity-90">
            새로운 멀티턴 chat 으로 이동:{" "}
            <a
              href="/?view=multiturn"
              className="inline-flex items-center gap-1 underline font-medium hover:text-amber-600 dark:hover:text-amber-300"
            >
              multiturn chat 으로 가기 <ArrowRight size={12} />
            </a>
            {" · "}
            영향도 검토 + 시뮬레이션 + Provenance 모두 지원.
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-[10px] text-amber-700 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-100 px-2 py-0.5 rounded hover:bg-amber-100 dark:hover:bg-amber-900/30"
          title="이 세션에서만 숨기기"
        >
          닫기
        </button>
      </div>
    </div>
  );
}

// ─── empty state ────────────────────────────────────

function EmptyState({ onPick, stats }: { onPick: (q: string) => void; stats: Record<string, number> | null }) {
  // 동적 카운트 — modeling.graph_stats 응답 그대로 (하드코딩 0건)
  const statsLine = stats
    ? Object.entries(stats)
        .filter(([, c]) => c > 0)
        .map(([k, c]) => `${c} ${k}`)
        .join(" · ")
    : "loading...";

  return (
    <div className="max-w-2xl mx-auto py-12 text-center">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center mb-4">
        <MessageSquare size={28} className="text-primary" />
      </div>
      <h3 className="text-lg font-semibold mb-2">무엇을 도와드릴까요?</h3>
      <p className="text-sm text-muted-foreground mb-1">
        ontology 에 자연어로 질문하세요.
      </p>
      <p className="text-[11px] text-muted-foreground mb-6 font-mono">
        현재 등록: <b>{statsLine}</b>
      </p>
      <div className="text-[11px] text-muted-foreground mb-2">💡 패턴 예시 (밑줄 자리에 원하는 용어/식별자 입력)</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-xl mx-auto">
        {GENERIC_PATTERNS.map((p, i) => (
          <button
            key={i}
            onClick={() => onPick(p.template)}
            className="text-left text-[12px] rounded-lg border border-border bg-card hover:border-primary/40 hover:bg-muted/40 p-3 transition-all flex items-start gap-2"
          >
            <Lightbulb size={14} className="text-primary mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-[10px] font-semibold text-primary">{p.label}</div>
              <div className="text-[11px] text-foreground/80 mt-0.5">{p.template}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── turn view ──────────────────────────────────────

function TurnView({ turn, expanded, onToggleExpand, onFollowup, running }: {
  turn: ChatTurn;
  expanded: boolean;
  onToggleExpand: () => void;
  onFollowup: (q: string) => void;
  running: boolean;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end gap-2 items-start">
        <div className="max-w-[80%] bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-sm">
          <div className="text-sm">{turn.content}</div>
        </div>
        <div className="w-7 h-7 rounded-full bg-primary/15 text-primary flex items-center justify-center flex-shrink-0">
          <User size={14} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-2 items-start">
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-primary/60 text-primary-foreground flex items-center justify-center flex-shrink-0">
        <Bot size={14} />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {/* assistant summary */}
        <div className="rounded-2xl rounded-tl-sm bg-muted px-4 py-2.5 max-w-[90%] inline-block shadow-sm">
          <div className="flex items-center gap-2 flex-wrap">
            {turn.intent && (
              <span className="text-[9px] uppercase tracking-wide font-bold px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 border border-violet-300">
                {turn.intent}
              </span>
            )}
            <button
              onClick={onToggleExpand}
              className="text-[10px] text-primary hover:underline"
            >
              {expanded ? "상세 접기" : "상세 보기"}
            </button>
          </div>
          <div className="text-sm mt-1">{turn.content}</div>
        </div>

        {/* rich result card — 펼침 */}
        {expanded && turn.finalPayload && (
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <RichResultCard result={turn.finalPayload} />
          </div>
        )}

        {/* timeline — 펼침 시 */}
        {expanded && turn.events && turn.events.length > 0 && (
          <details className="rounded-xl border border-border bg-card p-3">
            <summary className="cursor-pointer text-[11px] font-semibold text-muted-foreground hover:text-foreground">
              ▶ 실행 timeline ({turn.events.length} steps)
            </summary>
            <div className="mt-3">
              <StreamTimeline events={turn.events} />
            </div>
          </details>
        )}

        {/* followups */}
        {turn.followups && turn.followups.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1">
            <span className="text-[10px] text-muted-foreground self-center">💡</span>
            {turn.followups.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowup(q)}
                disabled={running}
                className="text-[11px] px-3 py-1 rounded-full border border-primary/30 bg-primary/5 hover:bg-primary/15 hover:border-primary/50 text-primary disabled:opacity-50 transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── active streaming card ──────────────────────────

const PHASE_LABEL: Record<string, string> = {
  thinking: "사고 중",
  intent_classification: "의도 분석",
  modeling_call: "modeling API 호출",
  modeling_result: "응답 수신",
  layer_scan: "Layer 스캔",
  code_gen: "Python 합성",
  sandbox_run: "Sandbox 실행",
  sandbox_result: "결과 수집",
  final: "완료",
  error: "오류",
  need_more_info: "추가 정보 필요",
};

function ActiveStreamCard({ events }: { events: StreamEvent[] }) {
  const last = events[events.length - 1];
  const phase = last?.type ? PHASE_LABEL[last.type] ?? last.type : "—";
  return (
    <div className="flex gap-2 items-start">
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-primary/60 text-primary-foreground flex items-center justify-center flex-shrink-0 animate-pulse">
        <Bot size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="rounded-2xl rounded-tl-sm bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border border-primary/20 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-[12px] mb-3">
            <Loader2 size={14} className="animate-spin text-primary" />
            <span className="font-bold text-primary">처리 중</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-primary/80 font-medium">{phase}</span>
            <span className="inline-flex gap-0.5 ml-1">
              <span className="w-1 h-1 rounded-full bg-primary section3-typing-dot" style={{ animationDelay: "0s" }} />
              <span className="w-1 h-1 rounded-full bg-primary section3-typing-dot" style={{ animationDelay: "0.2s" }} />
              <span className="w-1 h-1 rounded-full bg-primary section3-typing-dot" style={{ animationDelay: "0.4s" }} />
            </span>
            <span className="ml-auto text-[10px] text-muted-foreground">
              {events.length}개 단계 완료
            </span>
          </div>
          <StreamTimeline events={events} active />
        </div>
      </div>
    </div>
  );
}
