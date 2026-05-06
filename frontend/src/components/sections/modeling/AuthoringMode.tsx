"use client";

/**
 * AuthoringMode — interview-driven ontology authoring UI.
 *
 * Layout:
 *   ┌──────────────────────────┬─────────────────────────────┐
 *   │ Chat (capability i/o)    │ Live preview               │
 *   │   • toolbar (start/...)  │   • current hypothesis card │
 *   │   • message thread       │   • accepted option sketch  │
 *   │   • answer textarea      │   • named entities + roles  │
 *   │                          │   • cost summary            │
 *   └──────────────────────────┴─────────────────────────────┘
 *
 * Backend API: /api/authoring/* (see backend/api/authoring.py).
 * Round-5 archive corpus: see toClaude/modeling/round5-live-authoring.html.
 */

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthoring, type ChatMessage } from "./authoring/store";
import { useWorkbench } from "./store";
import { authoringApi } from "@/lib/api/authoring";
import type {
  AbsorbedAnswers,
  ArchiveDocument,
  AuthoringSession,
  ConfirmResponse,
  EntityHypothesis,
  ExtractedJpo,
  ComprehensiveArchive,
  GapAnalysis,
  InterviewBatch,
  NamingDecision,
  NextEntityRecommendation,
  NextStep,
  OntologyOption,
  OptionTable,
  PatternCheck,
} from "@/lib/api/authoring";

const DEFAULT_REPO_ID = "smoke-slab";

export function AuthoringMode() {
  const session = useAuthoring((s) => s.session);
  const messages = useAuthoring((s) => s.messages);
  const loading = useAuthoring((s) => s.loading);
  const error = useAuthoring((s) => s.error);
  const costUsd = useAuthoring((s) => s.costUsd);
  const turnNo = useAuthoring((s) => s.turnNo);
  const resumeSession = useAuthoring((s) => s.resumeSession);
  const completedEntities = useAuthoring((s) => s.completedEntities);
  const currentJpo = useAuthoring((s) => s.jpo);

  // P1a-B: if URL contains ?authoring_session=<id>, auto-resume.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (session) return; // already loaded
    const params = new URLSearchParams(window.location.search);
    const sid = params.get("authoring_session");
    if (sid) {
      resumeSession(sid).catch(() => {
        // silent — error surfaces in store.error
      });
    }
  }, [session, resumeSession]);

  return (
    <PanelGroup direction="horizontal" className="h-full">
      <Panel defaultSize={55} minSize={30}>
        <div className="flex flex-col h-full bg-card">
          <Toolbar />
          <SelectionBanner />
          {error && (
            <div className="px-3 py-2 text-[12px] text-rose-400 border-b border-rose-400/40 bg-rose-400/5">
              ⚠️ {error}
            </div>
          )}
          <ChatThread messages={messages} loading={loading} />
          <div className="h-7 border-t border-border bg-muted/40 px-3 flex items-center text-[11px] text-muted-foreground gap-3">
            {session ? (
              <>
                <span>session: <code className="font-mono">{session.id.slice(0, 8)}…</code></span>
                <span>turn {turnNo}</span>
                <span>
                  entity {completedEntities.length}
                  {currentJpo ? ` (+1 진행)` : ""}
                </span>
                <span>cost ${costUsd.toFixed(4)}</span>
                {loading && <span className="text-primary">⏳ 진행 중...</span>}
              </>
            ) : (
              <span>세션 없음 — 새 인터뷰를 시작하세요.</span>
            )}
          </div>
        </div>
      </Panel>
      <PanelResizeHandle className="w-1 bg-border hover:bg-primary transition-colors" />
      <Panel defaultSize={45} minSize={25}>
        <PreviewPanel />
      </Panel>
    </PanelGroup>
  );
}

// ── Selection banner (좌측 트리 → ① 코드 추출 안내) ──────────────────

function SelectionBanner() {
  const session = useAuthoring((s) => s.session);
  const jpo = useAuthoring((s) => s.jpo);
  const selectedFqn = useWorkbench((s) => s.selectedCodeTypeFqn);

  // 가설/인터뷰가 시작된 후엔 banner 안 보이게 — 답변 영역에 집중.
  if (jpo) return null;

  const simpleName = selectedFqn ? selectedFqn.split(".").pop() : null;
  const pkg = selectedFqn ? selectedFqn.replace(/\.[^.]+$/, "") : null;

  if (!session) {
    return (
      <div className="px-3 py-2 border-b border-border bg-muted/20 text-[11.5px] text-muted-foreground">
        세션 없음 — 우측 상단 toolbar 의 <strong>🆕 새 세션</strong> 부터 시작
      </div>
    );
  }

  if (!selectedFqn) {
    return (
      <div className="px-3 py-2.5 border-b border-amber-400/40 bg-amber-400/5 text-[11.5px] text-amber-300">
        <div className="font-semibold mb-0.5">📂 좌측에서 JPO 클래스 선택</div>
        <div className="text-amber-300/80">
          좌측 패키지 트리 → 패키지 클릭 → <strong>하단 inventory 패널</strong>에서 클래스 클릭.
          <br />
          (선택 없이 ① 코드 추출 시 bundled <code>HrSpecJpo</code> 사용 — demo 모드)
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-2.5 border-b border-emerald-400/40 bg-emerald-400/5 text-[11.5px]">
      <div className="flex items-baseline gap-2">
        <span className="text-emerald-400 font-semibold">✓ 선택됨</span>
        <code className="font-mono text-[12px] text-foreground">{simpleName}</code>
        <span className="text-[10.5px] text-muted-foreground truncate">{pkg}</span>
      </div>
      <div className="text-[10.5px] text-muted-foreground mt-0.5">
        toolbar 의 <strong>① 코드 추출 ({simpleName})</strong> 클릭 또는 좌측 트리에서 다른 클래스 선택
      </div>
    </div>
  );
}

// ── Toolbar ─────────────────────────────────────────────────────────

function Toolbar() {
  const session = useAuthoring((s) => s.session);
  const jpo = useAuthoring((s) => s.jpo);
  const hypothesis = useAuthoring((s) => s.hypothesis);
  const batch = useAuthoring((s) => s.batch);
  const answers = useAuthoring((s) => s.answers);
  const acceptedOption = useAuthoring((s) => s.acceptedOption);
  const names = useAuthoring((s) => s.names);
  const archive = useAuthoring((s) => s.archive);
  const persistedFqns = useAuthoring((s) => s.persistedFqns);
  const loading = useAuthoring((s) => s.loading);

  const startNewSession = useAuthoring((s) => s.startNewSession);
  const runExtract = useAuthoring((s) => s.runExtract);
  const runHypothesize = useAuthoring((s) => s.runHypothesize);
  const runInterview = useAuthoring((s) => s.runInterview);
  const runOptions = useAuthoring((s) => s.runOptions);
  const runGaps = useAuthoring((s) => s.runGaps);
  const runPatternCheck = useAuthoring((s) => s.runPatternCheck);
  const runNextStep = useAuthoring((s) => s.runNextStep);
  const runArchive = useAuthoring((s) => s.runArchive);
  const runConfirm = useAuthoring((s) => s.runConfirm);
  const acceptedOptionForToolbar = useAuthoring((s) => s.acceptedOption);

  const onStart = async () => {
    await startNewSession({ repoId: DEFAULT_REPO_ID });
  };

  // R2-W2 / "A": 좌측 트리에서 선택된 클래스 fqn 을 사용. backend 가
  // CodeTypeRow.source_file 로 disk 에서 raw content 를 읽어옴.
  const selectedFqn = useWorkbench((s) => s.selectedCodeTypeFqn);
  const activeRepoId = useWorkbench((s) => s.activeRepoId);
  const selectedSimpleName = selectedFqn ? selectedFqn.split(".").pop() : null;

  const onExtract = async () => {
    if (!session) return;
    if (!selectedFqn) {
      // Fallback to bundled HrSpec when nothing is picked — keeps the
      // prototype runnable on a fresh repo without imported code.
      await runExtract({
        filePath: "(bundled) HrSpecJpo.java",
        fileContent: BUNDLED_HR_SPEC_JPO,
      });
      return;
    }
    await runExtract({ fqn: selectedFqn, repoId: activeRepoId });
  };

  return (
    <div className="min-h-9 px-3 py-1 border-b border-border flex items-center gap-2 flex-wrap flex-shrink-0">
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mr-2">
        ✏️ Authoring
      </span>
      <Button size="sm" variant="outline" onClick={onStart} disabled={loading}>
        🆕 새 세션
      </Button>
      <ResumeSessionButton />
      <CopySessionUrlButton />
      <Button
        size="sm"
        variant="outline"
        onClick={onExtract}
        disabled={loading || !session || !!jpo}
        title={
          selectedSimpleName
            ? `좌측 트리 선택: ${selectedSimpleName}`
            : "좌측 트리에서 클래스 선택 (없으면 bundled HrSpec)"
        }
      >
        ① 코드 추출{selectedSimpleName && ` (${selectedSimpleName})`}
      </Button>
      <Button size="sm" variant="outline" onClick={runHypothesize} disabled={loading || !jpo || !!hypothesis}>
        ② 가설
      </Button>
      <Button size="sm" variant="outline" onClick={runInterview} disabled={loading || !hypothesis || !!batch}>
        ③ 인터뷰
      </Button>
      <Button size="sm" variant="outline" onClick={runOptions} disabled={loading || !answers || !!acceptedOption}>
        ⑤ 옵션
      </Button>
      <Button size="sm" variant="outline" onClick={runGaps} disabled={loading || !answers}>
        ⑥ 갭
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={runPatternCheck}
        disabled={loading || !acceptedOptionForToolbar}
        title="cap 7 — 기존 ontology 패턴과의 정합성 검사"
      >
        ⑦ 패턴
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={runNextStep}
        disabled={loading || !session}
        title="cap 10 — 다음 단계 추천"
      >
        ⑩ 다음 단계
      </Button>
      <Button size="sm" variant="outline" onClick={runArchive} disabled={loading || !names || !!archive}>
        ⑨ Archive
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => runConfirm(DEFAULT_REPO_ID, "scm")}
        disabled={loading || !names || persistedFqns.length > 0}
        className="border-emerald-400 text-emerald-400 hover:bg-emerald-400/10"
      >
        ✓ Confirm
      </Button>
      <NextEntityButton />
      <ComprehensiveArchiveButton />
    </div>
  );
}

