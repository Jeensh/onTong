"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send,
  Square,
  FileText,
  Check,
  X,
  Sparkles,
  Plus,
  MessageSquare,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  Trash2,
  Search,
  MessageCircleQuestion,
  Pencil,
  Zap,
  Loader2,
  CircleCheck,
  Brain,
  Paperclip,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat, type SSECallbacks, type ThinkingStep } from "@/lib/api/sseClient";
import { fetchFile } from "@/lib/api/wiki";
import { fetchSkills, matchSkill } from "@/lib/api/skills";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { toast } from "sonner";
import type { SkillMeta } from "@/types";

// ── Types ────────────────────────────────────────────────────────────

interface SourceItem {
  doc: string;
  relevance: number;
  updated?: string;
  updated_by?: string;
  status?: string;
}

interface ApprovalData {
  action_id: string;
  action_type: string;
  path: string;
  diff_preview: string;
}

interface ThinkingStepState {
  step: string;
  label: string;
  detail: string;
  status: "start" | "done";
}

interface ConflictWarning {
  details: string;
  conflicting_docs: string[];
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceItem[];
  approval?: ApprovalData;
  approvalResolved?: "approved" | "rejected";
  isStreaming?: boolean;
  error?: string;
  thinkingSteps?: ThinkingStepState[];
  conflictWarning?: ConflictWarning;
}

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
}

// ── Component ────────────────────────────────────────────────────────

