/**
 * Authoring AI mode — Zustand store.
 *
 * One store instance per browser session. Holds the in-flight authoring
 * cycle (session + capability outputs + chat messages + UI state) so the
 * left chat and right preview stay in sync.
 *
 * Round 5 Step 14 §A "live preview" is implemented by writing every
 * capability's output back into this store; the right panel just reads.
 */

import { create } from "zustand";
import { useWorkbench } from "../store";
import {
  authoringApi,
  type AbsorbedAnswers,
  type ArchiveDocument,
  type AuthoringSession,
  type EntityHypothesis,
  type ExtractedClass,
  type ExtractedJpo,
  type GapAnalysis,
  type Hypothesis,
  type InterviewBatch,
  type NamingDecision,
  type ComprehensiveArchive,
  type EntitySnapshot,
  type NextEntityRecommendation,
  type NextStep,
  type OntologyOption,
  type OptionTable,
  type PatternCheck,
  type PriorEntitySnapshot,
  type SessionStateSnapshot,
  type ToolStreamEvent,
} from "@/lib/api/authoring";

// ── Chat message shape ──────────────────────────────────────────────

export type ChatRole = "system" | "assistant" | "user";

export type ChatKind =
  | "info"           // plain text from system
  | "extracted"      // ExtractedJpo
  | "hypothesis"     // EntityHypothesis
  | "interview"      // InterviewBatch
  | "user_answer"    // raw user text
  | "absorbed"       // AbsorbedAnswers (a quick "정리됨" card)
  | "options"        // OptionTable — clickable
  | "gaps"           // GapAnalysis
  | "pattern"        // PatternCheck (R6 cap 7)
  | "next_step"      // NextStep advisor (R6 cap 10)
  | "next_entity"    // NextEntityRecommendation (P1a-C cap 11)
  | "naming"         // NamingDecision
  | "archive"        // ArchiveDocument (markdown)
  | "comprehensive_archive" // ComprehensiveArchive (P1a-E cap 12)
  | "confirmed"      // ConfirmResponse summary
  | "error";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  kind: ChatKind;
  payload: unknown;
  ts: number;
  /** R6: per-message tool call trace (γ expandable). Only set on cap 5/6
   * messages. Each entry is one finished tool call. */
  toolTrace?: ToolTraceEntry[];
}

/** One row in the post-hoc tool trace attached to gap/option messages. */
export interface ToolTraceEntry {
  tool_name: string;
  args_summary: string;
  result_summary: string;
  duration_ms: number;
  cached: boolean;
  error: string | null;
}

export type ToolTraceStage =
  | "extract"
  | "hypothesize"
  | "options"
  | "gaps"
  | "pattern"
  | "next_entity";

/** Live trace state while a streaming capability is running (β UX). */
export interface ActiveToolTrace {
  stage: ToolTraceStage | null;
  /** Currently-running tool (set on tool_call_start, cleared on end). */
  currentTool: { tool_name: string; args_summary: string } | null;
  /** All completed tool calls so far in this run. */
  completed: ToolTraceEntry[];
}

/** Snapshot of one finished entity cycle within a session.
 *  Pushed when the user clicks "다음 Entity". `messages` / `costUsd` /
 *  `turnNo` are session-level, not per-entity, so they live elsewhere. */
/** Narrow a Hypothesis to EntityHypothesis or throw. Used by downstream
 *  capabilities (gaps/options/etc.) that haven't yet been ported to
 *  Service/Action — Phase C-3a/b is interview-only. */
function _entityOrThrow(h: Hypothesis | null | undefined): EntityHypothesis {
  if (!h) throw new Error("hypothesis required.");
  if (h.kind !== "entity") {
    throw new Error(
      `이 단계는 JPA Entity 만 지원합니다 (현재 hypothesis kind=${h.kind}).`,
    );
  }
  return h;
}

/** Kind-aware {korean, english} display pair for any Hypothesis. */
function _hypothesisDisplay(h: Hypothesis | null | undefined):
  | { korean: string; english: string; role: string }
  | null {
  if (!h) return null;
  if (h.kind === "entity") {
    return {
      korean: h.candidate_term_korean,
      english: h.candidate_term_english,
      role: h.domain_role,
    };
  }
  if (h.kind === "service") {
    return {
      korean: h.candidate_capability_korean,
      english: h.candidate_capability_english,
      role: h.service_role,
    };
  }
  return {
    korean: h.domain_verb_korean,
    english: h.domain_verb_english,
    role: h.action_kind_guess,
  };
}

export interface CompletedEntityCycle {
  /** Extracted code outline — JPA Entity (kind="jpo", full schema) or
   *  Generic (kind="generic", outline only). Phase B rename: this used to
   *  be `jpo: ExtractedJpo` when only JPA Entity was supported. */
  extracted: ExtractedClass;
  /** Phase C-3 widened to Hypothesis union (entity | service | action).
   *  Downstream caps (options/gaps/etc.) still narrow to EntityHypothesis
   *  with a kind guard until those caps land in subsequent C-3 substeps. */
  hypothesis: Hypothesis | null;
  acceptedOption: OntologyOption | null;
  names: NamingDecision | null;
  archive: ArchiveDocument | null;
  pattern: PatternCheck | null;
  gaps: GapAnalysis | null;
  persistedFqns: string[];
  completedAt: number;
}

