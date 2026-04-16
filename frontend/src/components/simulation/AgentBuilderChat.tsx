"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Square, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { runAgentBuilderChat, createCustomAgent } from "@/lib/simulation/api";
import { SLAB_TOOLS } from "@/lib/simulation/types";
import { cn } from "@/lib/utils";
import type { CustomAgent } from "@/lib/simulation/types";

const INITIAL_MESSAGE = `안녕하세요! 👋 Slab 설계 도메인에 특화된 Custom Agent를 만들어 드리겠습니다.

**어떤 Slab 설계 문제를 해결하고 싶으신가요?** 자유롭게 말씀해 주세요!

예시:
- "특정 주문의 폭 범위 에러를 자동으로 진단하고 싶어"
- "Edging 기준이 바뀌면 어떤 주문이 영향받는지 알고 싶어"
- "분할수를 최적화해주는 에이전트가 필요해"`;

export function AgentBuilderChat() {
  const {
    builderMessages,
    builderRunning,
    pendingAgentDef,
    addBuilderUserMessage,
    startBuilderAssistantMessage,
    appendBuilderContent,
    addBuilderThinkingStep,
    finalizeBuilderMessage,
    setBuilderRunning,
    setBuilderAbortController,
    stopBuilder,
    clearBuilderMessages,
    setPendingAgentDef,
    addCustomAgent,
    setActiveView,
  } = useSimulationStore();

  const [input, setInput] = useState("");
  const [registering, setRegistering] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 초기 메시지 표시 (메시지 없을 때)
  const showInitial = builderMessages.length === 0 && !pendingAgentDef;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [builderMessages]);

  const getHistory = () =>
    builderMessages.map((m) => ({ role: m.role, content: m.content }));

  const handleSubmit = useCallback(async () => {
    const text = input.trim();
    if (!text || builderRunning) return;

    setInput("");
    addBuilderUserMessage(text);
    const assistantId = startBuilderAssistantMessage();

    const ac = new AbortController();
    setBuilderAbortController(ac);
    setBuilderRunning(true);

    try {
      await runAgentBuilderChat(
        text,
        getHistory(),
        {
          onThinking: (message) => {
            addBuilderThinkingStep(assistantId, { message, timestamp: Date.now() });
          },
          onContentDelta: (delta) => {
            appendBuilderContent(assistantId, delta);
          },
          onAgentReady: (agentDef) => {
            setPendingAgentDef(agentDef as Omit<CustomAgent, "id" | "created_at">);
          },
          onDone: () => {
            finalizeBuilderMessage(assistantId);
            setBuilderRunning(false);
            setBuilderAbortController(null);
          },
          onError: (msg) => {
            appendBuilderContent(assistantId, `\n\n❌ 오류: ${msg}`);
            finalizeBuilderMessage(assistantId);
            setBuilderRunning(false);
            setBuilderAbortController(null);
          },
        },
        ac.signal
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        appendBuilderContent(assistantId, `\n\n❌ 연결 오류: ${(err as Error).message}`);
      }
      finalizeBuilderMessage(assistantId);
      setBuilderRunning(false);
      setBuilderAbortController(null);
    }
  }, [input, builderRunning, builderMessages]);

  const handleRegister = async () => {
    if (!pendingAgentDef || registering) return;
    setRegistering(true);
    try {
      const newAgent = await createCustomAgent({
        ...pendingAgentDef,
        created_by: "chat",
      });
      addCustomAgent(newAgent);
      setPendingAgentDef(null);
      setActiveView({ kind: "custom_agent", agentId: newAgent.id });
    } catch (err) {
      console.error("등록 실패:", err);
    } finally {
      setRegistering(false);
    }
  };

  const handleReset = () => {
    clearBuilderMessages();
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/20">
        <div className="flex items-center gap-2">
          <span className="text-sm">🗨️</span>
          <span className="text-sm font-semibold">채팅으로 Agent 만들기</span>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="대화 초기화"
        >
          <RotateCcw className="w-3 h-3" />
          초기화
        </button>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* 초기 안내 메시지 */}
        {showInitial && (
          <div className="flex justify-start">
            <div className="max-w-[85%] p-3 rounded-xl rounded-tl-sm bg-muted text-sm">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {INITIAL_MESSAGE}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* 대화 메시지 */}
        {builderMessages.map((msg) => (
          <div
            key={msg.id}
            className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}
          >
            {msg.role === "user" ? (
              <div className="max-w-[85%] bg-primary text-primary-foreground px-3 py-2 rounded-xl rounded-tr-sm text-sm">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[85%] space-y-2">
                {(msg.thinking_steps?.length ?? 0) > 0 && (
                  <div className="text-xs text-muted-foreground px-1 flex items-center gap-1">
                    <span className="animate-pulse">🤔</span>
                    {msg.thinking_steps![msg.thinking_steps!.length - 1].message}
                  </div>
                )}
                {msg.content && (
                  <div className="bg-muted p-3 rounded-xl rounded-tl-sm">
                    <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                      {msg.isStreaming && (
                        <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5 align-middle" />
                      )}
                    </div>
                  </div>
                )}
                {msg.isStreaming && !msg.content && (
                  <div className="flex gap-1 px-1">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* agent_ready: 에이전트 미리보기 + 등록 버튼 */}
      {pendingAgentDef && !builderRunning && (
        <div className="mx-4 mb-4 p-4 rounded-xl border-2 border-primary/30 bg-primary/5">
          <div className="flex items-start gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center text-xl shrink-0"
              style={{ backgroundColor: (pendingAgentDef.color ?? "#6366f1") + "22" }}
            >
              {pendingAgentDef.icon ?? "🤖"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold">{pendingAgentDef.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{pendingAgentDef.description}</div>
              <div className="flex flex-wrap gap-1 mt-2">
                {(pendingAgentDef.available_tools ?? []).map((t) => {
                  const tool = SLAB_TOOLS.find((st) => st.id === t);
                  return (
                    <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full border bg-background">
                      {tool?.icon} {tool?.label ?? t}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
          <button
            onClick={handleRegister}
            disabled={registering}
            className="w-full py-2 px-4 rounded-lg text-sm font-medium text-white bg-primary hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {registering ? "등록 중..." : "🤖 이 Agent 등록하기"}
          </button>
        </div>
      )}

      {/* 입력창 */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="원하는 에이전트를 자유롭게 설명해주세요..."
            className="flex-1 min-h-[60px] max-h-[120px] resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            disabled={builderRunning}
          />
          <div className="flex flex-col gap-1.5">
            {builderRunning ? (
              <button
                onClick={stopBuilder}
                className="p-2 rounded-md bg-red-500 hover:bg-red-600 text-white transition-colors"
                title="중지"
              >
                <Square className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={!input.trim()}
                className="p-2 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5">
          Enter로 전송 · Shift+Enter 줄바꿈
        </p>
      </div>
    </div>
  );
}