export function AICopilot() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => [
    createSession(),
  ]);
  const [activeSessionId, setActiveSessionId] = useState(sessions[0].id);
  const [showSessionList, setShowSessionList] = useState(false);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<SkillMeta | null>(null);
  const [sessionSkill, setSessionSkill] = useState<SkillMeta | null>(null); // persists across follow-ups
  const [showSkillPicker, setShowSkillPicker] = useState(false);
  const [skillList, setSkillList] = useState<SkillMeta[]>([]);
  const [skillSuggestion, setSkillSuggestion] = useState<SkillMeta | null>(null);
  const [dismissedSkills, setDismissedSkills] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set<string>();
    try {
      const saved = localStorage.getItem("ontong:dismissed-skills");
      return saved ? new Set(JSON.parse(saved) as string[]) : new Set<string>();
    } catch { return new Set<string>(); }
  });
  const [skillSearch, setSkillSearch] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const tabs = useWorkspaceStore((s) => s.tabs);
  const refreshTree = useWorkspaceStore((s) => s.refreshTree);
  const setAgentDiff = useWorkspaceStore((s) => s.setAgentDiff);

  const activeSession = sessions.find((s) => s.id === activeSessionId)!;
  const messages = activeSession.messages;

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when switching sessions
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeSessionId]);

  // Load skill list for picker (refresh periodically to pick up toggle changes)
  const refreshSkillList = useCallback(() => {
    fetchSkills()
      .then((res) => setSkillList([...res.personal, ...res.system]))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshSkillList();
  }, [refreshSkillList]);

  // Persist dismissed skills to localStorage
  useEffect(() => {
    localStorage.setItem("ontong:dismissed-skills", JSON.stringify([...dismissedSkills]));
  }, [dismissedSkills]);

  // Auto-suggest skill based on input (debounced)
  useEffect(() => {
    if (!input.trim() || input.length < 3 || selectedSkill || sessionSkill) {
      setSkillSuggestion(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await matchSkill(input);
        if (res.match && !dismissedSkills.has(res.match.skill.path)) {
          setSkillSuggestion(res.match.skill);
        } else {
          setSkillSuggestion(null);
        }
      } catch {
        setSkillSuggestion(null);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [input, selectedSkill, sessionSkill, dismissedSkills]);

  const updateMessages = useCallback(
    (updater: (msgs: ChatMessage[]) => ChatMessage[]) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, messages: updater(s.messages) }
            : s
        )
      );
    },
    [activeSessionId]
  );

  const updateLastAssistant = useCallback(
    (updater: (msg: ChatMessage) => ChatMessage) => {
      updateMessages((msgs) => {
        const idx = msgs.findLastIndex((m) => m.role === "assistant");
        if (idx === -1) return msgs;
        const updated = [...msgs];
        updated[idx] = updater(updated[idx]);
        return updated;
      });
    },
    [updateMessages]
  );

  const updateSessionTitle = useCallback(
    (text: string) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId && s.title === "새 대화"
            ? { ...s, title: text.slice(0, 30) + (text.length > 30 ? "..." : "") }
            : s
        )
      );
    },
    [activeSessionId]
  );

  const handleNewSession = useCallback(() => {
    // Stop any ongoing stream
    abortRef.current?.abort();
    setIsLoading(false);

    const newSession = createSession();
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setShowSessionList(false);
    setInput("");
    setSelectedSkill(null);
    setSessionSkill(null);
  }, []);

  const handleSwitchSession = useCallback(
    (sessionId: string) => {
      if (isLoading) {
        abortRef.current?.abort();
        setIsLoading(false);
      }
      setActiveSessionId(sessionId);
      setShowSessionList(false);
      setInput("");
      setSelectedSkill(null);
      setSessionSkill(null);
    },
    [isLoading]
  );

  const handleDeleteSession = useCallback(
    (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== sessionId);
        // Always keep at least one session
        if (filtered.length === 0) return [createSession()];
        return filtered;
      });
      // If deleting active session, switch to first available
      if (sessionId === activeSessionId) {
        setSessions((prev) => {
          const remaining = prev.filter((s) => s.id !== sessionId);
          if (remaining.length > 0) {
            setActiveSessionId(remaining[0].id);
          } else {
            const fresh = createSession();
            setActiveSessionId(fresh.id);
            return [fresh];
          }
          return remaining;
        });
      }
    },
    [activeSessionId]
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    // Capture attached files and skill before clearing
    const filesToAttach = [...attachedFiles];
    const skillToUse = selectedSkill || sessionSkill;

    // Update session title from first message
    if (activeSession.title === "새 대화") {
      updateSessionTitle(text);
    }

    // Build display text with attached file/skill indicators
    const skillLabel = skillToUse ? `${skillToUse.icon} ${skillToUse.title}` : "";
    const displayText = [
      skillLabel ? `⚡ 스킬: ${skillLabel}` : "",
      ...filesToAttach.map(f => `📎 ${f}`),
      text,
    ].filter(Boolean).join("\n\n");

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: displayText,
    };
    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    updateMessages((msgs) => [...msgs, userMsg, assistantMsg]);
    setInput("");
    setAttachedFiles([]);
    setShowFilePicker(false);
    // Persist skill for follow-up questions in the same session
    if (skillToUse) {
      setSessionSkill(skillToUse);
    }
    setSelectedSkill(null);
    setSkillSuggestion(null);
    setShowSkillPicker(false);
    setIsLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const callbacks: SSECallbacks = {
      onThinkingStep: (data: ThinkingStep) => {
        updateLastAssistant((msg) => {
          const steps = [...(msg.thinkingSteps || [])];
          if (data.status === "start") {
            steps.push({ step: data.step, label: data.label, detail: data.detail, status: "start" });
          } else {
            // Update existing step to done
            const idx = steps.findLastIndex((s) => s.step === data.step);
            if (idx >= 0) {
              steps[idx] = { ...steps[idx], status: "done", label: data.label, detail: data.detail };
            } else {
              steps.push({ step: data.step, label: data.label, detail: data.detail, status: "done" });
            }
          }
          return { ...msg, thinkingSteps: steps };
        });
      },
      onContentDelta: (delta) => {
        updateLastAssistant((msg) => ({
          ...msg,
          content: msg.content + delta,
        }));
      },
      onSources: (sources) => {
        updateLastAssistant((msg) => ({
          ...msg,
          sources,
        }));
      },
      onConflictWarning: (data) => {
        updateLastAssistant((msg) => ({
          ...msg,
          conflictWarning: data,
        }));
      },
      onApprovalRequest: (data) => {
        updateLastAssistant((msg) => ({
          ...msg,
          approval: data,
        }));
      },
      onSkillMatch: (data) => {
        // Show skill match as a thinking step
        updateLastAssistant((msg) => {
          const steps = [...(msg.thinkingSteps || [])];
          steps.push({
            step: "skill_match",
            label: `${data.skill_icon} ${data.skill_title} 스킬 적용`,
            detail: "",
            status: "done",
          });
          return { ...msg, thinkingSteps: steps };
        });
        // Persist auto-matched skill for follow-up questions
        const matched = skillList.find((s) => s.path === data.skill_path);
        if (matched) {
          setSessionSkill(matched);
        }
      },
      onError: (data) => {
        updateLastAssistant((msg) => ({
          ...msg,
          error: data.message,
          isStreaming: false,
        }));
        toast.error(data.message);
      },
      onDone: () => {
        updateLastAssistant((msg) => ({
          ...msg,
          isStreaming: false,
        }));
        setIsLoading(false);
      },
    };

    try {
      await streamChat(text, activeSessionId, callbacks, controller.signal, filesToAttach, skillToUse?.path);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        updateLastAssistant((msg) => ({
          ...msg,
          error: "연결이 끊어졌습니다.",
          isStreaming: false,
        }));
        toast.error("서버 연결 실패. 백엔드가 실행 중인지 확인하세요.");
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  }, [input, isLoading, activeSessionId, activeSession.title, attachedFiles, selectedSkill, updateMessages, updateLastAssistant, updateSessionTitle]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    updateLastAssistant((msg) => ({
      ...msg,
      isStreaming: false,
    }));
    setIsLoading(false);
  }, [updateLastAssistant]);

  const handleApproval = useCallback(
    async (actionId: string, approved: boolean, actionType?: string, path?: string) => {
      try {
        // Capture old content before approval for diff view
        let oldContent: string | null = null;
        if (approved && actionType === "wiki_edit" && path) {
          try {
            const wiki = await fetchFile(path);
            oldContent = wiki.content;
          } catch {
            // File may not exist yet, skip diff
          }
        }

        const res = await fetch("/api/approval/resolve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: activeSessionId,
            action_id: actionId,
            approved,
          }),
        });
        if (!res.ok) throw new Error(`${res.status}`);
        updateLastAssistant((msg) => ({
          ...msg,
          approvalResolved: approved ? "approved" : "rejected",
        }));
        const isEdit = actionType === "wiki_edit";
        toast.success(
          approved
            ? isEdit ? "문서가 수정되었습니다" : "문서가 생성되었습니다"
            : "요청이 거절되었습니다"
        );
        if (approved) {
          refreshTree();
          // Show diff view for edits
          if (isEdit && path && oldContent !== null) {
            setAgentDiff({ filePath: path, oldContent });
            openTab(path);
          }
        }
      } catch {
        toast.error("승인 처리에 실패했습니다");
      }
    },
    [activeSessionId, updateLastAssistant, refreshTree, setAgentDiff, openTab]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Session List View ───────────────────────────────────────────────
  if (showSessionList) {
    return (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-2.5 border-b">
          <button
            onClick={() => setShowSessionList(false)}
            className="p-0.5 rounded hover:bg-muted"
            title="돌아가기"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-semibold flex-1">대화 목록</span>
          <button
            onClick={handleNewSession}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
            title="새 대화"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-auto">
          {sessions.map((session) => (
            <div
              key={session.id}
              role="button"
              tabIndex={0}
              onClick={() => handleSwitchSession(session.id)}
              onKeyDown={(e) => e.key === "Enter" && handleSwitchSession(session.id)}
              className={`w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-muted/50 transition-colors border-b border-border/50 group cursor-pointer ${
                session.id === activeSessionId
                  ? "bg-primary/5 border-l-2 border-l-primary"
                  : ""
              }`}
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {session.title}
                </div>
                <div className="text-xs text-muted-foreground">
                  {session.messages.length === 0
                    ? "빈 대화"
                    : `${Math.ceil(session.messages.length / 2)}개 질문`}
                  {" · "}
                  {formatTime(session.createdAt)}
                </div>
              </div>
              {sessions.length > 1 && (
                <button
                  onClick={(e) => handleDeleteSession(session.id, e)}
                  className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition-opacity"
                  title="삭제"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Chat View ─────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold flex-1 truncate">
          {activeSession.title === "새 대화" ? "On-Tong Agent" : activeSession.title}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewSession}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
            title="새 대화"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowSessionList(true)}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
            title="대화 목록"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto px-4 py-3 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
            <Sparkles className="h-8 w-8 opacity-30" />
            <p className="text-sm">Wiki에 대해 질문해보세요</p>
            <div className="text-xs space-y-1 text-center opacity-70">
              <p>&quot;주문 처리 규칙 알려줘&quot;</p>
              <p>&quot;DG320 에러 대응 방법은?&quot;</p>
              <p>&quot;캐시 장애 대응 문서 만들어줘&quot;</p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id}>
            {msg.role === "user" ? (
              <UserBubble content={msg.content} />
            ) : (
              <AssistantBubble
                msg={msg}
                onSourceClick={openTab}
                onApproval={handleApproval}
              />
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t px-4 py-3 space-y-2">
        {/* Auto-suggestion banner */}
        {skillSuggestion && !selectedSkill && (
          <div className="flex items-center gap-2 text-xs bg-primary/5 border border-primary/20 rounded-lg px-3 py-1.5">
            <span>{skillSuggestion.icon}</span>
            <span className="flex-1 truncate font-medium">{skillSuggestion.title}</span>
            <button
              onClick={() => { setSelectedSkill(skillSuggestion); setSkillSuggestion(null); }}
              className="text-primary hover:underline font-medium"
            >사용</button>
            <button
              onClick={() => { setDismissedSkills((s) => new Set(s).add(skillSuggestion.path)); setSkillSuggestion(null); }}
              className="text-muted-foreground hover:text-foreground"
            >무시</button>
          </div>
        )}

        {/* Selected/session skill pill */}
        {(selectedSkill || sessionSkill) && (
          <div className="flex items-center gap-1 text-xs bg-primary/10 text-primary px-2.5 py-1 rounded-full w-fit">
            <span>{(selectedSkill || sessionSkill)!.icon}</span>
            <span className="font-medium">{(selectedSkill || sessionSkill)!.title}</span>
            {!selectedSkill && sessionSkill && (
              <span className="text-muted-foreground ml-0.5">(유지 중)</span>
            )}
            <button onClick={() => { setSelectedSkill(null); setSessionSkill(null); }} className="ml-1 hover:text-destructive">
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        {/* Attached files chips */}
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {attachedFiles.map((fp) => (
              <span
                key={fp}
                className="inline-flex items-center gap-1 rounded-md bg-primary/10 text-primary px-2 py-0.5 text-xs"
              >
                <FileText className="h-3 w-3" />
                {fp.split("/").pop()}
                <button
                  onClick={() => setAttachedFiles((prev) => prev.filter((f) => f !== fp))}
                  className="ml-0.5 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* File picker dropdown */}
        {showFilePicker && (
          <div className="rounded-lg border bg-popover shadow-md p-1 max-h-40 overflow-auto">
            <div className="px-2 py-1 text-xs text-muted-foreground font-medium">
              열린 탭에서 첨부할 파일 선택
            </div>
            {tabs.length === 0 ? (
              <div className="px-2 py-2 text-xs text-muted-foreground">열린 파일이 없습니다</div>
            ) : (
              tabs
                .filter((t) => !attachedFiles.includes(t.filePath))
                .map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setAttachedFiles((prev) => [...prev, tab.filePath]);
                      setShowFilePicker(false);
                      inputRef.current?.focus();
                    }}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded hover:bg-muted text-left"
                  >
                    <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                    <span className="truncate">{tab.title}</span>
                  </button>
                ))
            )}
          </div>
        )}

        {/* Skill picker dropdown */}
        {showSkillPicker && (() => {
          const enabledSkills = skillList.filter((s) => s.enabled);
          const q = skillSearch.toLowerCase();
          const filtered = q
            ? enabledSkills.filter(
                (s) =>
                  s.title.toLowerCase().includes(q) ||
                  s.description.toLowerCase().includes(q) ||
                  s.trigger.some((t) => t.toLowerCase().includes(q))
              )
            : enabledSkills;
          const grouped: Record<string, SkillMeta[]> = {};
          for (const s of filtered) {
            const cat = s.category || "미분류";
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(s);
          }
          const catKeys = Object.keys(grouped).sort((a, b) => {
            if (a === "미분류") return 1;
            if (b === "미분류") return -1;
            return a.localeCompare(b);
          });
          return (
            <div className="rounded-lg border bg-popover shadow-md p-1 max-h-56 overflow-auto">
              <div className="px-2 py-1 text-xs text-muted-foreground font-medium">스킬 선택</div>
              {enabledSkills.length >= 5 && (
                <input
                  value={skillSearch}
                  onChange={(e) => setSkillSearch(e.target.value)}
                  placeholder="스킬 검색..."
                  className="w-full text-xs px-2 py-1 mb-1 rounded border bg-background"
                  autoFocus
                />
              )}
              {filtered.length === 0 ? (
                <div className="px-2 py-2 text-xs text-muted-foreground">
                  {enabledSkills.length === 0 ? "등록된 스킬이 없습니다" : "검색 결과 없음"}
                </div>
              ) : (
                catKeys.map((cat) => (
                  <div key={cat}>
                    {catKeys.length > 1 && (
                      <div className="px-2 py-0.5 text-[10px] text-muted-foreground font-semibold uppercase">{cat}</div>
                    )}
                    {grouped[cat].map((skill) => (
                      <button
                        key={skill.path}
                        onClick={() => {
                          setSelectedSkill(skill);
                          setShowSkillPicker(false);
                          setSkillSearch("");
                          inputRef.current?.focus();
                        }}
                        className="w-full flex items-center gap-2 px-2 py-1.5 text-xs rounded hover:bg-muted text-left"
                      >
                        <span className="text-base">{skill.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{skill.title}</div>
                          <div className="text-muted-foreground truncate">{skill.description}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          );
        })()}

        <div className="flex items-end gap-2">
          <button
            onClick={() => setShowFilePicker((v) => !v)}
            className={`shrink-0 rounded-lg p-2 transition-colors ${
              showFilePicker || attachedFiles.length > 0
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
            title="파일 첨부"
          >
            <Paperclip className="h-4 w-4" />
          </button>
          <button
            onClick={() => { setShowSkillPicker((v) => { if (!v) refreshSkillList(); return !v; }); setShowFilePicker(false); }}
            className={`shrink-0 rounded-lg p-2 transition-colors ${
              showSkillPicker || selectedSkill || sessionSkill
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
            title="스킬 선택"
          >
            <Zap className="h-4 w-4" />
          </button>
          <textarea
            ref={inputRef}
            className="flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring min-h-[40px] max-h-[120px]"
            placeholder="질문을 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          {isLoading ? (
            <button
              onClick={handleStop}
              className="shrink-0 rounded-lg bg-destructive p-2 text-destructive-foreground hover:bg-destructive/90"
              title="중지"
            >
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="shrink-0 rounded-lg bg-primary p-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
              title="전송"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────

function createSession(): ChatSession {
  return {
    id: crypto.randomUUID(),
    title: "새 대화",
    messages: [],
    createdAt: Date.now(),
  };
}

function formatTime(ts: number): string {
  const now = Date.now();
  const diff = now - ts;
  if (diff < 60_000) return "방금";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}분 전`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}시간 전`;
  return new Date(ts).toLocaleDateString("ko-KR", {
    month: "short",
    day: "numeric",
  });
}

// ── Sub-components ───────────────────────────────────────────────────

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-lg bg-primary px-3 py-2 text-primary-foreground text-sm whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

function AssistantBubble({
  msg,
  onSourceClick,
  onApproval,
}: {
  msg: ChatMessage;
  onSourceClick: (path: string) => void;
  onApproval: (actionId: string, approved: boolean, actionType?: string, path?: string) => void;
}) {
  const hasThinkingSteps = msg.thinkingSteps && msg.thinkingSteps.length > 0;
  const allStepsDone = hasThinkingSteps && msg.thinkingSteps!.every((s) => s.status === "done");
  const isThinking = hasThinkingSteps && !allStepsDone && !msg.content;

  return (
    <div className="space-y-2">
      {/* Thinking Steps */}
      {hasThinkingSteps && (
        <ThinkingStepsDisplay
          steps={msg.thinkingSteps!}
          isStreaming={!!msg.isStreaming}
          collapsed={!!msg.content && !!allStepsDone}
        />
      )}

      {/* Content */}
      <div className="max-w-[95%] rounded-lg bg-muted/50 px-3 py-2 text-sm">
        {isThinking && !msg.content && (
          <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5 align-text-bottom" />
        )}
        <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2 prose-pre:my-2 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:bg-muted prose-code:text-[0.85em] prose-code:before:content-none prose-code:after:content-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.content}
          </ReactMarkdown>
        </div>
        {msg.isStreaming && msg.content && (
          <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5 align-text-bottom" />
        )}
        {msg.error && (
          <div className="mt-2 text-destructive text-xs">
            {msg.error}
          </div>
        )}
      </div>

      {/* Conflict Warning Banner */}
      {msg.conflictWarning && (
        <div className="rounded-lg border border-amber-400/50 bg-amber-50 dark:bg-amber-950/30 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
            <svg className="h-4 w-4 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            문서 간 내용 차이 감지
          </div>
          <p className="text-xs text-amber-800 dark:text-amber-300/80 leading-relaxed">
            {msg.conflictWarning.details}
          </p>
          {msg.conflictWarning.conflicting_docs.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {msg.conflictWarning.conflicting_docs.map((doc) => (
                <button
                  key={doc}
                  onClick={() => onSourceClick(doc)}
                  className="inline-flex items-center gap-1 rounded border border-amber-300 dark:border-amber-600 px-1.5 py-0.5 text-[11px] text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors"
                >
                  <FileText className="h-3 w-3" />
                  {doc.split("/").pop()}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sources */}
      {msg.sources && msg.sources.length > 0 && (
        <div className="flex flex-wrap gap-1 px-1">
          {msg.sources.map((s) => (
            <button
              key={s.doc}
              onClick={() => onSourceClick(s.doc)}
              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs transition-colors ${
                s.status === "deprecated"
                  ? "border-red-300 text-red-500 line-through hover:bg-red-50 dark:border-red-700 dark:hover:bg-red-950/30"
                  : s.status === "approved"
                  ? "border-green-300 text-green-700 hover:bg-green-50 dark:border-green-700 dark:text-green-400 dark:hover:bg-green-950/30"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              }`}
              title={[
                `관련도: ${Math.round(s.relevance * 100)}%`,
                s.updated_by && `작성자: ${s.updated_by}`,
                s.updated && `수정일: ${s.updated}`,
                s.status && `상태: ${s.status}`,
              ].filter(Boolean).join(" | ")}
            >
              {s.status === "approved" && <CircleCheck className="h-3 w-3 text-green-600" />}
              {s.status === "deprecated" && <X className="h-3 w-3 text-red-500" />}
              {(!s.status || (s.status !== "approved" && s.status !== "deprecated")) && <FileText className="h-3 w-3" />}
              <span>{s.doc.split("/").pop()}</span>
              {s.updated && (
                <span className="text-[10px] opacity-60">{s.updated.slice(5, 10)}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Approval Request */}
      {msg.approval && !msg.approvalResolved && (
        <div className="rounded-lg border border-dashed border-primary/50 bg-primary/5 p-3 space-y-2">
          <div className="text-xs font-medium text-primary">
            {msg.approval.action_type === "wiki_edit" ? "Wiki 문서 수정 요청" : "Wiki 문서 생성 요청"}
          </div>
          <div className="text-xs text-muted-foreground">
            경로: <code className="bg-muted px-1 rounded">{msg.approval.path}</code>
          </div>
          <pre className="text-xs bg-muted text-muted-foreground rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap">
            {msg.approval.diff_preview}
          </pre>
          <div className="flex gap-2">
            <button
              onClick={() => onApproval(msg.approval!.action_id, true, msg.approval!.action_type, msg.approval!.path)}
              className="inline-flex items-center gap-1 rounded-md bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700"
            >
              <Check className="h-3 w-3" /> 승인
            </button>
            <button
              onClick={() => onApproval(msg.approval!.action_id, false, msg.approval!.action_type, msg.approval!.path)}
              className="inline-flex items-center gap-1 rounded-md bg-destructive px-3 py-1 text-xs text-destructive-foreground hover:bg-destructive/90"
            >
              <X className="h-3 w-3" /> 거절
            </button>
          </div>
        </div>
      )}

      {/* Approval resolved */}
      {msg.approvalResolved && (
        <div className={`text-xs px-2 py-1 rounded ${
          msg.approvalResolved === "approved"
            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
        }`}>
          {msg.approvalResolved === "approved" ? "승인됨" : "거절됨"}
          {msg.approval && ` — ${msg.approval.path}`}
        </div>
      )}
    </div>
  );
}

// ── Thinking Steps ──────────────────────────────────────────────────

const STEP_ICONS: Record<string, React.ReactNode> = {
  query_augment: <Zap className="h-3 w-3" />,
  vector_search: <Search className="h-3 w-3" />,
  clarity_check: <MessageCircleQuestion className="h-3 w-3" />,
  cognitive_reflect: <Brain className="h-3 w-3" />,
  answer_gen: <Pencil className="h-3 w-3" />,
};

function ThinkingStepsDisplay({
  steps,
  isStreaming,
  collapsed: initialCollapsed,
}: {
  steps: ThinkingStepState[];
  isStreaming: boolean;
  collapsed: boolean;
}) {
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed);
  const prevCollapsed = useRef(initialCollapsed);

  // Auto-collapse when streaming finishes and all steps done
  useEffect(() => {
    if (initialCollapsed && !prevCollapsed.current) {
      setIsCollapsed(true);
    }
    prevCollapsed.current = initialCollapsed;
  }, [initialCollapsed]);

  const completedCount = steps.filter((s) => s.status === "done").length;
  const totalCount = steps.length;

  // Collapsed view — clickable summary
  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-1 py-0.5 rounded hover:bg-muted/50"
      >
        <ChevronRight className="h-3 w-3" />
        <Zap className="h-3 w-3 text-primary/70" />
        <span>탐색 과정 ({completedCount}단계 완료)</span>
      </button>
    );
  }

  // Expanded view
  return (
    <div className="max-w-[95%] rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
      <button
        onClick={() => initialCollapsed ? setIsCollapsed(true) : undefined}
        className={`flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-1.5 ${
          initialCollapsed ? "hover:text-foreground cursor-pointer" : "cursor-default"
        }`}
      >
        {initialCollapsed && <ChevronDown className="h-3 w-3" />}
        <Zap className="h-3 w-3 text-primary/70" />
        <span>탐색 과정</span>
      </button>
      <div className="space-y-1">
        {steps.map((step, i) => (
          <div
            key={`${step.step}-${i}`}
            className="flex items-start gap-2 text-xs"
          >
            {/* Status indicator */}
            {step.status === "done" ? (
              <CircleCheck className="h-3.5 w-3.5 text-green-500 shrink-0 mt-0.5" />
            ) : (
              <Loader2 className="h-3.5 w-3.5 text-primary animate-spin shrink-0 mt-0.5" />
            )}
            {/* Icon + Label */}
            <span className="text-muted-foreground shrink-0">
              {STEP_ICONS[step.step] || <Zap className="h-3 w-3" />}
            </span>
            <span className={step.status === "done" ? "text-foreground" : "text-foreground"}>
              {step.label}
            </span>
            {/* Detail */}
            {step.detail && (
              <span className="text-muted-foreground truncate">
                — {step.detail}
              </span>
            )}
          </div>
        ))}
        {/* Active spinner when last step is still in progress */}
        {isStreaming && steps.length > 0 && steps[steps.length - 1].status === "start" && (
          <div className="h-0.5" />
        )}
      </div>
    </div>
  );
}