// ── Store shape ─────────────────────────────────────────────────────

export interface AuthoringState {
  // Session + transport
  session: AuthoringSession | null;
  turnNo: number;
  loading: boolean;
  error: string | null;
  costUsd: number;

  // Capability accumulators (each set by the corresponding action)
  /** Most-recent extract output. Either ExtractedJpo (kind="jpo") for
   *  @Entity classes — feeds the full hypothesis/interview/options pipeline —
   *  or ExtractedGenericClass (kind="generic") which gates downstream
   *  capabilities (Phase B-8). Phase B rename: was `jpo: ExtractedJpo | null`. */
  extracted: ExtractedClass | null;
  /** Phase C-3 widened to Hypothesis union (entity | service | action). */
  hypothesis: Hypothesis | null;
  batch: InterviewBatch | null;
  answers: AbsorbedAnswers | null;
  optionTable: OptionTable | null;
  acceptedOption: OntologyOption | null;
  gaps: GapAnalysis | null;
  pattern: PatternCheck | null;
  names: NamingDecision | null;
  archive: ArchiveDocument | null;
  persistedFqns: string[];

  // Chat thread
  messages: ChatMessage[];

  // R6: live tool trace for the currently-streaming capability (β UX)
  activeToolTrace: ActiveToolTrace;

  // P1-a multi-entity: each entity's final artifacts pushed here on "다음 Entity"
  completedEntities: CompletedEntityCycle[];

  // Actions
  reset: () => void;
  startNewSession: (opts?: { operatorId?: string; repoId?: string }) => Promise<void>;
  runExtract: (
    args:
      | { filePath: string; fileContent: string }
      | { fqn: string; repoId?: string },
  ) => Promise<void>;
  runHypothesize: () => Promise<void>;
  refreshHypothesisFromAnswers: () => Promise<void>; // P2-B: re-run cap 2 with answers, clear downstream

  // F3 (R2-W2): generic per-stage rerun with optional user_comment.
  // Stages cascade — running an earlier stage clears all later state so
  // the user re-progresses cleanly.
  rerunStage: (
    stage: "hypothesis" | "interview" | "options" | "naming",
    comment?: string,
  ) => Promise<void>;
  runInterview: () => Promise<void>;
  submitAnswer: (text: string) => Promise<void>; // legacy single-textarea path
  submitStructuredAnswers: (
    perQuestion: Record<string, { text: string; skip?: boolean }>,
    freeform: string,
  ) => Promise<void>; // Round-5 form path (P3-A)
  runOptions: () => Promise<void>;
  runGaps: () => Promise<void>;
  runPatternCheck: () => Promise<void>;
  runNextStep: () => Promise<void>;
  /** P1-a: capture current entity into completedEntities + reset capability
   *  state so the user can move to the next JPO without losing session
   *  history (messages, cost, completedEntities). */
  startNextEntity: () => void;
  /** P1a-C cap 11: ask the LLM to recommend the next 3-5 JPOs based on
   *  graph relationships with the just-completed entities. Auto-triggered
   *  after `startNextEntity` when at least one prior exists. */
  pickNextEntity: (repoId: string) => Promise<void>;
  /** P1a-E cap 12: synthesise a session-level archive across every entity
   *  authored so far (completed + current in-progress). User-triggered from
   *  the toolbar when ≥2 entities exist. */
  runComprehensiveArchive: (repoId: string) => Promise<void>;
  /** P1a-B: load existing session by id and rebuild store from decision log. */
  resumeSession: (sessionId: string) => Promise<void>;
  selectOption: (optionId: string) => Promise<void>;
  runArchive: () => Promise<void>;
  runConfirm: (repoId: string, domain?: string) => Promise<void>;
  refreshCost: () => Promise<void>;
}

// ── Helpers ─────────────────────────────────────────────────────────

function newMsgId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function pushMessage(
  set: (fn: (s: AuthoringState) => Partial<AuthoringState>) => void,
  role: ChatRole,
  kind: ChatKind,
  payload: unknown,
  extra: { toolTrace?: ToolTraceEntry[] } = {},
): void {
  set((s) => ({
    messages: [
      ...s.messages,
      { id: newMsgId(), role, kind, payload, ts: Date.now(), ...extra },
    ],
  }));
}

/** Drain an SSE stream from any `authoringApi.*Stream`, updating
 *  `activeToolTrace` in real time so the β UX shows the current tool
 *  spinner. Resolves with the final `done` payload + completed trace.
 */