// P1a-E: "📚 종합 archive" — synthesises all entities (completed + current)
// into a single domain report. Visible when ≥1 entity has been worked on.
function ComprehensiveArchiveButton() {
  const runComprehensiveArchive = useAuthoring((s) => s.runComprehensiveArchive);
  const completedEntities = useAuthoring((s) => s.completedEntities);
  const jpo = useAuthoring((s) => s.jpo);
  const loading = useAuthoring((s) => s.loading);
  const activeRepoId = useWorkbench((s) => s.activeRepoId);

  const total = completedEntities.length + (jpo ? 1 : 0);
  if (total < 1) return null;
  // Encourage multi-entity use; meaningful from 2+ entities.
  const ready = total >= 2;

  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() => activeRepoId && runComprehensiveArchive(activeRepoId)}
      disabled={loading || !activeRepoId}
      title={
        ready
          ? `종합 archive — 이번 세션의 ${total} entity 통합 보고서`
          : "최소 2 entity 부터 의미 있음 — 지금도 single-entity 보고서 생성 가능"
      }
      className={cn(
        "border-cyan-400 text-cyan-400 hover:bg-cyan-400/10",
        !ready && "opacity-60",
      )}
    >
      📚 종합 archive
    </Button>
  );
}

// P1a-B / P3 폴리싱: list 기반 dropdown picker. prompt 입력 대신 최근
// active 세션 카드를 보여주고 클릭 시 resume.
function ResumeSessionButton() {
  const resumeSession = useAuthoring((s) => s.resumeSession);
  const session = useAuthoring((s) => s.session);
  const loading = useAuthoring((s) => s.loading);
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<AuthoringSession[]>([]);
  const [fetching, setFetching] = useState(false);

  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setFetching(true);
    try {
      const list = await authoringApi.listSessions({ status: "active" });
      // most recent first by last_activity_at
      list.sort((a, b) => +new Date(b.last_activity_at) - +new Date(a.last_activity_at));
      setSessions(list);
      setOpen(true);
    } catch {
      setSessions([]);
      setOpen(true);
    } finally {
      setFetching(false);
    }
  };

  const onPick = async (id: string) => {
    setOpen(false);
    await resumeSession(id).catch((e) => {
      window.alert(`세션 로드 실패: ${e instanceof Error ? e.message : String(e)}`);
    });
  };

  const fmtTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString("ko-KR", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso.slice(0, 16);
    }
  };

  return (
    <div className="relative">
      <Button
        size="sm"
        variant="outline"
        onClick={toggle}
        disabled={loading || !!session || fetching}
        title="기존 active 세션 목록 → 클릭하여 이어서 진행"
      >
        ↻ 이어서{fetching ? "..." : ""}
      </Button>
      {open && (
        <div
          className="absolute top-full left-0 mt-1 z-50 w-[420px] max-h-[360px] overflow-auto rounded-md border border-border bg-card shadow-xl"
          onMouseLeave={() => setOpen(false)}
        >
          {sessions.length === 0 ? (
            <div className="p-3 text-[12px] text-muted-foreground italic text-center">
              active 상태의 기존 세션이 없습니다.
            </div>
          ) : (
            <ul>
              {sessions.slice(0, 12).map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onPick(s.id)}
                    className="w-full text-left px-3 py-2 hover:bg-muted/40 border-b border-border/40 transition"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <code className="text-[11px] font-mono text-foreground">
                        {s.id.slice(0, 8)}…
                      </code>
                      <span className="text-[10px] text-muted-foreground">
                        {fmtTime(s.last_activity_at)}
                      </span>
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      repo: <span className="text-foreground">{s.repo_id ?? "—"}</span>
                      {s.entity_focus && (
                        <>
                          {" · "}focus:{" "}
                          <span className="text-foreground">{s.entity_focus}</span>
                        </>
                      )}
                      {" · "}operator:{" "}
                      <span className="text-foreground">{s.operator_id}</span>
                    </div>
                  </button>
                </li>
              ))}
              {sessions.length > 12 && (
                <li className="px-3 py-1.5 text-[10px] text-muted-foreground italic">
                  +{sessions.length - 12}개 더 (최근 12개만 표시)
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// P1a-B: copies the resume URL (?authoring_session=<id>) to clipboard.
function CopySessionUrlButton() {
  const session = useAuthoring((s) => s.session);
  const [copied, setCopied] = useState(false);

  if (!session) return null;
  const onClick = async () => {
    const url = new URL(window.location.href);
    url.searchParams.set("authoring_session", session.id);
    try {
      await navigator.clipboard.writeText(url.toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      window.prompt("Resume URL (Cmd+C):", url.toString());
    }
  };
  return (
    <Button
      size="sm"
      variant="outline"
      onClick={onClick}
      title="Resume URL 복사 — 새 탭에서 열면 자동 이어서 진행"
    >
      {copied ? "✓ 복사됨" : "🔗 URL"}
    </Button>
  );
}

// P1-a: "다음 Entity" — capture current cycle, reset per-entity state,
// then auto-trigger cap 11 (next_entity picker) so the user sees JPO
// suggestions right away (P1a-C).
function NextEntityButton() {
  const startNextEntity = useAuthoring((s) => s.startNextEntity);
  const pickNextEntity = useAuthoring((s) => s.pickNextEntity);
  const jpo = useAuthoring((s) => s.jpo);
  const archive = useAuthoring((s) => s.archive);
  const persistedFqns = useAuthoring((s) => s.persistedFqns);
  const loading = useAuthoring((s) => s.loading);
  const activeRepoId = useWorkbench((s) => s.activeRepoId);

  if (!jpo) return null;
  // Encourage post-archive transition; greyed earlier so the user feels
  // the natural sequence (archive → next entity).
  const ready = !!archive || persistedFqns.length > 0;

  const onClick = async () => {
    startNextEntity();
    // Fire-and-forget: cap 11 picks next 3-5 candidates for the user.
    // We don't await because startNextEntity already updated UI; pickNextEntity
    // runs in the background and pushes its result as a chat message.
    if (activeRepoId) {
      pickNextEntity(activeRepoId).catch(() => {
        // pickNextEntity is non-critical — failure logged via withLoading
      });
    }
  };

  return (
    <Button
      size="sm"
      variant="outline"
      onClick={onClick}
      disabled={loading}
      title={
        ready
          ? "현재 entity 마무리 + 다음 JPO 자동 추천"
          : "Archive/Confirm 후 권장 — 클릭 시 history 저장 + 다음 JPO 추천"
      }
      className={cn(
        "border-violet-400 text-violet-400 hover:bg-violet-400/10",
        !ready && "opacity-60",
      )}
    >
      ⤳ 다음 Entity
    </Button>
  );
}

// ── Chat thread ─────────────────────────────────────────────────────

function ChatThread({ messages, loading }: { messages: ChatMessage[]; loading: boolean }) {
  const activeTrace = useAuthoring((s) => s.activeToolTrace);

  return (
    <div className="flex-1 overflow-auto p-3 space-y-2">
      {messages.length === 0 && (
        <div className="text-[12px] text-muted-foreground italic px-2 py-8 text-center">
          새 세션을 시작한 뒤 ① 코드 추출 부터 진행하세요.
        </div>
      )}
      {messages.map((m) => (
        <ChatBubble key={m.id} m={m} />
      ))}
      {activeTrace.stage && <LiveToolTraceCard trace={activeTrace} />}
      {loading && !activeTrace.stage && (
        <div className="text-[11px] text-muted-foreground animate-pulse px-2">⏳ LLM 호출 중...</div>
      )}
    </div>
  );
}

/** β UX — live progress while a streaming capability runs. */
function LiveToolTraceCard({ trace }: { trace: { stage: string | null; currentTool: { tool_name: string; args_summary: string } | null; completed: { tool_name: string; duration_ms: number }[] } }) {
  const stageLabel = (() => {
    switch (trace.stage) {
      case "extract": return "코드 추출";
      case "hypothesize": return "가설 수립";
      case "options": return "옵션 제시";
      case "gaps": return "갭 탐지";
      case "pattern": return "패턴 검사";
      case "next_entity": return "다음 JPO 추천";
      default: return "분석";
    }
  })();
  return (
    <div className="border border-blue-400/40 bg-blue-400/5 rounded-md px-3 py-2 text-[12px]">
      <div className="text-[10px] uppercase tracking-wider text-blue-400 mb-1">
        🔍 {stageLabel} · 그래프 탐색 중
      </div>
      {trace.currentTool ? (
        <div className="flex items-center gap-2">
          <span className="animate-pulse">●</span>
          <code className="text-[11px] text-foreground">{trace.currentTool.tool_name}</code>
          {trace.currentTool.args_summary && (
            <span className="text-[10px] text-muted-foreground truncate">
              {trace.currentTool.args_summary}
            </span>
          )}
        </div>
      ) : (
        <div className="text-muted-foreground italic">분석 중…</div>
      )}
      {trace.completed.length > 0 && (
        <div className="mt-1.5 pt-1.5 border-t border-blue-400/20 text-[10px] text-muted-foreground">
          완료 {trace.completed.length}회 · {trace.completed.map((t) => t.tool_name).slice(-3).join(" · ")}
        </div>
      )}
    </div>
  );
}

function ChatBubble({ m }: { m: ChatMessage }) {
  const align = m.role === "user" ? "items-end" : "items-start";
  const tint =
    m.role === "user"
      ? "bg-primary/10 border-primary/40"
      : m.kind === "error"
      ? "bg-rose-400/10 border-rose-400/40"
      : "bg-muted border-border";

  // F3 / R2-W2: which stage does this card represent? Only assistant cards
  // for stages with a backend rerun endpoint get the ✏/🔄 footer.
  const stageOf = (kind: string): "hypothesis" | "interview" | "options" | "naming" | null => {
    if (m.role !== "assistant") return null;
    if (kind === "hypothesis") return "hypothesis";
    if (kind === "interview") return "interview";
    if (kind === "options") return "options";
    if (kind === "naming") return "naming";
    return null;
  };
  const stage = stageOf(m.kind);

  return (
    <div className={cn("flex flex-col", align)}>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
        {m.role} · {m.kind}
      </div>
      <div className={cn("max-w-full border rounded-md px-3 py-2 text-[12px]", tint)}>
        <ChatPayload m={m} />
        {m.toolTrace && m.toolTrace.length > 0 && (
          <ToolTraceToggle trace={m.toolTrace} />
        )}
        {stage && <RerunFooter stage={stage} />}
      </div>
    </div>
  );
}

/** γ UX — expandable post-hoc trace on cap 5 / cap 6 result cards. */
function ToolTraceToggle({ trace }: { trace: { tool_name: string; args_summary: string; result_summary: string; duration_ms: number; cached: boolean; error: string | null }[] }) {
  const [open, setOpen] = useState(false);
  const totalMs = trace.reduce((s, t) => s + t.duration_ms, 0);
  const cachedCount = trace.filter((t) => t.cached).length;
  return (
    <div className="mt-2 pt-2 border-t border-border/60">
      <button
        className="text-[10px] text-muted-foreground hover:text-foreground transition flex items-center gap-1"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "▾" : "▸"} 🔍 어떻게 알아냈나 — {trace.length}회 ({totalMs}ms{cachedCount ? `, 캐시 ${cachedCount}` : ""})
      </button>
      {open && (
        <ol className="mt-1.5 space-y-1 text-[10px] font-mono">
          {trace.map((t, i) => (
            <li
              key={i}
              className={cn(
                "px-2 py-1 rounded border-l-2",
                t.error ? "border-rose-400 bg-rose-400/5" : t.cached ? "border-amber-400/60 bg-amber-400/5" : "border-blue-400/60 bg-blue-400/5",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-foreground">{i + 1}. {t.tool_name}</span>
                <span className="text-muted-foreground">
                  {t.duration_ms}ms{t.cached ? " · cached" : ""}
                </span>
              </div>
              {t.args_summary && (
                <div className="text-muted-foreground truncate">args: {t.args_summary}</div>
              )}
              <div className="text-muted-foreground truncate">→ {t.result_summary}</div>
              {t.error && <div className="text-rose-400 truncate">⚠ {t.error}</div>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// Per-card "✏ 수정 / 🔄 다시" footer for F3 cascading feedback loop.
// The user can correct or rerun any prior stage; downstream stages clear.
function RerunFooter({
  stage,
}: {
  stage: "hypothesis" | "interview" | "options" | "naming";
}) {
  const rerun = useAuthoring((s) => s.rerunStage);
  const loading = useAuthoring((s) => s.loading);
  const [editing, setEditing] = useState(false);
  const [comment, setComment] = useState("");

  const stageLabel = {
    hypothesis: "가설",
    interview: "인터뷰",
    options: "옵션",
    naming: "명명",
  }[stage];

  const submit = async () => {
    setEditing(false);
    await rerun(stage, comment);
    setComment("");
  };

  if (editing) {
    return (
      <div className="mt-2 pt-2 border-t border-border/60 space-y-1.5">
        <div className="text-[10.5px] text-muted-foreground">
          {stageLabel} 정정 — 코멘트가 prompt 에 추가되고, 후속 단계는 모두 초기화됩니다
        </div>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          autoFocus
          placeholder={`예: 이 ${stageLabel}은 ... 으로 정정해줘`}
          className="w-full bg-background text-foreground border border-border rounded px-2 py-1 text-[11.5px] min-h-[44px] resize-y"
        />
        <div className="flex items-center gap-2">
          <button
            onClick={submit}
            disabled={loading || !comment.trim()}
            className="text-[10.5px] px-2 py-1 rounded bg-violet-400/15 text-violet-200 border border-violet-400/50 hover:bg-violet-400/25 disabled:opacity-50"
          >
            ✏ 정정 후 재실행
          </button>
          <button
            onClick={() => { setEditing(false); setComment(""); }}
            className="text-[10.5px] px-2 py-1 rounded text-muted-foreground hover:text-foreground"
          >
            취소
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2 pt-1.5 border-t border-border/40 flex items-center gap-2 text-[10.5px] text-muted-foreground">
      <button
        onClick={() => setEditing(true)}
        disabled={loading}
        title={`${stageLabel} 정정 (사용자 코멘트 추가) — 후속 단계 초기화`}
        className="hover:text-violet-300 disabled:opacity-40 transition-colors"
      >
        ✏ 수정
      </button>
      <span className="text-border">·</span>
      <button
        onClick={() => rerun(stage, "")}
        disabled={loading}
        title={`${stageLabel} 단순 재실행 — 후속 단계 초기화`}
        className="hover:text-primary disabled:opacity-40 transition-colors"
      >
        🔄 다시
      </button>
      <span className="ml-auto text-muted-foreground/60">단계: {stageLabel}</span>
    </div>
  );
}

function ChatPayload({ m }: { m: ChatMessage }) {
  switch (m.kind) {
    case "info":
    case "user_answer":
    case "error":
      return <div className="whitespace-pre-wrap">{String(m.payload)}</div>;
    case "extracted":
      return <ExtractedView jpo={m.payload as ExtractedJpo} />;
    case "hypothesis":
      return <HypothesisView h={m.payload as EntityHypothesis} />;
    case "interview":
      return <InterviewView batch={m.payload as InterviewBatch} />;
    case "absorbed":
      return <AbsorbedView a={m.payload as AbsorbedAnswers} />;
    case "options":
      return <OptionsView table={m.payload as OptionTable} />;
    case "gaps":
      return <GapsView g={m.payload as GapAnalysis} />;
    case "pattern":
      return <PatternView p={m.payload as PatternCheck} />;
    case "next_step":
      return <NextStepView n={m.payload as NextStep} />;
    case "next_entity":
      return <NextEntityView r={m.payload as NextEntityRecommendation} />;
    case "comprehensive_archive":
      return <ComprehensiveArchiveView a={m.payload as ComprehensiveArchive} />;
    case "naming":
      return <NamesView n={m.payload as NamingDecision} />;
    case "archive":
      return <ArchiveView a={m.payload as ArchiveDocument} />;
    case "confirmed":
      return <ConfirmedView c={m.payload as ConfirmResponse} />;
  }
}

// ── Per-kind chat renderers (compact — full detail lives in preview) ─────

function ExtractedView({ jpo }: { jpo: ExtractedJpo }) {
  return (
    <div>
      <div className="font-semibold text-violet-400 mb-1">
        {jpo.class_name} → {jpo.table_name}
      </div>
      <div className="text-[11px] text-muted-foreground">
        PK {jpo.pk_columns.length}축 · 컬럼 {jpo.regular_columns.length}개
        {jpo.pk_class && <> · PK class: <code>{jpo.pk_class}</code></>}
      </div>
    </div>
  );
}

function HypothesisView({ h }: { h: EntityHypothesis }) {
  return (
    <div>
      <div className="font-semibold mb-1">
        🧠 가설: <span className="text-violet-400">{h.candidate_term_korean}</span>
        <code className="ml-2 text-[11px] font-mono text-muted-foreground">{h.candidate_term_english}</code>
        <span className="ml-2 text-[10px] px-1.5 py-px rounded-full border border-amber-400 text-amber-400 bg-amber-400/10">
          conf {h.confidence.toFixed(2)}
        </span>
      </div>
      <div className="text-[11.5px] text-muted-foreground">{h.pk_role_summary}</div>
      {h.concerns.length > 0 && (
        <div className="text-[11px] text-rose-400 mt-1">⚠ {h.concerns[0]}</div>
      )}
    </div>
  );
}

function InterviewView({ batch }: { batch: InterviewBatch }) {
  // Round-5 form pattern (P3-A): per-question textarea + skip + freeform.
  // The user's prior feedback was "지금처럼 질문 별로 대답을 할 수 있는 구조가 좋은 것 같아".
  const submit = useAuthoring((s) => s.submitStructuredAnswers);
  const hasAnswers = useAuthoring((s) => !!s.answers);
  const loading = useAuthoring((s) => s.loading);
  const [answers, setAnswers] = useState<Record<string, { text: string; skip?: boolean }>>({});
  const [freeform, setFreeform] = useState("");

  const updateAnswer = (qid: string, patch: { text?: string; skip?: boolean }) => {
    setAnswers((prev) => ({ ...prev, [qid]: { ...(prev[qid] ?? { text: "" }), ...patch } }));
  };

  const onSubmit = async () => {
    await submit(answers, freeform);
  };

  return (
    <div>
      <div className="font-semibold text-amber-400 mb-1">
        ❓ 인터뷰 ({batch.questions.length} 질문)
      </div>
      <div className="text-[11.5px] text-muted-foreground mb-2">{batch.intro}</div>
      <div className="space-y-2.5 mt-2">
        {batch.questions.map((q, idx) => {
          const a = answers[q.id] ?? { text: "" };
          const importanceColor =
            q.importance === "critical"
              ? "border-rose-400/60"
              : q.importance === "optional"
              ? "border-muted-foreground/40"
              : "border-border";
          return (
            <div key={q.id} className={cn("border rounded p-2 bg-card/50", importanceColor)}>
              <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-[10px] text-muted-foreground font-mono">
                  {idx + 1}.
                </span>
                <span className="text-[12px] font-semibold flex-1">{q.prompt}</span>
                {q.importance === "critical" && (
                  <span className="text-[9px] text-rose-400 border border-rose-400 bg-rose-400/10 px-1 rounded">
                    필수
                  </span>
                )}
                {q.skip_ok && (
                  <label className="text-[10px] text-muted-foreground flex items-center gap-1 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-primary"
                      checked={!!a.skip}
                      onChange={(e) => updateAnswer(q.id, { skip: e.target.checked })}
                      disabled={hasAnswers || loading}
                    />
                    모름
                  </label>
                )}
              </div>
              {q.my_guess && (
                <div className="text-[10.5px] text-muted-foreground italic mb-1.5">
                  내 추측: {q.my_guess}
                </div>
              )}
              {q.options && q.options.length > 0 && (
                <div className="text-[10.5px] text-muted-foreground mb-1.5">
                  선택지: {q.options.join(" · ")}
                </div>
              )}
              {!a.skip && (
                <textarea
                  value={a.text}
                  onChange={(e) => updateAnswer(q.id, { text: e.target.value })}
                  placeholder={q.placeholder}
                  disabled={hasAnswers || loading}
                  className="w-full bg-muted text-foreground border border-border rounded px-2 py-1 text-[11.5px] font-mono min-h-[36px] resize-y disabled:opacity-60"
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-3 border-t border-border pt-2">
        <label className="text-[11px] text-muted-foreground block mb-1">
          추가 의견 / 인터뷰에 없는 사실 (자유)
        </label>
        <textarea
          value={freeform}
          onChange={(e) => setFreeform(e.target.value)}
          placeholder="optional — emergent facts 로 기록됩니다"
          disabled={hasAnswers || loading}
          className="w-full bg-muted text-foreground border border-border rounded px-2 py-1 text-[11.5px] font-mono min-h-[36px] resize-y disabled:opacity-60"
        />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <Button onClick={onSubmit} disabled={hasAnswers || loading} className="text-[11.5px]">
          ④ 답변 제출 (Q 별 정리)
        </Button>
        {hasAnswers && (
          <span className="text-[10.5px] text-emerald-400">
            ✓ 정리됨 — 다음: ⑤ 옵션 / ⑥ 갭
          </span>
        )}
      </div>
    </div>
  );
}

function AbsorbedView({ a }: { a: AbsorbedAnswers }) {
  const answered = Object.keys(a.per_question).length - a.unanswered.length;
  return (
    <div>
      <div className="font-semibold mb-1">📥 답변 정리됨 ({answered}/{Object.keys(a.per_question).length})</div>
      {a.contradictions.length > 0 && (
        <div className="text-[11.5px] text-amber-400 mt-1">
          ⚠ 가설과 모순: {a.contradictions[0]}
        </div>
      )}
      {a.emergent_facts.length > 0 && (
        <div className="text-[11.5px] text-violet-400 mt-1">
          💡 새 사실: {a.emergent_facts[0]}
        </div>
      )}
      <div className="mt-2 text-[11px] text-primary">
        → 다음: ⑤ 옵션 / ⑥ 갭 — toolbar 에서 진행
      </div>
    </div>
  );
}

function OptionsView({ table }: { table: OptionTable }) {
  const select = useAuthoring((s) => s.selectOption);
  const loading = useAuthoring((s) => s.loading);
  return (
    <div>
      <div className="font-semibold mb-1">🎯 {table.title}</div>
      <div className="text-[11.5px] text-muted-foreground mb-2">{table.context_summary}</div>
      <div className="space-y-2">
        {table.options.map((o) => (
          <div
            key={o.id}
            className={cn(
              "border rounded p-2",
              o.id === table.recommended_id
                ? "border-emerald-400 bg-emerald-400/5"
                : "border-border bg-card",
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="font-semibold text-[12px]">
                {o.id === table.recommended_id && <span className="text-emerald-400 mr-1">★</span>}
                {o.name}
              </div>
              <Button
                size="sm"
                variant={o.id === table.recommended_id ? "default" : "outline"}
                disabled={loading}
                onClick={() => select(o.id)}
              >
                선택
              </Button>
            </div>
            <pre className="text-[11px] font-mono whitespace-pre overflow-x-auto bg-muted/40 p-1.5 rounded my-1">
              {o.structure_sketch}
            </pre>
            <div className="text-[11px] text-muted-foreground">{o.trade_offs_one_line}</div>
          </div>
        ))}
      </div>
      <div className="mt-2 text-[11.5px] text-muted-foreground italic">
        💭 {table.recommendation_reasoning}
      </div>
    </div>
  );
}

function GapsView({ g }: { g: GapAnalysis }) {
  return (
    <div>
      <div className="font-semibold mb-1">🔍 갭 탐지 ({g.severity_summary})</div>
      {g.gaps.length === 0 ? (
        <div className="text-[11.5px] text-emerald-400">✓ 갭 없음 — {g.recommendation}</div>
      ) : (
        <div className="space-y-1">
          {g.gaps.map((gap) => (
            <div key={gap.id} className="border-l-2 border-amber-400 pl-2 text-[11.5px]">
              <strong>[{gap.kind}/{gap.severity}]</strong> {gap.title}
              <div className="text-[11px] text-muted-foreground">→ {gap.recommended_resolution}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PatternView({ p }: { p: PatternCheck }) {
  const scorePct = Math.round(p.consistency_score * 100);
  const scoreColor =
    p.consistency_score >= 0.8
      ? "text-emerald-400"
      : p.consistency_score >= 0.5
      ? "text-amber-400"
      : "text-rose-400";
  const recColor = (() => {
    switch (p.recommendation) {
      case "그대로 진행":
        return "text-emerald-400";
      case "옵션 재고려":
        return "text-rose-400";
      case "사용자 의견 필요":
        return "text-amber-400";
    }
  })();
  return (
    <div>
      <div className="font-semibold mb-1">
        🧩 패턴 검사 ({p.findings.length} findings)
        <span className={cn("ml-2 text-[11px]", scoreColor)}>{scorePct}/100</span>
      </div>
      <div className="text-[11.5px] text-muted-foreground mb-1">{p.summary}</div>
      <div className={cn("text-[11.5px] font-medium", recColor)}>→ {p.recommendation}</div>
      {p.findings.length > 0 && (
        <div className="mt-1 space-y-1">
          {p.findings.map((f) => {
            const sevColor =
              f.severity === "block"
                ? "border-rose-400"
                : f.severity === "warn"
                ? "border-amber-400"
                : "border-blue-400";
            const alignBadge =
              f.alignment === "matches" ? "✓" : f.alignment === "deviates" ? "≠" : "·";
            return (
              <div
                key={f.id}
                className={cn("border-l-2 pl-2 text-[11.5px]", sevColor)}
              >
                <strong>
                  {alignBadge} [{f.dimension}/{f.severity}]
                </strong>{" "}
                {f.title}
                <div className="text-[11px] text-muted-foreground">
                  기존: {f.evidence_existing}
                </div>
                <div className="text-[11px] text-muted-foreground">
                  제안: {f.evidence_proposed}
                </div>
                <div className="text-[11px] text-foreground/80 italic mt-0.5">
                  💡 {f.suggestion}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function NextStepView({ n }: { n: NextStep }) {
  const priorityColor = (() => {
    switch (n.priority) {
      case "critical":
        return "border-rose-400 text-rose-400";
      case "recommended":
        return "border-blue-400 text-blue-400";
      case "optional":
        return "border-muted-foreground text-muted-foreground";
    }
  })();
  const actionLabel: Record<string, string> = {
    run_interview: "③ 인터뷰",
    submit_answers: "④ 답변 제출",
    run_options: "⑤ 옵션 제시",
    accept_option: "옵션 채택",
    run_pattern_check: "⑦ 패턴 검사",
    run_gaps: "⑥ 갭 탐지",
    revise_hypothesis: "✏ 가설 수정",
    revise_options: "✏ 옵션 수정",
    run_naming: "⑧ 명명",
    run_archive: "⑨ Archive",
    run_confirm: "✓ Confirm",
    done: "🎉 완료",
    escalate_to_user: "❓ 사용자 판단",
  };
  return (
    <div>
      <div className="font-semibold mb-1">🎯 다음 단계 추천</div>
      <div className={cn("border-l-2 pl-2 mb-1", priorityColor)}>
        <strong>[{n.priority}]</strong>{" "}
        {actionLabel[n.recommended_action] ?? n.recommended_action}
      </div>
      <div className="text-[11.5px] text-muted-foreground">{n.reason_korean}</div>
      {n.alternatives.length > 0 && (
        <div className="text-[10.5px] text-muted-foreground mt-1">
          또는: {n.alternatives.map((a) => actionLabel[a] ?? a).join(" · ")}
        </div>
      )}
    </div>
  );
}

function NextEntityView({ r }: { r: NextEntityRecommendation }) {
  const runExtract = useAuthoring((s) => s.runExtract);
  const loading = useAuthoring((s) => s.loading);
  const activeRepoId = useWorkbench((s) => s.activeRepoId);

  const signalLabel: Record<string, string> = {
    pk_overlap: "PK 공유",
    same_package: "같은 패키지",
    uncovered_domain: "미처리 도메인",
    frequent_caller: "빈번 호출",
    inheritance_chain: "상속 관계",
  };
  const signalColor: Record<string, string> = {
    pk_overlap: "border-emerald-400 text-emerald-400",
    same_package: "border-blue-400 text-blue-400",
    uncovered_domain: "border-violet-400 text-violet-400",
    frequent_caller: "border-amber-400 text-amber-400",
    inheritance_chain: "border-cyan-400 text-cyan-400",
  };

  return (
    <div>
      <div className="font-semibold mb-1">
        🔮 다음 JPO 추천 ({r.candidates.length})
      </div>
      <div className="text-[11.5px] text-muted-foreground mb-1.5">
        {r.summary_korean}
      </div>
      <ol className="space-y-1.5">
        {r.candidates.map((c) => {
          const conf = Math.round(c.confidence * 100);
          return (
            <li
              key={c.fqn}
              className={cn(
                "border-l-2 pl-2 py-1 text-[11.5px]",
                signalColor[c.signal] ?? "border-muted-foreground",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <strong>{c.simple_name}</strong>
                <span className="text-[10px] text-muted-foreground">
                  [{signalLabel[c.signal] ?? c.signal}] {conf}%
                </span>
              </div>
              <div className="text-[11px] text-muted-foreground">
                {c.reason_korean}
              </div>
              <Button
                size="sm"
                variant="outline"
                className="mt-1 h-6 text-[10.5px]"
                disabled={loading}
                onClick={() => runExtract({ fqn: c.fqn, repoId: activeRepoId })}
                title={c.fqn}
              >
                ① 이 JPO 로 시작
              </Button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ComprehensiveArchiveView({ a }: { a: ComprehensiveArchive }) {
  // P1a-E: session-level archive. Reuse the .md export pattern from
  // ArchivePreview but with cyan accents to distinguish from single-entity.
  const onDownload = () => {
    const blob = new Blob([a.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const slug = a.body.title
      .replace(/[^\p{L}\p{N}-]+/gu, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 80) || "comprehensive-archive";
    link.download = `${slug}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-cyan-300">
          📚 종합 archive — {a.body.entity_sections.length} entities
        </span>
        <button
          type="button"
          onClick={onDownload}
          className="text-[10.5px] px-2 py-1 rounded border border-cyan-400/50 text-cyan-300 bg-cyan-400/5 hover:bg-cyan-400/10 transition-colors"
          title=".md 파일로 다운로드"
        >
          ⬇ .md 내려받기
        </button>
      </div>
      <article className="prose prose-invert prose-sm max-w-none bg-card p-3 rounded border border-cyan-400/30 max-h-[520px] overflow-auto
        prose-headings:my-2 prose-headings:font-semibold prose-headings:text-foreground
        prose-h1:text-[14px] prose-h2:text-[12.5px] prose-h3:text-[11.5px]
        prose-p:my-1.5 prose-p:text-[12px] prose-p:text-foreground prose-p:leading-relaxed
        prose-ul:my-1.5 prose-ol:my-1.5 prose-li:text-[12px] prose-li:my-0.5 prose-li:text-foreground
        prose-code:text-[11px] prose-code:bg-background prose-code:text-cyan-300 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
        prose-strong:text-foreground prose-em:text-muted-foreground">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{a.markdown}</ReactMarkdown>
      </article>
      {a.body.next_steps_korean.length > 0 && (
        <div className="text-[10.5px] text-muted-foreground italic">
          다음 세션 follow-up: {a.body.next_steps_korean.length} 건
        </div>
      )}
    </div>
  );
}

function NamesView({ n }: { n: NamingDecision }) {
  return (
    <div>
      <div className="font-semibold mb-1">🏷 명명 ({n.entities.length} entities)</div>
      <ul className="space-y-0.5 text-[11.5px]">
        {n.entities.map((e) => (
          <li key={e.english_id}>
            <code className="text-violet-400 font-mono">{e.english_id}</code> /{" "}
            <span className="font-semibold">{e.korean_label}</span>
            <span className="ml-2 text-[10px] text-muted-foreground">({e.role})</span>
          </li>
        ))}
      </ul>
      {n.naming_conflicts.length > 0 && (
        <div className="text-[11px] text-rose-400 mt-1">⚠ 충돌: {n.naming_conflicts.join(", ")}</div>
      )}
    </div>
  );
}

function ArchiveView({ a }: { a: ArchiveDocument }) {
  return (
    <div>
      <div className="font-semibold mb-1">📦 {a.title}</div>
      <div className="text-[11.5px] text-muted-foreground">{a.body.summary_korean}</div>
      <div className="text-[10px] mt-1 text-muted-foreground">
        markdown 미리보기는 우측 패널에서 ↗
      </div>
    </div>
  );
}

function ConfirmedView({ c }: { c: ConfirmResponse }) {
  return (
    <div className="text-emerald-400">
      ✅ {c.persisted_count} 개 entity 가 ontology DB 에 저장됨.
      <ul className="text-[11px] font-mono mt-1 space-y-0.5">
        {c.persisted_fqns.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>
    </div>
  );
}

// ── Right panel (live preview) ──────────────────────────────────────

function PreviewPanel() {
  const session = useAuthoring((s) => s.session);
  const hypothesis = useAuthoring((s) => s.hypothesis);
  const acceptedOption = useAuthoring((s) => s.acceptedOption);
  const names = useAuthoring((s) => s.names);
  const archive = useAuthoring((s) => s.archive);
  const gaps = useAuthoring((s) => s.gaps);
  const persistedFqns = useAuthoring((s) => s.persistedFqns);
  const costUsd = useAuthoring((s) => s.costUsd);

  return (
    <div className="h-full overflow-auto bg-card p-3 space-y-3 text-[12px]">
      <PreviewSection title="현재 세션">
        {session ? (
          <div className="space-y-1">
            <div><code className="text-[11px]">{session.id}</code></div>
            <div className="text-[11px] text-muted-foreground">
              operator: {session.operator_id} · branch: {session.branch_name} · status: {session.status}
            </div>
            {session.entity_focus && (
              <div className="text-[11px] text-violet-400">focus: {session.entity_focus}</div>
            )}
            <div className="text-[11px]">
              💰 누적 비용: <strong>${costUsd.toFixed(4)}</strong>
            </div>
          </div>
        ) : (
          <div className="text-muted-foreground italic text-[11px]">세션 없음</div>
        )}
      </PreviewSection>

      <PreviewSection title="가설">
        <HypothesisCard />
      </PreviewSection>

      <PreviewSection title="채택 옵션">
        {acceptedOption ? (
          <div>
            <div className="font-semibold mb-1">{acceptedOption.name}</div>
            <pre className="text-[11px] font-mono whitespace-pre overflow-x-auto bg-muted p-2 rounded my-1">
              {acceptedOption.structure_sketch}
            </pre>
            <div className="text-[11px] text-muted-foreground">{acceptedOption.trade_offs_one_line}</div>
          </div>
        ) : (
          <div className="text-muted-foreground italic text-[11px]">옵션 채택 전</div>
        )}
      </PreviewSection>

      <PreviewSection title={`엔티티 (${names?.entities.length ?? 0})`}>
        {names ? (
          <ul className="space-y-1">
            {names.entities.map((e) => {
              const fqn = `term.smoke-slab.${e.english_id.toLowerCase()}`;
              const persisted = persistedFqns.includes(fqn);
              return (
                <li key={e.english_id} className="border border-border rounded p-2 bg-muted/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-semibold">{e.korean_label}</span>
                      <code className="ml-2 text-[10px] font-mono text-muted-foreground">{e.english_id}</code>
                    </div>
                    {persisted ? (
                      <span className="text-[10px] text-emerald-400 border border-emerald-400 bg-emerald-400/10 px-1 rounded">
                        ✓ saved
                      </span>
                    ) : (
                      <span className="text-[10px] text-amber-400 border border-amber-400 bg-amber-400/10 px-1 rounded">
                        draft
                      </span>
                    )}
                  </div>
                  <div className="text-[10.5px] text-muted-foreground mt-0.5">
                    role: {e.role}
                    {e.parent_english_id && <> · parent: <code>{e.parent_english_id}</code></>}
                  </div>
                  <div className="text-[11px] mt-1">{e.description_short}</div>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="text-muted-foreground italic text-[11px]">명명 전</div>
        )}
      </PreviewSection>

      {gaps && gaps.gaps.length > 0 && (
        <PreviewSection title={`갭 (${gaps.gaps.length})`}>
          <div className="space-y-1">
            {gaps.gaps.map((g) => (
              <div
                key={g.id}
                className={cn(
                  "border-l-2 pl-2 py-0.5 text-[11.5px]",
                  g.severity === "high"
                    ? "border-rose-400"
                    : g.severity === "medium"
                    ? "border-amber-400"
                    : "border-muted-foreground",
                )}
              >
                <strong>[{g.kind}]</strong> {g.title}
                <div className="text-[10.5px] text-muted-foreground">
                  → {g.recommended_resolution}{g.demo_potential && " · 🎬 demo 후보"}
                </div>
              </div>
            ))}
          </div>
        </PreviewSection>
      )}

      {archive && (
        <PreviewSection title="Archive">
          <ArchivePreview archive={archive} />
        </PreviewSection>
      )}

      <CompletedEntitiesPreview />
    </div>
  );
}

function CompletedEntitiesPreview() {
  const completedEntities = useAuthoring((s) => s.completedEntities);
  if (completedEntities.length === 0) return null;
  return (
    <PreviewSection
      title={`이번 세션에서 완료한 Entity (${completedEntities.length})`}
    >
      <ol className="space-y-1">
        {completedEntities.map((c, i) => (
          <li
            key={`${c.jpo.class_name}-${c.completedAt}`}
            className="border-l-2 border-violet-400/60 pl-2 py-1 text-[11.5px]"
          >
            <div className="flex items-center justify-between gap-2">
              <strong className="text-violet-300">
                {i + 1}. {c.jpo.class_name}
              </strong>
              <span className="text-[10px] text-muted-foreground">
                {new Date(c.completedAt).toLocaleTimeString("ko-KR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
            <div className="text-[10.5px] text-muted-foreground">
              {c.acceptedOption ? (
                <>★ {c.acceptedOption.name}</>
              ) : c.hypothesis ? (
                <>가설: {c.hypothesis.candidate_term_korean}</>
              ) : (
                <>(미완)</>
              )}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">
              {c.archive ? "📄 archive · " : ""}
              {c.persistedFqns.length > 0
                ? `✓ persist ${c.persistedFqns.length}개`
                : c.archive
                ? "persist 안 함"
                : ""}
            </div>
          </li>
        ))}
      </ol>
    </PreviewSection>
  );
}

function ArchivePreview({ archive }: { archive: ArchiveDocument }) {
  // P4-1: render archive markdown as rich HTML via react-markdown + GFM
  // (tables, strikethrough, etc.). Provide a download button so the user
  // can export the canonical .md without losing the rendering.
  const onDownload = () => {
    const blob = new Blob([archive.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // Filename: slug from title, safe characters only.
    const slug = archive.title
      .replace(/[^\p{L}\p{N}-]+/gu, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 80) || "archive";
    a.download = `${slug}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10.5px] text-muted-foreground">
          {archive.status === "completed" ? "✓ 완료" : "⚠️ 부분 완료"}
        </span>
        <button
          type="button"
          onClick={onDownload}
          className="text-[10.5px] px-2 py-1 rounded border border-emerald-400/50 text-emerald-300 bg-emerald-400/5 hover:bg-emerald-400/10 transition-colors"
          title=".md 파일로 다운로드"
        >
          ⬇ .md 내려받기
        </button>
      </div>
      {/* X1: prose-invert 의 default text 색이 너무 흐려서 사용자가 안 보인다고 함.
          모든 element 의 text-color 를 명시적으로 foreground 로 강제 + bg 는 살짝 더 밝게. */}
      <article className="prose prose-invert prose-sm max-w-none bg-card p-3 rounded border border-border max-h-[480px] overflow-auto
        prose-headings:my-2 prose-headings:font-semibold prose-headings:text-foreground
        prose-h1:text-[14px] prose-h2:text-[12.5px] prose-h3:text-[11.5px]
        prose-p:my-1.5 prose-p:text-[12px] prose-p:text-foreground prose-p:leading-relaxed
        prose-ul:my-1.5 prose-ol:my-1.5 prose-li:text-[12px] prose-li:my-0.5 prose-li:text-foreground
        prose-table:text-[11.5px] prose-table:my-2 prose-table:border prose-table:border-border
        prose-thead:bg-muted prose-thead:border-b prose-thead:border-border
        prose-th:bg-muted prose-th:px-2 prose-th:py-1 prose-th:text-left prose-th:text-primary prose-th:font-semibold
        prose-td:px-2 prose-td:py-1 prose-td:border-t prose-td:border-border prose-td:text-foreground
        prose-code:text-[11px] prose-code:bg-background prose-code:text-primary prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
        prose-pre:text-[11px] prose-pre:bg-background prose-pre:p-2 prose-pre:rounded prose-pre:border prose-pre:border-border
        prose-strong:text-foreground prose-strong:font-semibold
        prose-em:text-foreground/90
        prose-blockquote:border-l-violet-400 prose-blockquote:text-foreground/90
        prose-hr:border-border
        prose-a:text-primary">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{archive.markdown}</ReactMarkdown>
      </article>
    </div>
  );
}

function HypothesisCard() {
  // P2-B: refresh button + contradiction indicator. The button re-runs cap 2
  // and clears downstream artifacts so the user can iterate cleanly.
  const hypothesis = useAuthoring((s) => s.hypothesis);
  const answers = useAuthoring((s) => s.answers);
  const loading = useAuthoring((s) => s.loading);
  const refresh = useAuthoring((s) => s.refreshHypothesisFromAnswers);

  if (!hypothesis) {
    return <div className="text-muted-foreground italic text-[11px]">가설 없음</div>;
  }

  // Heuristic contradiction count from absorbed answers' contradicts list.
  const contradictionCount = answers?.contradictions.length ?? 0;
  const hasAnswers = !!answers;

  return (
    <div>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex-1">
          <div className="text-[14px] font-semibold">{hypothesis.candidate_term_korean}</div>
          <code className="text-[11px] font-mono text-muted-foreground">
            {hypothesis.candidate_term_english}
          </code>
        </div>
        {hasAnswers && (
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            title="현재 답변을 반영해서 가설을 다시 검토. 옵션/갭/명명/archive 는 초기화됩니다."
            className={cn(
              "text-[10.5px] px-2 py-1 rounded border transition-colors flex-shrink-0",
              "border-violet-400/50 text-violet-300 bg-violet-400/5 hover:bg-violet-400/10",
              "disabled:opacity-40 disabled:cursor-not-allowed",
              contradictionCount > 0 && !loading && "animate-pulse",
            )}
          >
            🔄 가설 다시 보기
          </button>
        )}
      </div>
      {contradictionCount > 0 && (
        <div className="text-[10.5px] text-amber-400 mb-1">
          ⚠ 답변에서 가설과 모순 {contradictionCount}건 — 가설 다시 보기 권장
        </div>
      )}
      <div className="text-[11px] text-muted-foreground mt-1">
        role: <strong>{hypothesis.domain_role}</strong> · confidence:{" "}
        {hypothesis.confidence.toFixed(2)}
      </div>
      <div className="text-[11.5px] mt-2">{hypothesis.pk_role_summary}</div>
    </div>
  );
}

function PreviewSection({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  // P4-2-A + R2-W2-Now/X3: collapsible. 사용자가 토글을 인지 못한다고 한 피드백
  // 반영 — chevron 더 크게, hover affordance 강화, 닫혔을 때 시각적으로 명확히
  // (배경 더 흐림 + 색상 변화).
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={cn(
      "border rounded-md transition-all",
      open ? "border-border bg-background" : "border-border/50 bg-background/50",
    )}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={open ? "클릭하여 접기" : "클릭하여 펼치기"}
        className={cn(
          "w-full text-[11px] uppercase tracking-wider font-semibold px-3 py-2 border-b flex items-center justify-between transition-colors group",
          open
            ? "text-primary border-border bg-muted/40 hover:bg-muted/70"
            : "text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/40",
        )}
      >
        <span className="flex items-center gap-1.5">
          <span className="inline-block text-[13px] leading-none transition-transform group-hover:scale-110" aria-hidden>
            {open ? "▾" : "▸"}
          </span>
          {title}
        </span>
        <span className="text-[10px] font-normal text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
          {open ? "접기" : "펼치기"}
        </span>
      </button>
      {open && <div className="p-3">{children}</div>}
    </section>
  );
}

// ── Bundled HrSpec content ──────────────────────────────────────────
//
// Canonical Round 5 input, bundled inline so the prototype is always
// runnable without a file picker. Replace with a repo-aware picker in B.6.

const BUNDLED_HR_SPEC_JPO = `package com.example.slabdesign.store.sd.std.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · HR_SPEC — 열연설비사양기준 JPO.
 * Composite PK: (CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_TYPE_CD).
 * 룩업 시 ORDER_OS.CONFIRMED_PLANT_CD 의 2자리(열연위치) → HR_PLANT_CD 매칭.
 * 압연 단중 한도는 HR_MIN_WGT / HR_MAX_WGT (Step 3 별도 테이블) 에 있음.
 */
@Entity
@Table(name = "HR_SPEC")
@IdClass(HrSpecPK.class)
public class HrSpecJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "HR_PLANT_CD", length = 1)
    private String hrPlantCd;       // 열연공장코드 (확통2자리)

    @Id @Column(name = "PRODUCT_TYPE_CD", length = 4)
    private String productTypeCd;

    @Column(name = "WIDTH_LOW", precision = 10, scale = 2)
    private BigDecimal widthLow;    // step 2 폭하한 계산

    @Column(name = "WIDTH_HIGH", precision = 10, scale = 2)
    private BigDecimal widthHigh;   // step 2 폭상한 계산

    @Column(name = "LENGTH_LOW", precision = 10, scale = 2)
    private BigDecimal lengthLow;   // step 3 길이하한 계산

    @Column(name = "LENGTH_HIGH", precision = 10, scale = 2)
    private BigDecimal lengthHigh;  // step 3 길이상한 계산
}
`;
