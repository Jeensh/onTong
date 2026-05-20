"use client";

/**
 * Phase 3 컨테이너 — multiturn chat panel.
 *
 * UX:
 * - 빈 상태: 자연어 입력 + repo_id 선택 → /start
 * - turn 1 (ambiguous stub) 즉시 표시 → 자동 /respond 호출 (Gate I real)
 * - turn 2 (Gate I real): GateTargetCard 에서 사용자 선택 → /confirm → /respond
 * - turn 3 simulate: GateBundleCard → [실행] → /respond (Gate III sim)
 * - turn 3 impact:  GateExecutedImpactCard (session done)
 * - turn 4 simulate: GateExecutedSimulationCard (session done)
 */

import { useEffect, useRef, useState } from "react";
import {
  Send, Loader2, Sparkles, Trash2, AlertCircle, GitBranch, FlaskConical,
  Target, AlertTriangle, MapPin, BookOpen, ChevronDown, History, ArrowRight,
} from "lucide-react";
import type {
  DecisionView, GateIntentClassified, GatePayload, GateTarget, SessionSummary,
} from "@/lib/section3/multiturn";
import { listSessions } from "@/lib/section3/multiturn";
import { useMultiturnSession } from "./useMultiturnSession";
import { GateTargetCard } from "./GateTargetCard";
import { GateBundleCard } from "./GateBundleCard";
import { GateExecutedSimulationCard } from "./GateExecutedSimulationCard";
import { GateExecutedImpactCard } from "./GateExecutedImpactCard";
import { GateExecutedReadOnlyCard } from "./GateExecutedReadOnlyCard";
import { IntentStage } from "./IntentStage";
import { ScopeStage } from "./ScopeStage";
import { SimulateStageHeader } from "./SimulateStageHeader";

const DEFAULT_REPO = "slab-design-real-v2";

// Phase 21a — intent 별 그룹화된 예시 (색상은 IntentStage 와 동기화)
interface IntentExample {
  q: string;
  hint?: string;
}
interface IntentCategory {
  kind: "simulate" | "impact" | "hypothesis" | "locate" | "explain";
  label: string;
  description: string;
  Icon: typeof Sparkles;
  cls: string;
  bgCls: string;
  examples: IntentExample[];
}

const INTENT_CATEGORIES: IntentCategory[] = [
  {
    kind: "simulate",
    label: "시뮬레이션",
    description: "코드를 돌려 결과 확인",
    Icon: FlaskConical,
    cls: "text-purple-700 border-purple-300",
    bgCls: "bg-purple-50",
    examples: [
      { q: "주문 검증 시뮬해줘", hint: "주문 validate 전체" },
      { q: "엣징 사양 룩업 룰 시뮬", hint: "엣징 그룹" },
    ],
  },
  {
    kind: "impact",
    label: "영향도 분석",
    description: "변경 시 어디가 영향 받는지",
    Icon: AlertTriangle,
    cls: "text-amber-700 border-amber-300",
    bgCls: "bg-amber-50",
    examples: [
      { q: "cumulativeProductivity 바꾸면 어디 영향받아?", hint: "함수 단위" },
      { q: "final_width_range 바꾸면 어떤 메서드 영향?", hint: "caller chain" },
    ],
  },
  {
    kind: "hypothesis",
    label: "가설 검증",
    description: "조건 → 결과 확인 (예/아니오)",
    Icon: Target,
    cls: "text-pink-700 border-pink-300",
    bgCls: "bg-pink-50",
    examples: [
      { q: "두께 0.1mm 이하일 때 검증 실패하나?", hint: "단일 조건" },
      { q: "주문 수량 0 이면 어떻게 처리?", hint: "edge case" },
    ],
  },
  {
    kind: "locate",
    label: "위치 찾기",
    description: "관련 코드가 어디 있는지",
    Icon: MapPin,
    cls: "text-sky-700 border-sky-300",
    bgCls: "bg-sky-50",
    examples: [
      { q: "주문 검증 룰이 어디 있어?", hint: "FQN + 파일" },
    ],
  },
  {
    kind: "explain",
    label: "설명",
    description: "코드가 무엇을 하는지",
    Icon: BookOpen,
    cls: "text-emerald-700 border-emerald-300",
    bgCls: "bg-emerald-50",
    examples: [
      { q: "SdThicknessAction 이 뭐 하는 거야?", hint: "동작 요약" },
    ],
  },
];