async function consumeStream(
  set: (fn: (s: AuthoringState) => Partial<AuthoringState>) => void,
  stage: ToolTraceStage,
  stream: AsyncGenerator<ToolStreamEvent>,
): Promise<{ output: unknown; completed: ToolTraceEntry[] }> {
  set(() => ({
    activeToolTrace: { stage, currentTool: null, completed: [] },
  }));
  const completed: ToolTraceEntry[] = [];
  // Map tool_call_start payloads (keyed by tool_name) to their args_summary
  // so we can stitch them onto the matching tool_call_end.
  const pendingArgs: Record<string, string> = {};
  let output: unknown = null;

  try {
    for await (const ev of stream) {
      if (ev.type === "tool_call_start") {
        pendingArgs[ev.tool_name] = ev.args_summary;
        set(() => ({
          activeToolTrace: {
            stage,
            currentTool: { tool_name: ev.tool_name, args_summary: ev.args_summary },
            completed: [...completed],
          },
        }));
      } else if (ev.type === "tool_call_end") {
        const entry: ToolTraceEntry = {
          tool_name: ev.tool_name,
          args_summary: pendingArgs[ev.tool_name] ?? "",
          result_summary: ev.result_summary,
          duration_ms: ev.duration_ms,
          cached: ev.cached,
          error: ev.error,
        };
        completed.push(entry);
        delete pendingArgs[ev.tool_name];
        set(() => ({
          activeToolTrace: {
            stage,
            currentTool: null,
            completed: [...completed],
          },
        }));
      } else if (ev.type === "done") {
        output = ev.output;
      } else if (ev.type === "error") {
        throw new Error(ev.message);
      }
      // stream_open / heartbeat — ignore
    }
  } finally {
    set(() => ({
      activeToolTrace: { stage: null, currentTool: null, completed: [] },
    }));
  }
  return { output, completed };
}

async function withLoading<T>(
  set: (fn: (s: AuthoringState) => Partial<AuthoringState>) => void,
  fn: () => Promise<T>,
): Promise<T | undefined> {
  set(() => ({ loading: true, error: null }));
  try {
    const out = await fn();
    set(() => ({ loading: false }));
    return out;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    set(() => ({ loading: false, error: msg }));
    pushMessage(set, "system", "error", msg);
    return undefined;
  }
}

function requireSession(state: AuthoringState): AuthoringSession {
  if (!state.session) throw new Error("No active session — call startNewSession() first.");
  return state.session;
}

// ── Store implementation ────────────────────────────────────────────