const INTENT_LABEL_MAP: Record<string, string> = {
  simulate: "💜 시뮬",
  impact: "💛 영향도",
  hypothesis: "💗 가설",
  locate: "📍 위치",
  explain: "💚 설명",
  ambiguous: "❓ 모호",
};

interface MultiturnChatProps {
  /** 외부에서 전달된 기존 session — 히스토리 브라우저에서 진입할 때. */
  initialSid?: string | null;
  /** 새 세션 시작 시 부모에게 알려 URL 정리. */
  onNewSession?: () => void;
  /** Dashboard 에서 고른 repo 가 새 chat 의 기본값으로 들어옴. */
  defaultRepoId?: string | null;
  /** Phase 21a — EmptyState 의 "최근 세션" 클릭 시 sid 로 진입. */
  onOpenSession?: (sid: string) => void;
}

export function MultiturnChat({
  initialSid, onNewSession, defaultRepoId, onOpenSession,
}: MultiturnChatProps = {}) {
  const { state, start, respond, confirm, reset, loadSession } = useMultiturnSession();
  const [input, setInput] = useState("");
  const [repoId, setRepoId] = useState(defaultRepoId || DEFAULT_REPO);
  const scrollRef = useRef<HTMLDivElement>(null);
  const loadedSidRef = useRef<string | null>(null);

  // 부모가 defaultRepoId 바꾸면 (dashboard 칩 클릭) 현재 EmptyState 의 repoId 도 따라감.
  // 단, 이미 active session 이 있으면 그 세션의 repo 가 유지되므로 영향 없음.
  useEffect(() => {
    if (defaultRepoId && !state.sessionId) {
      setRepoId(defaultRepoId);
    }
  }, [defaultRepoId, state.sessionId]);

  // initialSid 주입 시 1회 로드 (sid 가 바뀌면 재로드)
  useEffect(() => {
    if (initialSid && loadedSidRef.current !== initialSid) {
      loadedSidRef.current = initialSid;
      loadSession(initialSid);
    }
  }, [initialSid, loadSession]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight, behavior: "smooth",
    });
  }, [state.decisions.length, state.pending]);

  // turn 1 (ambiguous stub) → 자동으로 Gate I real 호출
  const lastDecision = state.decisions[state.decisions.length - 1];
  useEffect(() => {
    if (
      state.sessionId &&
      !state.pending &&
      state.decisions.length === 1 &&
      lastDecision?.gate_kind === "target_selected" &&
      (lastDecision.payload as { intent: string }).intent === "ambiguous" &&
      lastDecision.user_response === null
    ) {
      // first /respond — Gate I real
      respond(state.session?.user_query ?? "");
    }
  }, [
    state.sessionId, state.pending, state.decisions.length,
    state.session?.user_query, lastDecision, respond,
  ]);

  const submit = async () => {
    const text = input.trim();
    if (!text || state.pending) return;
    setInput("");
    await start(text, repoId);
  };

  const onPickExample = (q: string) => {
    setInput(q);
  };

  const onConfirmGateI = async (turn_no: number, selected_index: number) => {
    await confirm(turn_no, "confirm", { selected_index });
    // Gate II (simulate) or Gate III impact (impact) 진입
    await respond("이걸로 진행");
  };

  // Phase 21b — intent_classified confirm → target_selected (Gate I real) 호출
  const onConfirmIntent = async (turn_no: number) => {
    await confirm(turn_no, "confirm", {});
    await respond("intent 확정 — 후보 찾기");
  };

  const onProceedBundle = async () => {
    await respond("실행");
  };

  const onRetryGateI = async () => {
    // 사용자가 "다른 후보 검색" — 같은 query 로 다시 /respond 는 불가 (이미 turn 2 가 있음)
    // 새 세션 시작 안내
    alert("다른 후보를 보려면 [새 대화] 버튼으로 다시 시작하세요");
  };

  // Phase 14C — 0-cand suggestions chip 클릭 → 새 세션 시작 (1-click auto-research)
  const onSuggestionClick = async (suggestion: string) => {
    if (state.pending) return;
    const currentRepo = state.session?.repo_id ?? repoId;
    reset();
    loadedSidRef.current = null;
    onNewSession?.();
    await start(suggestion, currentRepo);
  };

  // Phase 16J — target_is_test 빨강 칩 발화 시 부모가 제공하는 retry 동선.
  // 새 세션을 같은 user_query 로 시작 — 사용자가 직접 rank-2 production 후보 선택.
  // (LLM 재분류 variance 때문에 자동 pick 보다 사용자 선택이 더 안전.)
  const onRetryWithDifferentTarget = async () => {
    const q = state.session?.user_query;
    if (!q || state.pending) return;
    const currentRepo = state.session?.repo_id ?? repoId;
    reset();
    loadedSidRef.current = null;
    onNewSession?.();
    await start(q, currentRepo);
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-background to-muted/20">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary to-primary/60 text-primary-foreground flex items-center justify-center">
              <Sparkles size={14} />
            </div>
            멀티턴 시뮬 / 영향도 agent
            <span className="text-[10px] text-muted-foreground font-normal">v2 · 3 gates</span>
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5 ml-9">
            자연어 → intent (simulate / impact) → 후보 → 번들 → 실행 / 영향도 · 모든 카드에 Provenance
          </p>
        </div>
        {state.sessionId && (
          <button
            onClick={() => {
              reset();
              setInput("");
              loadedSidRef.current = null;
              onNewSession?.();
            }}
            className="text-[11px] inline-flex items-center gap-1 text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted"
          >
            <Trash2 size={12} /> 새 대화
          </button>
        )}
      </div>

      {/* Body */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {!state.sessionId && (
          <EmptyState
            onPick={onPickExample}
            repoId={repoId}
            setRepoId={setRepoId}
            onOpenSession={onOpenSession}
          />
        )}

        {state.sessionId && state.session && (
          <SessionHeader
            session={state.session}
            nextGateKind={state.lastNextGateKind}
            currentStage={computeCurrentStage(state.decisions)}
          />
        )}

        {/* Phase 17 — 3-Stage workflow frame */}
        {state.sessionId && state.decisions.length > 0 && (
          <WorkflowFrame
            decisions={state.decisions}
            pending={state.pending}
            repoId={state.session?.repo_id ?? repoId}
            onConfirmIntent={onConfirmIntent}
            onConfirmGateI={onConfirmGateI}
            onRetryGateI={onRetryGateI}
            onProceedBundle={onProceedBundle}
            onSuggestionClick={onSuggestionClick}
            onRetryWithDifferentTarget={onRetryWithDifferentTarget}
            onEditIntent={onRetryWithDifferentTarget}
          />
        )}

        {state.pending && <PendingPulse />}
        {state.error && <ErrorBanner status={state.error.status} detail={state.error.detail} />}
      </div>

      {/* Input */}
      {!state.sessionId && (
        <div className="border-t border-border bg-card/80 backdrop-blur-sm p-3">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
              placeholder="예: 주문 검증 시뮬해줘 / cumulativeProductivity 바꾸면 영향?"
              className="flex-1 px-3 py-2 text-sm border border-border rounded bg-background focus:outline-none focus:border-primary"
              disabled={state.pending}
            />
            <button
              onClick={submit}
              disabled={state.pending || !input.trim()}
              className="inline-flex items-center gap-1 bg-primary text-primary-foreground px-3 py-2 text-sm rounded hover:bg-primary/90 disabled:opacity-50"
            >
              {state.pending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              시작
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState(p: {
  onPick: (q: string) => void;
  repoId: string;
  setRepoId: (s: string) => void;
  /** 최근 세션 진입 (Section3Section ?sid= URL routing). */
  onOpenSession?: (sid: string) => void;
}) {
  const [recentSessions, setRecentSessions] = useState<SessionSummary[] | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    listSessions({ limit: 5, repo_id: p.repoId })
      .then((r) => { if (alive) setRecentSessions(r.sessions); })
      .catch(() => { if (alive) setRecentSessions([]); });
    return () => { alive = false; };
  }, [p.repoId]);

  return (
    <div className="max-w-3xl mx-auto py-4 space-y-5">
      {/* Hero question */}
      <div className="text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-[10px] font-semibold uppercase tracking-wider mb-2">
          <Sparkles size={11} /> Section 3 — 멀티턴 시뮬 / 영향도 agent
        </div>
        <h2 className="text-xl font-semibold">🎯 무엇을 알고 싶으세요?</h2>
        <p className="text-[12px] text-muted-foreground mt-1">
          5 종 의도 중 하나로 시작 → 자동 3 stage 진행 (의도 → 영역 → 시뮬레이션)
        </p>
      </div>

      {/* Intent category cards */}
      <div className="grid grid-cols-3 gap-2.5">
        {INTENT_CATEGORIES.map((cat) => (
          <IntentCategoryCard
            key={cat.kind}
            category={cat}
            onPick={p.onPick}
          />
        ))}
      </div>

      {/* Recent sessions */}
      {recentSessions && recentSessions.length > 0 && (
        <div className="border border-border rounded-lg bg-card/50 p-3">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground mb-2">
            <History size={11} />
            최근 세션 ({recentSessions.length})
            <span className="font-normal normal-case text-muted-foreground/70 ml-auto font-mono">
              repo: {p.repoId}
            </span>
          </div>
          <div className="space-y-1">
            {recentSessions.slice(0, 5).map((s) => {
              const label = INTENT_LABEL_MAP[
                inferIntentFromGateKind(s.last_gate_kind)
              ] ?? "❓";
              return (
                <button
                  key={s.id}
                  onClick={() => p.onOpenSession?.(s.id)}
                  className="w-full text-left px-2 py-1.5 rounded hover:bg-muted/50 transition-colors flex items-center gap-2 text-[11px]"
                >
                  <span className="font-mono text-[10px] shrink-0">{label}</span>
                  <span className="truncate flex-1">{s.user_query || "(no query)"}</span>
                  <span className={`shrink-0 text-[9px] font-mono ${s.status === "done" ? "text-emerald-600" : "text-amber-600"}`}>
                    {s.status}
                  </span>
                  <ArrowRight size={10} className="text-muted-foreground shrink-0" />
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Free natural-language input */}
      <div className="border-t border-border/40 pt-3">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
          또는 자연어로 직접
        </div>
        {/* 실제 input 은 부모 (MultiturnChat) 의 하단 input bar 가 처리 — 여기는 hint */}
        <p className="text-[11px] text-muted-foreground italic">
          ↓ 하단 입력창에 한국어로 자연스럽게 입력하세요. agent 가 의도 분류해줍니다.
        </p>
      </div>

      {/* Advanced (collapse) */}
      <div className="border-t border-border/40 pt-3">
        <button
          onClick={() => setAdvancedOpen((v) => !v)}
          className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ChevronDown
            size={11}
            className={`transition-transform ${advancedOpen ? "" : "-rotate-90"}`}
          />
          고급 옵션 (repo 변경)
        </button>
        {advancedOpen && (
          <div className="mt-2 border border-border rounded p-2.5">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
              repo_id
            </label>
            <input
              value={p.repoId}
              onChange={(e) => p.setRepoId(e.target.value)}
              className="block mt-1 w-full px-2 py-1 text-[11px] font-mono border border-border rounded bg-background"
            />
            <p className="text-[10px] text-muted-foreground/70 mt-1">
              기본: <code className="font-mono">slab-design-real-v2</code>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function IntentCategoryCard({
  category, onPick,
}: { category: IntentCategory; onPick: (q: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = category.Icon;

  return (
    <div className={`border rounded-lg ${category.cls} ${category.bgCls}/30 overflow-hidden`}>
      <button
        onClick={() => setExpanded((v) => !v)}
        className={`w-full p-2.5 text-left ${expanded ? "" : "hover:" + category.bgCls}`}
      >
        <div className="flex items-start gap-2">
          <Icon size={16} className="shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-[13px] truncate">{category.label}</div>
            <div className="text-[10px] opacity-80 mt-0.5 leading-tight">
              {category.description}
            </div>
          </div>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-current/20 px-2 pt-1.5 pb-2 space-y-1 bg-card/40">
          {category.examples.map((ex) => (
            <button
              key={ex.q}
              onClick={(e) => { e.stopPropagation(); onPick(ex.q); }}
              className="w-full text-left text-[11px] hover:bg-card/60 rounded px-1.5 py-1 transition-colors"
            >
              <div className="text-foreground truncate">&ldquo;{ex.q}&rdquo;</div>
              {ex.hint && (
                <div className="text-[9px] text-muted-foreground/80 truncate">{ex.hint}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function inferIntentFromGateKind(gateKind: string | null): string {
  if (!gateKind) return "ambiguous";
  if (gateKind === "executed_simulation") return "simulate";
  if (gateKind === "executed_impact") return "impact";
  if (gateKind === "executed_hypothesis") return "hypothesis";
  if (gateKind === "executed_lookup") return "locate";  // or explain — 양쪽 다
  return "ambiguous";
}


function SessionHeader({
  session, nextGateKind, currentStage,
}: {
  session: NonNullable<ReturnType<typeof useMultiturnSession>["state"]["session"]>;
  nextGateKind: string | null;
  /** Phase 20 — 현재 진행 stage (1/2/3). 없으면 0. */
  currentStage?: number;
}) {
  return (
    <div className="text-[11px] text-muted-foreground bg-muted/30 rounded px-3 py-2 border border-border">
      <div className="flex items-center gap-3">
        {/* Phase 20 — 3-stage progress dots */}
        {currentStage !== undefined && (
          <StageProgress current={currentStage} />
        )}
        <span className="font-mono">
          session <span className="text-foreground">{session.id.slice(0, 8)}</span>
        </span>
        <span className="font-mono">
          repo <span className="text-foreground">{session.repo_id}</span>
        </span>
        <span className={`font-mono ${session.status === "done" ? "text-emerald-600" : "text-amber-600"}`}>
          {session.status}
        </span>
        {nextGateKind && session.status !== "done" && (
          <span className="font-mono text-blue-600">
            → {nextGateKind}
          </span>
        )}
        {session.user_query && (
          <span className="truncate flex-1 italic">"{session.user_query}"</span>
        )}
      </div>
    </div>
  );
}

function StageProgress({ current }: { current: number }) {
  // 0 = none, 1 = Stage 1 진행, 2 = Stage 2, 3 = Stage 3 (done 포함)
  return (
    <div className="flex items-center gap-0.5" title={`Stage ${current}/3`}>
      {[1, 2, 3].map((s) => {
        const active = current >= s;
        const isCurrent = current === s;
        return (
          <span
            key={s}
            className={
              isCurrent
                ? "w-1.5 h-1.5 rounded-full bg-primary ring-2 ring-primary/30"
                : active
                ? "w-1.5 h-1.5 rounded-full bg-emerald-500"
                : "w-1.5 h-1.5 rounded-full bg-border"
            }
          />
        );
      })}
    </div>
  );
}

// Phase 20 — decision log → 현재 stage 계산 (1/2/3).
//   1 = intent_classified (Phase 21b) 또는 Gate I real 만 (candidate 미확정)
//   2 = candidate confirm 됐고 bundle 아직
//   3 = bundle 또는 executed 도달
function computeCurrentStage(decisions: DecisionView[]): number {
  if (decisions.length === 0) return 0;
  const hasExecuted = decisions.some(
    (d) => d.gate_kind === "bundle_prepared" || d.gate_kind.startsWith("executed_"),
  );
  if (hasExecuted) return 3;
  const gateIReal = decisions.find(
    (d) =>
      d.gate_kind === "target_selected" &&
      (d.payload as GateTarget).intent !== "ambiguous",
  );
  if (gateIReal && gateIReal.user_response !== null) return 2;
  if (gateIReal) return 1;
  // Phase 21b — intent_classified turn 도 Stage 1 으로 카운트
  if (decisions.some((d) => d.gate_kind === "intent_classified")) return 1;
  return 0;
}

// Phase 18 — confirmed candidate 의 ScopeStage context 추출.
// turn 2 의 user_response (selected_index) 로 후보 픽 → 해당 candidate 의
// action_fqn / code_method_fqn / declared_on_term 반환.
function selectedScopeContext(
  decision: DecisionView,
  _allDecisions: DecisionView[],
): { action_fqn: string; code_method_fqn: string; declared_on_term: string | null } | null {
  const payload = decision.payload as GateTarget;
  const resp = decision.user_response;
  if (!resp || typeof resp.selected_index !== "number") return null;
  const idx = resp.selected_index;
  const cand = payload.candidates[idx];
  if (!cand) return null;
  return {
    action_fqn: cand.action_id,
    code_method_fqn: cand.code_method_fqn,
    declared_on_term: cand.declared_on_term ?? null,
  };
}

// Phase 17 — 3-Stage workflow frame.
// 사용자 vision: (1) 의도 파악 → (2) 영향 영역 → (3) 시뮬레이션. agent gate
// timeline 을 3 stage 시각 frame 으로 wrap. backend 변경 0, UX 만 재정렬.
function WorkflowFrame(p: {
  decisions: DecisionView[];
  pending: boolean;
  repoId: string;
  onConfirmIntent: (turn_no: number) => void;
  onConfirmGateI: (turn_no: number, selected_index: number) => void;
  onRetryGateI: () => void;
  onProceedBundle: () => void;
  onSuggestionClick?: (suggestion: string) => void;
  onRetryWithDifferentTarget?: () => void;
  onEditIntent?: () => void;
}) {
  // Phase 21b — intent_classified turn (Gate I-a). 사용자가 confirm 하면
  // 다음 /respond 에서 target_selected (Gate I real) 진행.
  const intentClassified = p.decisions.find(
    (d) => d.gate_kind === "intent_classified",
  );
  // Find the Gate I real decision (intent !== "ambiguous").
  // turn 1 = stub (ambiguous + cand=0), turn 2 또는 3 = real Gate I.
  const gateIReal = p.decisions.find(
    (d) =>
      d.gate_kind === "target_selected" &&
      (d.payload as GateTarget).intent !== "ambiguous",
  );
  // Stage 2+ progressed if any decision exists past Gate I real
  const stage2Confirmed = p.decisions.some(
    (d) =>
      d.gate_kind === "bundle_prepared" ||
      d.gate_kind.startsWith("executed_"),
  );
  const stage1Collapsed = stage2Confirmed;
  // intent_classified 가 있고 gateIReal 가 아직 없으면 → IntentStage 가 confirm 대기 상태
  const intentAwaitingConfirm = !!intentClassified && !gateIReal;

  // Decisions that belong to Stage 2 (target_selected real) vs Stage 3 (bundle/executed)
  const stage2Decisions = p.decisions.filter(
    (d) =>
      d.gate_kind === "target_selected" &&
      (d.payload as GateTarget).intent !== "ambiguous",
  );
  const stage3Decisions = p.decisions.filter(
    (d) =>
      d.gate_kind === "bundle_prepared" ||
      d.gate_kind.startsWith("executed_"),
  );

  return (
    <div className="space-y-4">
      {/* Stage 1 — 의도 파악 (Phase 21b: intent_classified pause 또는 target_selected) */}
      {intentAwaitingConfirm && intentClassified && (
        <IntentStage
          payload={intentClassified.payload as GateIntentClassified}
          collapsed={false}
          onConfirm={() => p.onConfirmIntent(intentClassified.turn_no)}
          confirmDisabled={intentClassified.user_response !== null}
          pending={p.pending}
          onEdit={p.onEditIntent}
        />
      )}
      {gateIReal && (
        <IntentStage
          payload={gateIReal.payload as GateTarget}
          collapsed={stage1Collapsed}
          onEdit={p.onEditIntent}
        />
      )}

      {/* Stage 2 — 영향 영역 (candidate selection + Phase 18 scope panel) */}
      {stage2Decisions.length > 0 && (
        <StageFrame
          stage={2}
          title="영향 영역"
          subtitle="후보 선택 + 영향도"
          icon={<GitBranch size={14} className="text-primary" />}
          collapsed={stage2Confirmed && stage2Decisions[0].user_response !== null}
        >
          {stage2Decisions.map((d, i) => (
            <DecisionCard
              key={`${d.turn_no}-${d.gate_kind}-${i}`}
              decision={d}
              isLast={false}
              pending={p.pending}
              repoId={p.repoId}
              onConfirmGateI={(idx) => p.onConfirmGateI(d.turn_no, idx)}
              onRetryGateI={p.onRetryGateI}
              onProceedBundle={p.onProceedBundle}
              onSuggestionClick={p.onSuggestionClick}
              onRetryWithDifferentTarget={p.onRetryWithDifferentTarget}
            />
          ))}
          {/* Phase 18 — scope panel: 사용자가 candidate confirm 한 후 (user_response 존재) 렌더링.
              그 전에는 단순 후보 list. */}
          {stage2Decisions[0].user_response !== null &&
           selectedScopeContext(stage2Decisions[0], p.decisions) && (
            <ScopeStage
              selected={selectedScopeContext(stage2Decisions[0], p.decisions)!}
              repoId={p.repoId}
              collapsed={false}
            />
          )}
        </StageFrame>
      )}

      {/* Stage 3 — 시뮬레이션 (bundle + executed) */}
      {stage3Decisions.length > 0 && (
        <StageFrame
          stage={3}
          title="시뮬레이션"
          subtitle="실행 및 결과"
          icon={<FlaskConical size={14} className="text-primary" />}
          collapsed={false}
        >
          {/* Phase 19 — 영역/fixture/상태 요약 헤더 */}
          <SimulateStageHeader
            decisions={stage3Decisions}
            primaryMethodFqn={
              stage2Decisions[0] && stage2Decisions[0].user_response !== null
                ? selectedScopeContext(stage2Decisions[0], p.decisions)?.code_method_fqn ?? null
                : null
            }
          />
          {stage3Decisions.map((d, i) => (
            <DecisionCard
              key={`${d.turn_no}-${d.gate_kind}-${i}`}
              decision={d}
              isLast={i === stage3Decisions.length - 1}
              pending={p.pending}
              repoId={p.repoId}
              onConfirmGateI={(idx) => p.onConfirmGateI(d.turn_no, idx)}
              onRetryGateI={p.onRetryGateI}
              onProceedBundle={p.onProceedBundle}
              onSuggestionClick={p.onSuggestionClick}
              onRetryWithDifferentTarget={p.onRetryWithDifferentTarget}
            />
          ))}
        </StageFrame>
      )}
    </div>
  );
}

// Stage frame — 공통 header (Stage N — Title) + children
function StageFrame({
  stage, title, subtitle, icon, collapsed, children,
}: {
  stage: number;
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  collapsed: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border/60 rounded-lg bg-card/30 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/40 bg-muted/30">
        {icon}
        <span className="text-sm font-semibold">
          Stage {stage} — {title}
        </span>
        {subtitle && (
          <span className="text-[11px] text-muted-foreground">· {subtitle}</span>
        )}
        {collapsed && (
          <span className="ml-auto text-[10px] text-emerald-600 font-medium">
            ✓ 확정됨
          </span>
        )}
      </div>
      <div className="p-3 space-y-3">{children}</div>
    </div>
  );
}

function DecisionCard(p: {
  decision: DecisionView;
  isLast: boolean;
  pending: boolean;
  repoId: string;
  onConfirmGateI: (selected_index: number) => void;
  onRetryGateI: () => void;
  onProceedBundle: () => void;
  onSuggestionClick?: (suggestion: string) => void;
  onRetryWithDifferentTarget?: () => void;
}) {
  const { decision, isLast, pending, repoId } = p;
  const payload = decision.payload as GatePayload;

  if (payload.kind === "target_selected") {
    // turn 1 stub (ambiguous + auto-progress) 는 surface 안 함
    if (payload.intent === "ambiguous" && payload.candidates.length === 0) {
      return null;
    }
    return (
      <GateTargetCard
        payload={payload}
        turn_no={decision.turn_no}
        alreadyConfirmed={decision.user_response !== null}
        pending={pending}
        repoId={repoId}
        onConfirm={p.onConfirmGateI}
        onRetry={p.onRetryGateI}
        onSuggestionClick={p.onSuggestionClick}
      />
    );
  }
  if (payload.kind === "bundle_prepared") {
    return (
      <GateBundleCard
        payload={payload}
        turn_no={decision.turn_no}
        pending={pending}
        isLast={isLast}
        repoId={repoId}
        onProceed={p.onProceedBundle}
      />
    );
  }
  if (payload.kind === "executed_simulation") {
    return (
      <GateExecutedSimulationCard
        payload={payload}
        turn_no={decision.turn_no}
      />
    );
  }
  if (payload.kind === "executed_impact") {
    return (
      <GateExecutedImpactCard
        payload={payload}
        turn_no={decision.turn_no}
        repoId={repoId}
      />
    );
  }
  if (payload.kind === "executed_lookup" || payload.kind === "executed_hypothesis") {
    // Phase 16J — target_is_test 빨강 발화 시 retry CTA 노출.
    // 빨강 칩 detection 은 GateExecutedReadOnlyCard 내부에서 sources 파싱.
    // 여기서는 callback 만 옵셔널로 전달 — 카드가 빨강 발화 시에만 사용.
    const retryCta = p.onRetryWithDifferentTarget
      ? {
          label: "다른 후보로 다시 시도",
          onClick: p.onRetryWithDifferentTarget,
        }
      : null;
    return (
      <GateExecutedReadOnlyCard
        payload={payload}
        turn_no={decision.turn_no}
        onRetryWithDifferentTarget={retryCta}
      />
    );
  }
  return null;
}

function PendingPulse() {
  return (
    <div className="flex items-center gap-2 text-[12px] text-muted-foreground px-3 py-2">
      <Loader2 size={14} className="animate-spin text-primary" />
      <span>처리 중… (LLM 분류 / sim_v2 / ontology 호출)</span>
    </div>
  );
}

function ErrorBanner({ status, detail }: { status: number; detail: string }) {
  return (
    <div className="flex items-start gap-2 px-3 py-2 border border-rose-200 bg-rose-50 text-rose-700 rounded text-[12px]">
      <AlertCircle size={14} className="mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-mono font-semibold">HTTP {status}</div>
        <div className="font-mono whitespace-pre-wrap mt-0.5">{detail}</div>
      </div>
    </div>
  );
}