export const useAuthoring = create<AuthoringState>((set, get) => ({
  session: null,
  turnNo: 0,
  loading: false,
  error: null,
  costUsd: 0,

  extracted: null,
  hypothesis: null,
  batch: null,
  answers: null,
  optionTable: null,
  acceptedOption: null,
  gaps: null,
  pattern: null,
  names: null,
  archive: null,
  persistedFqns: [],

  messages: [],
  activeToolTrace: { stage: null, currentTool: null, completed: [] },
  completedEntities: [],

  reset: () => {
    set(() => ({
      session: null,
      turnNo: 0,
      loading: false,
      error: null,
      costUsd: 0,
      extracted: null,
      hypothesis: null,
      batch: null,
      answers: null,
      optionTable: null,
      acceptedOption: null,
      gaps: null,
      pattern: null,
      names: null,
      archive: null,
      persistedFqns: [],
      messages: [],
      activeToolTrace: { stage: null, currentTool: null, completed: [] },
      completedEntities: [],
    }));
  },

  startNewSession: async (opts) => {
    await withLoading(set, async () => {
      get().reset();
      const sess = await authoringApi.createSession({
        operator_id: opts?.operatorId ?? "default",
        repo_id: opts?.repoId,
      });
      set(() => ({ session: sess, turnNo: 0 }));
      pushMessage(
        set,
        "system",
        "info",
        `세션 시작 (id=${sess.id.slice(0, 8)}…) — 코드 파일을 추출하면 인터뷰가 시작됩니다.`,
      );
    });
  },

  runExtract: async (args) => {
    await withLoading(set, async () => {
      const sess = requireSession(get());
      const turn = get().turnNo + 1;
      const req: Parameters<typeof authoringApi.extractStream>[1] = {
        turn_no: turn,
      };
      if ("fqn" in args) {
        req.fqn = args.fqn;
        req.repo_id = args.repoId ?? null;
      } else {
        req.file_path = args.filePath;
        req.file_content = args.fileContent;
      }
      const trace = await consumeStream(
        set,
        "extract",
        authoringApi.extractStream(sess.id, req),
      );
      const out = trace.output as ExtractedClass;
      set(() => ({ extracted: out, turnNo: turn }));
      pushMessage(set, "assistant", "extracted", out, {
        toolTrace: trace.completed,
      });
      await get().refreshCost();
    });
  },

  runHypothesize: async () => {
    await withLoading(set, async () => {
      const { extracted, session } = get();
      if (!session || !extracted) throw new Error("Run extract first.");
      // Phase C-2: hypothesis dispatcher accepts jpo / service / action.
      // ExtractedGenericClass (kind="generic") has no hypothesis prompt yet —
      // the toolbar gate prevents it from reaching this code path.
      if (extracted.kind === "generic") {
        throw new Error(
          "Generic 클래스 hypothesis 는 미지원 — JPA Entity 또는 Service / Action 클래스를 선택하세요.",
        );
      }
      const turn = get().turnNo + 1;
      const trace = await consumeStream(
        set,
        "hypothesize",
        authoringApi.hypothesizeStream(session.id, {
          turn_no: turn,
          extracted,
        }),
      );
      const out = trace.output as Hypothesis;
      // Phase C-3a: interview accepts all hypothesis kinds (entity/service/
      // action) via the Hypothesis union. Downstream caps (options/gaps/
      // naming) remain entity-only and are gated separately by `isEntityKind`
      // in the toolbar, so it's safe to surface service/action hypotheses
      // here without breaking the pipeline.
      set(() => ({ hypothesis: out, turnNo: turn }));
      pushMessage(set, "assistant", "hypothesis", out, {
        toolTrace: trace.completed,
      });
      await get().refreshCost();
    });
  },

  refreshHypothesisFromAnswers: async () => {
    // P2-B: re-run hypothesis with current answers in mind, then clear all
    // downstream artifacts (options/gaps/names/archive). The user explicitly
    // wanted this Round-5 pattern back: "내가 너의 질문이 이상하면 새로운 내용을
    // 알려주면서, 너가 새롭게 검토하고 리프레시 하는 흐름이 좋았는데".
    //
    // For now we re-call cap 2 with the same JPO (the prompt itself doesn't
    // currently fold answers in — that's a follow-up). The visible benefit is
    // resetting downstream state so the user can re-run options/gaps/naming
    // against the new hypothesis without confusion.
    await withLoading(set, async () => {
      const { extracted, session, answers } = get();
      if (!session || !extracted) throw new Error("Run extract first.");
      if (extracted.kind === "generic") {
        throw new Error("Generic 클래스 hypothesis 는 미지원.");
      }
      pushMessage(
        set,
        "user",
        "info",
        answers
          ? "🔄 답변을 반영해서 가설을 다시 검토합니다 — 옵션/갭/명명/archive 가 초기화됩니다."
          : "🔄 가설을 다시 생성합니다.",
      );
      const turn = get().turnNo + 1;
      const trace = await consumeStream(
        set,
        "hypothesize",
        authoringApi.hypothesizeStream(session.id, {
          turn_no: turn,
          extracted,
        }),
      );
      const out = trace.output as Hypothesis;
      set(() => ({
        hypothesis: out,
        turnNo: turn,
        // Clear everything downstream of hypothesis so the user can re-run.
        optionTable: null,
        acceptedOption: null,
        gaps: null,
        pattern: null,
        names: null,
        archive: null,
        persistedFqns: [],
      }));
      pushMessage(set, "assistant", "hypothesis", out, {
        toolTrace: trace.completed,
      });
      await get().refreshCost();
    });
  },

  runInterview: async () => {
    await withLoading(set, async () => {
      const { hypothesis, session } = get();
      if (!session || !hypothesis) throw new Error("Run hypothesize first.");
      const turn = get().turnNo + 1;
      const out = await authoringApi.interview(session.id, {
        turn_no: turn,
        hypothesis,
      });
      set(() => ({ batch: out, turnNo: turn }));
      pushMessage(set, "assistant", "interview", out);
      await get().refreshCost();
    });
  },

  submitAnswer: async (text) => {
    // Legacy free-form path — kept only for backward compatibility with the
    // single-textarea AnswerComposer (now removed). New flow goes through
    // submitStructuredAnswers below.
    await withLoading(set, async () => {
      const { batch, session } = get();
      if (!session || !batch) throw new Error("No interview batch — run interview first.");
      pushMessage(set, "user", "user_answer", text);
      const turn = get().turnNo + 1;
      const out = await authoringApi.absorb(session.id, {
        turn_no: turn,
        batch,
        user_reply: text,
      });
      set(() => ({ answers: out, turnNo: turn }));
      pushMessage(set, "assistant", "absorbed", out);
      await get().refreshCost();
    });
  },

  submitStructuredAnswers: async (perQuestion, freeform) => {
    // Round-2 flow (P3-A): user already supplied per-question answers via the
    // Round-5-style form, so we can build AbsorbedAnswers directly without
    // calling cap 4 (answer_absorber). Saves ~$0.02 per cycle and removes
    // a 10s LLM round-trip — the trade-off is that contradiction detection
    // moves to the explicit "refresh hypothesis" button (P2-B).
    const { batch, session } = get();
    if (!session || !batch) throw new Error("No interview batch — run interview first.");

    // Build per-question dict — every question id from the batch is present.
    const per_question: AbsorbedAnswers["per_question"] = {};
    const unanswered: string[] = [];
    for (const q of batch.questions) {
      const entry = perQuestion[q.id];
      const text = (entry?.text ?? "").trim();
      const skipped = entry?.skip === true;
      if (!text || skipped) {
        per_question[q.id] = {
          question_id: q.id,
          raw_text: "",
          normalized: "",
          is_unknown: true,
          picked_option: null,
          contradicts_my_guess: false,
          contradicts_note: null,
        };
        unanswered.push(q.id);
        continue;
      }
      // Heuristic: if the question had options and the answer text matches
      // (case-insensitive substring) one of them, treat it as a pick.
      let picked: string | null = null;
      if (q.options) {
        const lower = text.toLowerCase();
        picked = q.options.find((o) => lower.includes(o.toLowerCase())) ?? null;
      }
      per_question[q.id] = {
        question_id: q.id,
        raw_text: text,
        normalized: text,
        is_unknown: false,
        picked_option: picked,
        contradicts_my_guess: false, // detected later by gap_detector / refresh
        contradicts_note: null,
      };
    }

    const emergent_facts = freeform.trim() ? [freeform.trim()] : [];
    const out: AbsorbedAnswers = {
      per_question,
      unanswered,
      emergent_facts,
      contradictions: [],
    };

    // Compose a chat-friendly transcript so the chat thread still reads naturally.
    const transcriptLines: string[] = [];
    for (const q of batch.questions) {
      const ans = per_question[q.id];
      if (ans.is_unknown) continue;
      transcriptLines.push(`• ${q.id}: ${ans.normalized}`);
    }
    if (emergent_facts.length > 0) {
      transcriptLines.push(`• 추가: ${emergent_facts[0]}`);
    }
    pushMessage(set, "user", "user_answer", transcriptLines.join("\n") || "(모두 모름/skip)");

    const turn = get().turnNo + 1;
    set(() => ({ answers: out, turnNo: turn }));
    pushMessage(set, "assistant", "absorbed", out);
    // No /absorb call — saved one LLM round-trip.
  },

  runOptions: async () => {
    await withLoading(set, async () => {
      const { hypothesis, answers, session } = get();
      if (!session || !hypothesis || !answers)
        throw new Error("Need hypothesis + answers before options.");
      const entityH = _entityOrThrow(hypothesis);
      const turn = get().turnNo + 1;

      const trace = await consumeStream(
        set,
        "options",
        authoringApi.optionsStream(session.id, {
          turn_no: turn,
          hypothesis: entityH,
          answers,
        }),
      );
      const out = trace.output as OptionTable;
      set(() => ({ optionTable: out, turnNo: turn }));
      pushMessage(
        set,
        "assistant",
        "options",
        out,
        { toolTrace: trace.completed },
      );
      await get().refreshCost();
    });
  },

  runGaps: async () => {
    await withLoading(set, async () => {
      const { extracted, hypothesis, answers, session } = get();
      if (!session || !extracted || !hypothesis || !answers)
        throw new Error("Need extracted + hypothesis + answers before gaps.");
      if (extracted.kind !== "jpo") {
        throw new Error("Gaps 는 현재 JPA Entity 만 지원합니다.");
      }
      const entityH = _entityOrThrow(hypothesis);
      const turn = get().turnNo + 1;

      const trace = await consumeStream(
        set,
        "gaps",
        authoringApi.gapsStream(session.id, {
          turn_no: turn,
          extracted_jpo: extracted,
          hypothesis: entityH,
          answers,
        }),
      );
      const out = trace.output as GapAnalysis;
      set(() => ({ gaps: out, turnNo: turn }));
      pushMessage(
        set,
        "assistant",
        "gaps",
        out,
        { toolTrace: trace.completed },
      );
      await get().refreshCost();
    });
  },

  runNextStep: async () => {
    // R6 cap 10 — pure state-based advisor. No graph tools, no SSE; just a
    // quick Sonnet call summarising "what should the user do next?"
    await withLoading(set, async () => {
      const s = get();
      if (!s.session) throw new Error("No session.");
      const turn = s.turnNo + 1;
      const snapshot: SessionStateSnapshot = {
        has_hypothesis: !!s.hypothesis,
        hypothesis_confidence: s.hypothesis?.confidence ?? null,
        has_interview_batch: !!s.batch,
        has_answers: !!s.answers,
        has_option_table: !!s.optionTable,
        has_accepted_option: !!s.acceptedOption,
        has_gaps: !!s.gaps,
        gaps_block_modeling: s.gaps?.blocks_modeling ?? false,
        gap_high_count: s.gaps?.gaps.filter((g) => g.severity === "high").length ?? 0,
        has_pattern_check: !!s.pattern,
        pattern_recommendation: s.pattern?.recommendation ?? null,
        has_names: !!s.names,
        has_archive: !!s.archive,
        persisted_fqn_count: s.persistedFqns.length,
      };
      const out = await authoringApi.nextStep(s.session.id, {
        turn_no: turn,
        state: snapshot,
      });
      set(() => ({ turnNo: turn }));
      pushMessage(set, "assistant", "next_step", out);
      await get().refreshCost();
    });
  },

  startNextEntity: () => {
    // P1-a — capture current entity into completedEntities + reset
    // capability state. Session, messages, turnNo, costUsd, and
    // completedEntities itself are kept (session-level state).
    const s = get();
    if (!s.extracted) {
      // Nothing to capture (no entity processed yet) — ignore.
      return;
    }
    const cycle: CompletedEntityCycle = {
      extracted: s.extracted,
      hypothesis: s.hypothesis,
      acceptedOption: s.acceptedOption,
      names: s.names,
      archive: s.archive,
      pattern: s.pattern,
      gaps: s.gaps,
      persistedFqns: s.persistedFqns,
      completedAt: Date.now(),
    };
    const turn = s.turnNo + 1;
    set(() => ({
      completedEntities: [...s.completedEntities, cycle],
      turnNo: turn,
      // Reset per-entity state
      extracted: null,
      hypothesis: null,
      batch: null,
      answers: null,
      optionTable: null,
      acceptedOption: null,
      gaps: null,
      pattern: null,
      names: null,
      archive: null,
      persistedFqns: [],
    }));
    // P1a-B: persist a backend marker so reload can split the cycle.
    if (s.session) {
      authoringApi
        .markNextEntity(s.session.id, { turn_no: turn })
        .catch(() => {
          // non-critical — only affects resume cycle splitting
        });
    }
    pushMessage(
      set,
      "system",
      "info",
      `✓ ${cycle.extracted.class_name} 마무리 — 다음 Entity 추천 받는 중...`,
    );
  },

  resumeSession: async (sessionId) => {
    // P1a-B — fetch the rebuilt state from backend and populate the store.
    // Messages aren't reconstructed (chat thread is ephemeral); only
    // structured artifacts.
    await withLoading(set, async () => {
      const r = await authoringApi.replay(sessionId);
      // Backend keeps the legacy "jpo" field name in replay payloads (Phase B
      // boundary translation; Phase C will unify when backend gains Service /
      // Action schemas). Frontend store uses `extracted: ExtractedClass`
      // throughout — cast at the boundary, default to kind="jpo" so older
      // payloads without the discriminator still deserialize correctly.
      const cycles: CompletedEntityCycle[] = r.completed_entities.map(
        (c) => ({
          extracted: c.jpo as ExtractedClass,
          hypothesis: c.hypothesis,
          acceptedOption: c.accepted_option,
          names: c.names,
          archive: c.archive,
          pattern: c.pattern,
          gaps: c.gaps,
          persistedFqns: c.persisted_fqns,
          completedAt: c.completed_at ? Date.parse(c.completed_at) : Date.now(),
        }),
      );
      set(() => ({
        session: r.session,
        turnNo: r.decision_count,
        loading: false,
        error: null,
        costUsd: r.cost_total_usd,
        // Current cycle artifacts — translate backend `jpo` → store `extracted`.
        extracted: (r.current.jpo as ExtractedClass | null) ?? null,
        hypothesis: r.current.hypothesis,
        batch: r.current.batch,
        answers: r.current.answers,
        optionTable: r.current.option_table,
        acceptedOption: r.current.accepted_option,
        gaps: r.current.gaps,
        pattern: r.current.pattern,
        names: r.current.names,
        archive: r.current.archive,
        persistedFqns: r.current.persisted_fqns,
        // History
        completedEntities: cycles,
        messages: [],
        activeToolTrace: { stage: null, currentTool: null, completed: [] },
      }));
      pushMessage(
        set,
        "system",
        "info",
        `↻ 세션 ${sessionId.slice(0, 8)}… 이어서 진행 (완료 ${cycles.length} entity, 현재 ${r.current.jpo ? (r.current.jpo as ExtractedClass).class_name : "(없음)"})`,
      );
      // P3 polish: replay history into chat as a compact summary so the
      // user sees what was done before the reload. Skipping full per-cap
      // re-render — just a 1-line per entity recap.
      for (const c of cycles) {
        const accepted = c.acceptedOption?.name ?? "옵션 미채택";
        const persisted =
          c.persistedFqns.length > 0
            ? ` ✓ persist ${c.persistedFqns.length}`
            : "";
        pushMessage(
          set,
          "system",
          "info",
          `· ${c.extracted.class_name} → ${_hypothesisDisplay(c.hypothesis)?.korean ?? "(미정)"} / ${accepted}${persisted}`,
        );
      }
      if (r.current.jpo) {
        const cur = r.current.jpo as ExtractedClass;
        pushMessage(
          set,
          "system",
          "info",
          `· 현재 진행 중: ${cur.class_name}${r.current.hypothesis ? ` / 가설 = ${r.current.hypothesis.candidate_term_korean}` : ""}`,
        );
      }
    });
  },

  runComprehensiveArchive: async (repoId) => {
    // P1a-E cap 12 — session-level synthesis. Includes current in-progress
    // entity (if any artifacts) so the user sees a snapshot of the whole
    // session, not just confirmed entities.
    await withLoading(set, async () => {
      const s = get();
      if (!s.session) throw new Error("No session.");
      const entities: EntitySnapshot[] = [];
      // Completed cycles first
      for (const c of s.completedEntities) {
        const cd = _hypothesisDisplay(c.hypothesis);
        entities.push({
          class_name: c.extracted.class_name,
          package: c.extracted.package,
          candidate_term_korean: cd?.korean ?? "(미정)",
          candidate_term_english: cd?.english ?? c.extracted.class_name,
          domain_role: cd?.role ?? "unknown",
          accepted_option_name: c.acceptedOption?.name ?? null,
          accepted_option_alignment: c.acceptedOption?.domain_alignment ?? null,
          accepted_option_structure: c.acceptedOption?.structure_sketch ?? null,
          persisted_fqns: c.persistedFqns,
          gap_titles: c.gaps?.gaps.map((g) => g.title) ?? [],
          pattern_findings_summary: c.pattern
            ? `${c.pattern.findings.length} findings, score ${c.pattern.consistency_score.toFixed(2)}, ${c.pattern.recommendation}`
            : null,
          archive_excerpt: c.archive?.markdown?.slice(0, 300) ?? null,
          in_progress: false,
        });
      }
      // Then current in-progress (if at least extracted)
      if (s.extracted) {
        const sd = _hypothesisDisplay(s.hypothesis);
        entities.push({
          class_name: s.extracted.class_name,
          package: s.extracted.package,
          candidate_term_korean: sd?.korean ?? "(미정)",
          candidate_term_english: sd?.english ?? s.extracted.class_name,
          domain_role: sd?.role ?? "unknown",
          accepted_option_name: s.acceptedOption?.name ?? null,
          accepted_option_alignment: s.acceptedOption?.domain_alignment ?? null,
          accepted_option_structure: s.acceptedOption?.structure_sketch ?? null,
          persisted_fqns: s.persistedFqns,
          gap_titles: s.gaps?.gaps.map((g) => g.title) ?? [],
          pattern_findings_summary: s.pattern
            ? `${s.pattern.findings.length} findings, score ${s.pattern.consistency_score.toFixed(2)}, ${s.pattern.recommendation}`
            : null,
          archive_excerpt: s.archive?.markdown?.slice(0, 300) ?? null,
          in_progress: true,
        });
      }
      if (entities.length === 0) {
        throw new Error("No entities to archive.");
      }
      const turn = s.turnNo + 1;
      const out = await authoringApi.comprehensiveArchive(s.session.id, {
        turn_no: turn,
        repo_id: repoId,
        entities,
      });
      set(() => ({ turnNo: turn }));
      pushMessage(set, "assistant", "comprehensive_archive", out);
      await get().refreshCost();
    });
  },

  pickNextEntity: async (repoId) => {
    // P1a-C cap 11 — graph-tool driven. Reads completedEntities + repo_id,
    // returns 3-5 candidate JPOs with reasons. Surfaced as a chat message
    // with clickable "이 JPO 로 시작" buttons.
    await withLoading(set, async () => {
      const s = get();
      if (!s.session) throw new Error("No session.");
      const completed_entity_fqns: string[] = s.completedEntities
        .map((c) => {
          const pkg = c.extracted.package;
          const cls = c.extracted.class_name;
          return pkg ? `${pkg}.${cls}` : cls;
        })
        .filter((fqn) => fqn.length > 0);
      const confirmed_term_fqns: string[] = s.completedEntities.flatMap(
        (c) => c.persistedFqns,
      );

      const turn = s.turnNo + 1;
      const trace = await consumeStream(
        set,
        "next_entity",
        authoringApi.nextEntityStream(s.session.id, {
          turn_no: turn,
          repo_id: repoId,
          completed_entity_fqns,
          confirmed_term_fqns,
        }),
      );
      const out = trace.output as NextEntityRecommendation;
      set(() => ({ turnNo: turn }));
      pushMessage(set, "assistant", "next_entity", out, {
        toolTrace: trace.completed,
      });
      await get().refreshCost();
    });
  },

  runPatternCheck: async () => {
    // R6 cap 7 — sits between option-acceptance and naming. Verifies the
    // accepted shape against existing ontology patterns. Empty findings
    // is a valid (and common) result; the user proceeds to naming either
    // way. P1a-D: also passes in-session prior entities so the agent can
    // detect cross-entity patterns within the session.
    await withLoading(set, async () => {
      const { hypothesis, acceptedOption, session, completedEntities } = get();
      if (!session || !hypothesis || !acceptedOption)
        throw new Error("Accept an option before pattern check.");
      const entityH = _entityOrThrow(hypothesis);
      const turn = get().turnNo + 1;
      const priors: PriorEntitySnapshot[] = completedEntities.map((c) => {
        const cd = _hypothesisDisplay(c.hypothesis);
        return {
          class_name: c.extracted.class_name,
          candidate_term_korean: cd?.korean ?? "(미정)",
          candidate_term_english: cd?.english ?? c.extracted.class_name,
          domain_role: cd?.role ?? "unknown",
          accepted_option_name: c.acceptedOption?.name ?? null,
          accepted_option_structure: c.acceptedOption?.structure_sketch ?? null,
          accepted_option_alignment: c.acceptedOption?.domain_alignment ?? null,
          persisted_fqns: c.persistedFqns,
          archive_summary: c.archive
            ? c.archive.markdown.split("\n").slice(0, 3).join(" / ")
            : null,
        };
      });
      const trace = await consumeStream(
        set,
        "pattern",
        authoringApi.patternStream(session.id, {
          turn_no: turn,
          hypothesis: entityH,
          accepted_option: acceptedOption,
          prior_session_entities: priors.length > 0 ? priors : null,
        }),
      );
      const out = trace.output as PatternCheck;
      set(() => ({ pattern: out, turnNo: turn }));
      pushMessage(set, "assistant", "pattern", out, {
        toolTrace: trace.completed,
      });
      await get().refreshCost();
    });
  },

  selectOption: async (optionId) => {
    await withLoading(set, async () => {
      const { hypothesis, optionTable, session } = get();
      if (!session || !hypothesis || !optionTable)
        throw new Error("No options to select from.");
      const entityH = _entityOrThrow(hypothesis);
      const accepted = optionTable.options.find((o) => o.id === optionId);
      if (!accepted) throw new Error(`Option ${optionId} not in current table`);
      set(() => ({ acceptedOption: accepted }));
      pushMessage(set, "user", "info", `옵션 채택: ${accepted.name}`);

      // Chain immediately into naming.
      const turn = get().turnNo + 1;
      const namingOut = await authoringApi.naming(session.id, {
        turn_no: turn,
        hypothesis: entityH,
        accepted_option: accepted,
      });
      set(() => ({ names: namingOut, turnNo: turn }));
      pushMessage(set, "assistant", "naming", namingOut);
      await get().refreshCost();
    });
  },

  runArchive: async () => {
    await withLoading(set, async () => {
      const { hypothesis, answers, acceptedOption, names, gaps, session } = get();
      if (!session || !hypothesis || !answers || !acceptedOption || !names)
        throw new Error("Need hypothesis + answers + accepted option + names before archive.");
      const entityH = _entityOrThrow(hypothesis);
      const turn = get().turnNo + 1;
      const out = await authoringApi.archive(session.id, {
        turn_no: turn,
        hypothesis: entityH,
        answers,
        accepted_option: acceptedOption,
        names,
        gaps,
        step_number: 1,
      });
      set(() => ({ archive: out, turnNo: turn }));
      pushMessage(set, "assistant", "archive", out);
      await get().refreshCost();
    });
  },

  runConfirm: async (repoId, domain) => {
    await withLoading(set, async () => {
      const { acceptedOption, names, session } = get();
      if (!session || !acceptedOption || !names)
        throw new Error("Need names + acceptedOption before confirm.");
      const turn = get().turnNo + 1;
      const out = await authoringApi.confirm(session.id, {
        turn_no: turn,
        names,
        accepted_option: acceptedOption,
        repo_id: repoId,
        domain,
      });
      set(() => ({ persistedFqns: out.persisted_fqns, turnNo: turn }));
      pushMessage(set, "assistant", "confirmed", out);
      // Queue 가 새 confirmed entity 를 즉시 surface 하도록 trigger.
      try { useWorkbench.getState().bumpQueueRefresh(); } catch { /* ignore */ }
      await get().refreshCost();
    });
  },

  refreshCost: async () => {
    const { session } = get();
    if (!session) return;
    try {
      const cost = await authoringApi.getCost(session.id);
      set(() => ({ costUsd: cost.total_usd }));
    } catch {
      // non-fatal
    }
  },

  rerunStage: async (stage, comment) => {
    // F3 / R2-W2: rerun a specific stage with optional user_comment, clear
    // every downstream stage so the user re-progresses cleanly. This is the
    // "사용자 정정 → AI 재검토" cascading pattern from Round 5.
    await withLoading(set, async () => {
      const { extracted, hypothesis, batch, answers, acceptedOption, session } = get();
      if (!session) throw new Error("No session.");

      const tag = comment?.trim()
        ? `🔄 ${stage} 재실행 (코멘트: "${comment.trim().slice(0, 60)}${comment.trim().length > 60 ? "…" : ""}")`
        : `🔄 ${stage} 단순 재실행`;
      pushMessage(set, "user", "info", tag);

      const turn = get().turnNo + 1;

      if (stage === "hypothesis") {
        if (!extracted) throw new Error("extracted required");
        if (extracted.kind === "generic") {
          throw new Error("Generic 클래스 hypothesis rerun 은 미지원.");
        }
        const trace = await consumeStream(
          set,
          "hypothesize",
          authoringApi.hypothesizeStream(session.id, {
            turn_no: turn,
            extracted,
            user_comment: comment,
          }),
        );
        const out = trace.output as Hypothesis;
        // Phase C-3a: surface all hypothesis kinds (interview accepts the union).
        // Downstream entity-only caps are gated by `isEntityKind` in the toolbar.
        set(() => ({
          hypothesis: out,
          turnNo: turn,
          batch: null,
          answers: null,
          optionTable: null,
          acceptedOption: null,
          gaps: null,
          names: null,
          archive: null,
          persistedFqns: [],
        }));
        pushMessage(set, "assistant", "hypothesis", out, {
          toolTrace: trace.completed,
        });
      } else if (stage === "interview") {
        if (!hypothesis) throw new Error("hypothesis required");
        const out = await authoringApi.interview(session.id, {
          turn_no: turn,
          hypothesis,
          user_comment: comment,
        });
        set(() => ({
          batch: out,
          turnNo: turn,
          answers: null,
          optionTable: null,
          acceptedOption: null,
          gaps: null,
          names: null,
          archive: null,
          persistedFqns: [],
        }));
        pushMessage(set, "assistant", "interview", out);
      } else if (stage === "options") {
        if (!hypothesis || !answers) throw new Error("hypothesis + answers required");
        const entityH = _entityOrThrow(hypothesis);
        const trace = await consumeStream(
          set,
          "options",
          authoringApi.optionsStream(session.id, {
            turn_no: turn,
            hypothesis: entityH,
            answers,
            user_comment: comment,
          }),
        );
        const out = trace.output as OptionTable;
        set(() => ({
          optionTable: out,
          turnNo: turn,
          acceptedOption: null,
          gaps: null,
          names: null,
          archive: null,
          persistedFqns: [],
        }));
        pushMessage(set, "assistant", "options", out, {
          toolTrace: trace.completed,
        });
      } else if (stage === "naming") {
        if (!hypothesis || !acceptedOption) throw new Error("hypothesis + acceptedOption required");
        const entityH = _entityOrThrow(hypothesis);
        const out = await authoringApi.naming(session.id, {
          turn_no: turn,
          hypothesis: entityH,
          accepted_option: acceptedOption,
          user_comment: comment,
        });
        set(() => ({
          names: out,
          turnNo: turn,
          archive: null,
          persistedFqns: [],
        }));
        pushMessage(set, "assistant", "naming", out);
      }

      // Avoid unused-variable warning for batch — used implicitly via
      // requireSession path; keep the destructuring above clean.
      void batch;

      await get().refreshCost();
    });
  },
}));
